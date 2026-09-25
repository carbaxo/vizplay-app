"""
Gestor de descargas con **pausa y continuación**. Port de `Downloads.kt`.

Se descarga con peticiones HTTP `Range`, así que continuar es pedir «desde el
byte N»; y si el enlace de Real-Debrid ha caducado (van atados a tu IP y
expiran), se le pide uno nuevo con el magnet guardado y se sigue desde donde
iba, sin volver a empezar.

En Android lo mueve WorkManager y sigue con la app cerrada. En el PC cada
descarga es un hilo de la app: al cerrarla se PAUSAN (lo bajado se queda en
disco) y al volver a abrirla se continúan con un clic.
"""
from __future__ import annotations

import hashlib
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Callable

import requests

from . import almacen, prefs, realdebrid
from .red import AGENTE, sesion

QUEUED, RUNNING, PAUSED, DONE, ERROR = "queued", "running", "paused", "done", "error"
_FICHERO = "descargas.json"
_MAX_A_LA_VEZ = 3
_VIDEO_EXT = re.compile(r"\.(mkv|mp4|avi|m4v|webm|mov|wmv|mpg|mpeg|ts)$", re.I)

_jobs: list[dict] = []
_lock = threading.RLock()
_hilos: dict[str, threading.Thread] = {}
_pausar: set[str] = set()
_oyentes: list[Callable[[], None]] = []
_ultimo_guardado = 0.0


def al_cambiar(fn: Callable[[], None]) -> None:
    _oyentes.append(fn)


def _avisar() -> None:
    for fn in list(_oyentes):
        fn()


def init() -> None:
    with _lock:
        _jobs[:] = [j for j in almacen.leer_json(_FICHERO, []) if isinstance(j, dict) and j.get("id")]
        # Nada puede estar «descargando» si acabamos de arrancar: si la app se
        # cerró a mitad, el estado quedó congelado y la lista mostraría una
        # descarga viva que no existe.
        for j in _jobs:
            j["speed"] = 0
            if j.get("state") in (RUNNING, QUEUED):
                j["state"] = PAUSED
        _adopt_loose_files()
    _save(force=True)


def _save(force: bool = False) -> None:
    global _ultimo_guardado
    ahora = time.monotonic()
    # El progreso llega varias veces por segundo: a disco solo en los cambios de
    # estado y de vez en cuando.
    if not force and ahora - _ultimo_guardado < 3:
        return
    _ultimo_guardado = ahora
    with _lock:
        datos = [{k: v for k, v in j.items() if k != "speed"} for j in _jobs]
    almacen.guardar_json(_FICHERO, datos)


def _adopt_loose_files() -> None:
    """Vídeos que están en la carpeta pero no en la lista (bajados por otra app,
    o de antes de reinstalar), para que aparezcan listos para ver."""
    carpeta = prefs.download_dir()
    if not carpeta.is_dir():
        return
    with _lock:
        rutas = {str(Path(j["file"]).resolve()).lower() for j in _jobs if j.get("file")}
        ahora = time.time()
        for f in carpeta.iterdir():
            if not f.is_file() or not _VIDEO_EXT.search(f.name) or f.stat().st_size <= 0:
                continue
            if str(f.resolve()).lower() in rutas:
                continue
            # Recién tocado: puede estar BAJANDO ahora mismo (otra app escribiendo)
            if ahora - f.stat().st_mtime < 60:
                continue
            size = f.stat().st_size
            fid = hashlib.md5(str(f).lower().encode("utf-8")).hexdigest()[:12]
            _jobs.append({"id": f"file:{fid}", "name": f.name, "file": str(f), "url": "",
                          "magnet": "", "bytes": size, "total": size, "state": DONE, "error": ""})


def rescan() -> None:
    with _lock:
        _adopt_loose_files()
    _save(force=True)
    _avisar()


def lista() -> list[dict]:
    with _lock:
        out = []
        for j in _jobs:
            d = dict(j)
            d.setdefault("speed", 0)
            d["pct"] = min(1.0, j["bytes"] / j["total"]) if j.get("total") else 0.0
            out.append(d)
        return out


def get(jid: str) -> dict | None:
    with _lock:
        return next((j for j in _jobs if j["id"] == jid), None)


