"""
Real-Debrid desde el propio PC (mismo flujo que Android y la web):
addMagnet -> selectFiles -> poll -> unrestrict -> URL HTTPS directa.
Port de `RealDebrid.kt`.

El token es privado: se guarda cifrado con DPAPI (ver almacen.py) y, si hay
sesión, va con la CUENTA en Firestore (account.rdToken), no con el aparato.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

import requests

from . import almacen
from . import search as S
from .red import sesion

API = "https://api.real-debrid.com/rest/1.0"
_VIDEO = re.compile(r"\.(mp4|mkv|avi|m4v|webm|mov|wmv|mpg|mpeg|ts)$", re.I)
_BAD = ("magnet_error", "error", "virus", "dead")

token: str = ""
account: str | None = None
info: dict | None = None
info_error = ""
info_loading = False
cached_hashes: set[str] = set()

# Torrent RD ya creado por magnet: los reintentos (mientras RD lo baja a sus
# servidores) no deben añadir el mismo torrent una y otra vez.
_torrent_id_by_magnet: dict[str, str] = {}
_oyentes: list[Callable[[], None]] = []
_lock = threading.Lock()


class ErrorRD(RuntimeError):
    pass


def al_cambiar(fn: Callable[[], None]) -> None:
    _oyentes.append(fn)


def _avisar() -> None:
    for fn in list(_oyentes):
        fn()


def init() -> None:
    global token
    token = almacen.secreto("rd_token")


def configured() -> bool:
    return bool(token)


def _save() -> None:
    almacen.guardar_secreto("rd_token", token)


def error_es(code: str) -> str:
    """Los códigos de error de RD, en castellano y **con la salida**.

    El que más sale es `infringing_file`: RD tiene una lista de torrents
    bloqueados por copyright, y el bloqueo va **por torrent concreto, no por
    título**, así que la salida es probar otra versión del mismo capítulo.
    """
    return {
        "infringing_file": "Real-Debrid ha rechazado ese torrent: está en su lista de bloqueados por "
                           "copyright. El bloqueo es de ese torrent concreto, no del título, así que "
                           "prueba con otra versión del mismo capítulo.",
        "hoster_unavailable": "Ese servidor no está disponible ahora mismo en Real-Debrid.",
        "hoster_not_free": "Real-Debrid no admite ese servidor.",
        "hoster_unsupported": "Real-Debrid no admite ese servidor.",
        "too_many_active_downloads": "Demasiadas descargas activas en Real-Debrid; espera un momento.",
        "active_downloads_exceeded": "Has llegado al máximo de descargas a la vez de Real-Debrid.",
        "torrent_too_big": "El torrent es demasiado grande para tu cuenta de Real-Debrid.",
        "magnet_invalid": "Real-Debrid no ha podido leer ese torrent (fichero o magnet no válido).",
        "torrent_file_invalid": "Real-Debrid no ha podido leer ese torrent (fichero o magnet no válido).",
        "no_server": "Real-Debrid no tiene servidor libre para eso ahora.",
        "permission_denied": "Tu cuenta de Real-Debrid no tiene permiso para eso (¿sin premium?).",
        "bad_token": "Token de Real-Debrid inválido o caducado.",
        "ip_not_allowed": "Real-Debrid no permite esta IP (¿VPN o red compartida?).",
        "traffic_exhausted": "Se ha agotado el tráfico de tu cuenta de Real-Debrid.",
        "action_already_done": "Eso ya estaba hecho.",
        "unknown_ressource": "Real-Debrid no encuentra eso (¿borrado de la cuenta?).",
    }.get(code.strip().lower(), f"Real-Debrid: {code}")


def status_es(st: str) -> str:
    """El estado de RD, en castellano y sin jerga."""
    return {
        "magnet_conversion": "leyendo el magnet",
        "waiting_files_selection": "esperando a elegir archivos",
        "queued": "en cola",
        "downloading": "descargando en Real-Debrid",
        "downloaded": "listo",
        "compressing": "comprimiendo",
        "uploading": "subiendo",
        "magnet_error": "el magnet no vale",
        "error": "error",
        "virus": "rechazado (virus)",
        "dead": "sin semillas: nadie lo comparte",
    }.get(st, st or "desconocido")


def _raw(method: str, path: str, form: dict | None = None, tok: str | None = None):
    """Llamada cruda. Cuando RD falla suele explicar el motivo en `error`: se
    propaga, que es mucho más útil que un "respondió 400" a secas."""
    try:
        r = sesion.request(method, API + path, data=form,
                           headers={"Authorization": f"Bearer {tok if tok is not None else token}"},
                           timeout=(10, 20))
    except requests.RequestException as e:
        raise ErrorRD(f"Sin conexión con Real-Debrid ({e.__class__.__name__}).") from e
    if r.ok or r.status_code == 204:
        return r.json() if r.content else {}
    try:
        why = str(r.json().get("error", ""))
    except ValueError:
        why = ""
    if r.status_code == 401:
        raise ErrorRD("Token de Real-Debrid inválido o caducado.")
    if r.status_code == 403 and not why:
        raise ErrorRD("Real-Debrid rechaza la cuenta (¿sin premium?).")
    raise ErrorRD(error_es(why) if why else f"Real-Debrid respondió {r.status_code}.")


# ------------------------------------------------------------------ cuenta
def refresh_info() -> None:
    """Relee cuenta y límites. Los huecos de torrent van en otra ruta y pueden
    fallar por su cuenta: si no se leen, el resto sigue siendo útil."""
    global info, info_error, info_loading
    if not configured():
        info, info_error = None, ""
        _avisar()
        return
    info_loading = True
    _avisar()
    try:
        u = _raw("GET", "/user")
        used = limit = -1
        try:
            a = _raw("GET", "/torrents/activeCount")
            used, limit = int(a.get("nb", -1)), int(a.get("limit", -1))
        except ErrorRD:
            pass
        secs = int(u.get("premium") or 0)
        exp = str(u.get("expiration") or "")
        try:
            y, m, d = exp[:10].split("-")
            bonita = f"{d}/{m}/{y}"
        except ValueError:
            bonita = exp
        info = {
            "username": u.get("username", ""), "email": u.get("email", ""),
            "premium": u.get("type") == "premium", "days": secs // 86400,
            "expiration": exp, "expiresPretty": bonita, "points": int(u.get("points") or 0),
            "slotsUsed": used, "slotsLimit": limit,
            "slotsKnown": limit > 0, "slotsFull": limit > 0 and used >= limit,
        }
        info_error = ""
    except ErrorRD as e:
        info_error = str(e)
    finally:
        info_loading = False
        _avisar()


def connect(new_token: str) -> tuple[bool, str]:
    """Valida con el token CANDIDATO y solo lo guarda si vale: así un token
    malo no deja la app a medias ni rompe llamadas en curso."""
    global token, account
    cand = new_token.strip()
    try:
        u = _raw("GET", "/user", tok=cand)
    except ErrorRD as e:
        return False, str(e)
    token, account = cand, u.get("username", "")
    _save()
    _avisar()
    threading.Thread(target=refresh_info, daemon=True).start()
    return True, account if u.get("type") == "premium" else f"{account} (SIN premium)"


def adopt_token(t: str) -> None:
    """Adopta el token de la CUENTA: si en este PC había otro, se sustituye. Si
    el de la nube no vale, connect falla y se queda el actual."""
    cand = t.strip()
    if cand and cand != token:
        connect(cand)


def disconnect() -> None:
    global token, account, info, info_error, cached_hashes
    token, account, info, info_error = "", None, None, ""
    cached_hashes = set()
    _save()
    _avisar()


# --------------------------------------------------------------- streaming
def _select_video_files(tid: str, inf: dict) -> None:
    """Marca los vídeos del torrent; sin selectFiles se queda parado para siempre."""
    vids = [str(f.get("id")) for f in inf.get("files") or [] if _VIDEO.search(str(f.get("path", "")))]
    _raw("POST", f"/torrents/selectFiles/{tid}", {"files": ",".join(vids) if vids else "all"})


def _torrent_for(magnet: str) -> str:
    tid = _torrent_id_by_magnet.get(magnet)
    if tid:
        return tid
    tid = str(_raw("POST", "/torrents/addMagnet", {"magnet": magnet}).get("id", ""))
    if tid:
        _torrent_id_by_magnet[magnet] = tid
    return tid


def _wait_downloaded(tid: str, tries: int = 12) -> dict:
    inf = _raw("GET", f"/torrents/info/{tid}")
    selected = False
    if inf.get("status") == "waiting_files_selection":
        _select_video_files(tid, inf)
        selected = True
    for _ in range(tries):
        inf = _raw("GET", f"/torrents/info/{tid}")
        st = inf.get("status")
        if st == "downloaded":
            break
        # Puede llegar aquí en magnet_conversion/queued antes de pedir selección
        if st == "waiting_files_selection" and not selected:
            _select_video_files(tid, inf)
            selected = True
        if st in _BAD:
            raise ErrorRD(f"Real-Debrid no pudo con el torrent: {status_es(st)}.")
        time.sleep(1.5)
    return inf


def stream_magnet(magnet: str) -> dict:
    """magnet -> URL directa. Devuelve {url, filename} si está listo, o
    {progress} si RD aún lo está bajando a sus servidores, o {error}."""
    try:
        tid = _torrent_for(magnet)
        if not tid:
            return {"error": "RD no aceptó el magnet."}
        inf = _wait_downloaded(tid)
        if inf.get("status") != "downloaded":
            return {"progress": int(inf.get("progress") or 0)}
        links = inf.get("links") or []
        if not links:
            return {"error": "RD no devolvió enlaces."}
        un = _raw("POST", "/unrestrict/link", {"link": links[0]})
        dl = un.get("download", "")
        if not dl:
            return {"error": "No se pudo generar el enlace directo."}
        return {"url": dl, "filename": un.get("filename") or inf.get("filename") or "video"}
    except ErrorRD as e:
        # Si el torrent cacheado ya no existe en RD, que el próximo intento lo re-añada
        _torrent_id_by_magnet.pop(magnet, None)
        return {"error": str(e)}


def _files_from(inf: dict) -> list[dict]:
    """Ficheros listos de un torrent, en orden natural (04x02 antes de 04x10).
    Los enlaces vienen en el MISMO orden que los archivos marcados, así que se
    emparejan por posición ANTES de ordenar."""
    chosen = [(str(f.get("path", "")).lstrip("/"), int(f.get("bytes") or 0))
              for f in inf.get("files") or [] if int(f.get("selected") or 0) == 1]
    out = []
    for i, link in enumerate(inf.get("links") or []):
        name, size = chosen[i] if i < len(chosen) else (f"Archivo {i + 1}", 0)
        out.append({"name": name, "short": name.rsplit("/", 1)[-1], "bytes": size,
                    "size": S.human_size(size), "link": link})
    out.sort(key=lambda f: S.natural_key(f["name"]))
    return out


def pack_files(magnet: str) -> dict:
    """Abre un PACK: lo añade si hace falta, espera a que RD lo tenga y devuelve
    la lista de capítulos. stream_magnet no sirve: coge siempre el primero."""
    try:
        tid = _torrent_for(magnet)
        if not tid:
            return {"error": "Real-Debrid no aceptó el magnet."}
        inf = _wait_downloaded(tid)
        if inf.get("status") != "downloaded":
            return {"progress": int(inf.get("progress") or 0)}
        files = _files_from(inf)
        return {"files": files} if files else {"error": "El pack no trae ningún vídeo reconocible."}
    except ErrorRD as e:
        _torrent_id_by_magnet.pop(magnet, None)
        return {"error": str(e)}


def unrestrict(link: str) -> dict:
    """Enlace de RD (o de hoster: 1fichier, Mega…) -> URL directa."""
    try:
        un = _raw("POST", "/unrestrict/link", {"link": link.strip()})
    except ErrorRD as e:
        return {"error": str(e)}
    dl = un.get("download", "")
    if not dl:
        return {"error": "Real-Debrid no devolvió un enlace directo."}
    return {"url": dl, "filename": un.get("filename") or "video"}


# --------------------------------------------------- gestión de la cuenta
def add_magnet(magnet: str) -> dict:
    """Mete un magnet en la cuenta y le marca los vídeos. NO espera a que
    termine: el progreso se ve luego en la lista."""
    m = magnet.strip()
    if not m.lower().startswith("magnet:"):
        return {"error": "Eso no es un magnet (tiene que empezar por «magnet:?xt=…»)."}
    try:
        tid = str(_raw("POST", "/torrents/addMagnet", {"magnet": m}).get("id", ""))
        if not tid:
            return {"error": "Real-Debrid no aceptó el magnet."}
        for _ in range(10):
            inf = _raw("GET", f"/torrents/info/{tid}")
            st = inf.get("status")
            if st == "waiting_files_selection":
                _select_video_files(tid, inf)
                break
            if st in _BAD:
                return {"error": f"Real-Debrid no pudo con el torrent: {status_es(st)}."}
            if st not in ("magnet_conversion", "queued"):
                break
            time.sleep(1.2)
        return {"id": tid}
    except ErrorRD as e:
        return {"error": str(e)}


def torrents() -> list[dict]:
    """Los torrents de la cuenta, del más reciente al más antiguo. De paso se
    apuntan los listos: es lo que marca en la ficha qué se ve al instante."""
    global cached_hashes
    out = []
    for t in _raw("GET", "/torrents?limit=50") or []:
        st = t.get("status", "")
        size = int(t.get("bytes") or 0)
        out.append({
            "id": t.get("id", ""),
            "name": t.get("filename") or t.get("original_filename") or "torrent",
            "hash": str(t.get("hash") or "").lower(),
            "status": st, "statusEs": status_es(st),
            "progress": int(t.get("progress") or 0),
            "bytes": size, "size": S.human_size(size),
            "links": len(t.get("links") or []),
            "speed": int(t.get("speed") or 0),
            "seeders": int(t.get("seeders") or 0),
            "ready": st == "downloaded",
            "working": st in ("magnet_conversion", "queued", "downloading", "compressing", "uploading"),
        })
    cached_hashes = {t["hash"] for t in out if t["ready"] and t["hash"]}
    _avisar()
    return out


def refresh_cached() -> None:
    if not configured():
        return
    try:
        torrents()
    except ErrorRD:
        pass


def torrent_files(tid: str) -> dict:
    try:
        inf = _raw("GET", f"/torrents/info/{tid}")
    except ErrorRD as e:
        return {"error": str(e)}
    files = _files_from(inf)
    if not files:
        return {"error": f"Todavía no hay nada listo: {status_es(inf.get('status', ''))}."}
    return {"files": files}


def delete_torrent(tid: str) -> str | None:
    try:
        _raw("DELETE", f"/torrents/delete/{tid}")
        return None
    except ErrorRD as e:
        return str(e)