def _edit(jid: str, force: bool = True, **cambios) -> None:
    with _lock:
        j = next((x for x in _jobs if x["id"] == jid), None)
        if j is None:
            return
        j.update(cambios)
    _save(force)
    _avisar()


def _safe_name(name: str) -> str:
    n = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "video"
    return n if "." in n else n + ".mp4"


def _unique(carpeta: Path, name: str) -> Path:
    """Evita pisar un fichero ya descargado con el mismo nombre."""
    p = carpeta / name
    if not p.exists():
        return p
    stem, suf = p.stem, p.suffix
    n = 2
    while (carpeta / f"{stem} ({n}){suf}").exists():
        n += 1
    return carpeta / f"{stem} ({n}){suf}"


def folder_label() -> str:
    return str(prefs.download_dir())


def free_space() -> int:
    import shutil
    carpeta = prefs.download_dir()
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        return shutil.disk_usage(carpeta).free
    except OSError:
        return 0


def add(url: str, name: str, magnet: str = "") -> str:
    """Encola una descarga. El magnet es opcional pero muy recomendable: es lo
    que permite pedirle a Real-Debrid un enlace nuevo si el actual caduca."""
    carpeta = prefs.download_dir()
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Carpeta elegida que ya no existe (disco fuera): a la de por defecto,
        # en vez de perder la descarga.
        carpeta = Path.home() / "Downloads" / "VizPlay"
        carpeta.mkdir(parents=True, exist_ok=True)
    fname = _safe_name(name)
    destino = _unique(carpeta, fname)
    jid = str(uuid.uuid4())
    with _lock:
        _jobs.insert(0, {"id": jid, "name": name or fname, "file": str(destino), "url": url, "magnet": magnet,
                         "bytes": 0, "total": 0, "state": QUEUED, "error": "", "speed": 0})
    _save(force=True)
    _avisar()
    _arrancar_cola()
    return jid


def pause(jid: str) -> None:
    """Se marca antes de parar el hilo para que no lo tome por un error."""
    _pausar.add(jid)
    _edit(jid, state=PAUSED, speed=0)


def resume(jid: str) -> None:
    """Continúa desde el byte donde se quedó (o reintenta si había fallado)."""
    _pausar.discard(jid)
    _edit(jid, state=QUEUED, error="")
    _arrancar_cola()


def remove(jid: str) -> None:
    _pausar.add(jid)
    hilo = _hilos.get(jid)
    if hilo:
        hilo.join(timeout=5)
    j = get(jid)
    # Como en Android: "Borrar" quita también el vídeo del disco, esté a medias o no
    if j:
        try:
            Path(j["file"]).unlink(missing_ok=True)
        except OSError:
            pass
    with _lock:
        _jobs[:] = [x for x in _jobs if x["id"] != jid]
    _pausar.discard(jid)
    _save(force=True)
    _avisar()


def pause_all() -> None:
    """Al cerrar la app: se paran todas y lo bajado se queda en disco."""
    with _lock:
        vivas = [j["id"] for j in _jobs if j["state"] in (RUNNING, QUEUED)]
    for jid in vivas:
        pause(jid)
    for jid in vivas:
        h = _hilos.get(jid)
        if h:
            h.join(timeout=3)


def active_count() -> int:
    with _lock:
        return sum(1 for j in _jobs if j["state"] in (RUNNING, QUEUED))


def _arrancar_cola() -> None:
    with _lock:
        corriendo = sum(1 for jid, h in _hilos.items() if h.is_alive())
        for j in reversed(_jobs):   # las más antiguas primero
            if corriendo >= _MAX_A_LA_VEZ:
                break
            if j["state"] == QUEUED and not (j["id"] in _hilos and _hilos[j["id"]].is_alive()):
                h = threading.Thread(target=_worker, args=(j["id"],), daemon=True, name=f"dl-{j['id'][:8]}")
                _hilos[j["id"]] = h
                h.start()
                corriendo += 1


def _http_reason(code: int) -> str:
    if code in (401, 403):
        return "Real-Debrid rechazó el enlace (caducado o de otra IP)."
    if code in (404, 410):
        return "El archivo ya no está en Real-Debrid."
    if code == 416:
        return "El servidor no admite continuar la descarga."
    if code == 429:
        return "Demasiadas peticiones a Real-Debrid; prueba en un rato."
    if 500 <= code <= 599:
        return f"Real-Debrid falló ({code}); prueba en un rato."
    return f"El servidor respondió {code}."


def _fresh_url(magnet: str) -> str | None:
    if not magnet:
        return None
    for _ in range(8):   # RD puede tardar si tiene que re-preparar el torrent
        r = realdebrid.stream_magnet(magnet)
        if r.get("url"):
            return r["url"]
        if "progress" not in r:
            return None
        time.sleep(3)
    return None


def _worker(jid: str) -> None:
    try:
        _descargar(jid)
    except Exception as e:  # noqa: BLE001 - un fallo raro no puede matar la app
        _edit(jid, state=ERROR, error=f"Error de descarga: {e}", speed=0)
    finally:
        _arrancar_cola()


def _descargar(jid: str) -> None:
    j = get(jid)
    if not j or jid in _pausar:
        return
    _edit(jid, state=RUNNING, error="")
    url, renewed = j["url"], False
    destino = Path(j["file"])
    destino.parent.mkdir(parents=True, exist_ok=True)

    for _ in range(3):   # intento normal + con enlace renovado (+1 si se corta)
        have = destino.stat().st_size if destino.exists() else 0
        headers = {"User-Agent": AGENTE}
        if have > 0:
            headers["Range"] = f"bytes={have}-"
        try:
            resp = sesion.get(url, headers=headers, stream=True, timeout=(25, 60))
        except requests.RequestException:
            _edit(jid, state=ERROR, error="Se cortó la conexión. Pulsa continuar.", speed=0)
            return

        with resp:
            # 416 = el rango pedido no existe: el fichero ya estaba completo
            if resp.status_code == 416:
                _finish(jid)
                return
            if not resp.ok:
                # Los enlaces de RD caducan: con el magnet se pide uno nuevo
                if not renewed and j.get("magnet"):
                    renewed = True
                    _edit(jid, state=RUNNING, error="Renovando el enlace en Real-Debrid…")
                    fresh = _fresh_url(j["magnet"])
                    if fresh and fresh != url:
                        url = fresh
                        _edit(jid, url=fresh, error="")
                        continue
                _edit(jid, state=ERROR, error=_http_reason(resp.status_code), speed=0)
                return

            # 206 = nos da el trozo pedido. 200 con have>0 = ignoró el Range y
            # manda el fichero entero: hay que empezar de cero.
            partial = resp.status_code == 206 and have > 0
            try:
                length = int(resp.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            total = (have + length) if partial else length
            if total > 0:
                _edit(jid, total=total)
            written = have if partial else 0
            t0, b0 = time.monotonic(), written
            with open(destino, "r+b" if (partial and destino.exists()) else "wb") as f:
                if partial:
                    f.seek(have)
                    f.truncate()
                try:
                    for chunk in resp.iter_content(256 * 1024):
                        if jid in _pausar:
                            _edit(jid, bytes=written, speed=0, state=PAUSED)
                            return
                        if not chunk:
                            continue
                        f.write(chunk)
                        written += len(chunk)
                        ahora = time.monotonic()
                        if ahora - t0 >= 0.8:
                            speed = int((written - b0) / (ahora - t0))
                            _edit(jid, force=False, bytes=written, speed=speed, state=RUNNING,
                                  total=total if total > 0 else get(jid)["total"])
                            t0, b0 = ahora, written
                except requests.RequestException:
                    _edit(jid, bytes=written, state=ERROR, speed=0,
                          error="La descarga se cortó a mitad. Pulsa continuar.")
                    return
            # El servidor cortó antes de tiempo: al continuar, el Range sigue
            if total > 0 and written < total:
                _edit(jid, bytes=written, state=ERROR, speed=0,
                      error="La descarga se cortó a mitad. Pulsa continuar.")
                return
            _finish(jid)
            return
    _edit(jid, state=ERROR, speed=0, error="No se pudo continuar la descarga. Pulsa continuar.")


def _finish(jid: str) -> None:
    j = get(jid)
    if not j:
        return
    try:
        size = Path(j["file"]).stat().st_size
    except OSError:
        size = j["bytes"]
    _edit(jid, state=DONE, bytes=size, total=j["total"] or size, speed=0, error="")
