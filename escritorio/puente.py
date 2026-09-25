"""
El puente entre el núcleo (Python) y la interfaz (QML).

Dos canales, y nada más:

 - `estado` (propiedad JSON): TODO lo que la interfaz pinta y no hay que pedir
   (sesión, perfiles, Mi lista, progreso, descargas, Real-Debrid, ajustes). El
   núcleo avisa de cada cambio y aquí se agrupan en un solo envío cada ~120 ms:
   las descargas notifican varias veces por segundo y reenviar el estado entero
   por cada una sería tirar CPU.
 - `pedir(tipo, args)` -> id, y la respuesta llega luego por la señal `evento`
   con ese id. Es el embudo: todo lo lento (red, Real-Debrid, Firebase) corre en
   un hilo aparte y vuelve al hilo de Qt por UNA señal interna, así que la UI
   nunca espera. La búsqueda de fuentes manda varias respuestas con el mismo id
   (una por motor que contesta) y la última lleva `fin: true`.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from .nucleo import (downloads, fuentes, google_login, lang, links, motores, prefs, rd_engine,
                     realdebrid, sync, tmdb, watch_store)
from .nucleo import search as S

log = logging.getLogger("vizplay.puente")


def _vlc() -> str:
    """Ruta de VLC si está instalado (el mejor con MKV + DTS/TrueHD)."""
    for c in (shutil.which("vlc"),
              os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "VideoLAN", "VLC", "vlc.exe"),
              os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "VideoLAN", "VLC",
                           "vlc.exe")):
        if c and os.path.isfile(c):
            return c
    return ""


class Puente(QObject):
    estadoChanged = Signal()
    evento = Signal(str)
    _despacha = Signal(object)   # de cualquier hilo -> hilo de Qt (AutoConnection encola)
    _cambio = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._estado = "{}"
        self._ids = itertools.count(1)
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="puente")
        # Para lo que un pedido lanza en paralelo por dentro: si saliera del mismo
        # pool, con los 8 hilos ocupados se esperarían unos a otros para siempre.
        self._aux = ThreadPoolExecutor(max_workers=6, thread_name_prefix="aux")
        self._despacha.connect(self._recibe)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(120)
        self._timer.timeout.connect(self._publicar)
        self._cambio.connect(self._timer.start)
        self._vlc = _vlc()
        for mod in (prefs, realdebrid, sync, watch_store, downloads):
            mod.al_cambiar(self._cambio.emit)
        self._publicar()

    # ------------------------------------------------------------ estado
    def _get_estado(self) -> str:
        return self._estado

    estado = Property(str, _get_estado, notify=estadoChanged)

    def _publicar(self) -> None:
        a = realdebrid.info
        st = {
            "rd": {"configured": realdebrid.configured(), "account": realdebrid.account, "info": a,
                   "infoError": realdebrid.info_error, "infoLoading": realdebrid.info_loading},
            "cached": sorted(realdebrid.cached_hashes),
            "sync": {"signedIn": sync.signed_in(), "email": sync.email, "profiles": sync.profiles,
                     "active": sync.active_profile, "loading": sync.loading, "error": sync.last_error,
                     "kids": sync.kids()},
            "favorites": sync.favorites,
            "progress": watch_store.lista,
            "downloads": downloads.lista(),
            "downloadsFolder": downloads.folder_label(),
            "freeSpace": S.human_size(downloads.free_space()),
            "prefs": {"langOrder": prefs.language_order(), "engine": prefs.engine(),
                      "peerflixUrl": prefs.peerflix_url(), "extraAddonUrl": prefs.extra_addon_url(),
                      "extraConfigured": motores.extra_configured(), "playerMode": prefs.player_mode(),
                      "downloadDir": str(prefs.download_dir()), "tmdbKey": tmdb.has_key(),
                      "tmdbFromEnv": bool(os.environ.get("TMDB_KEY")),
                      "bigText": bool(prefs.get("bigText", False))},
            "langs": [{"code": i.code, "label": i.label, "flag": i.flag} for i in lang.ALL],
            "vlc": self._vlc,
        }
        try:
            self._estado = json.dumps(st, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            log.exception("estado no serializable")
            return
        self.estadoChanged.emit()

    # ---------------------------------------------------------- pedidos
    @Slot(str, str, result=int)
    def pedir(self, tipo: str, args_json: str) -> int:
        rid = next(self._ids)
        try:
            args = json.loads(args_json or "{}")
        except ValueError:
            args = {}
        fn = getattr(self, "_p_" + tipo, None)
        if fn is None:
            self._despacha.emit({"id": rid, "tipo": tipo, "ok": False, "error": f"pedido desconocido: {tipo}",
                                 "fin": True})
            return rid

        def run():
            try:
                data = fn(args, lambda parcial: self._despacha.emit(
                    {"id": rid, "tipo": tipo, "ok": True, "data": parcial, "fin": False}))
                self._despacha.emit({"id": rid, "tipo": tipo, "ok": True, "data": data, "fin": True})
            except Exception as e:  # noqa: BLE001 - todo error acaba en la UI, no en la consola
                log.warning("pedido %s falló: %s\n%s", tipo, e, traceback.format_exc())
                self._despacha.emit({"id": rid, "tipo": tipo, "ok": False, "error": str(e) or e.__class__.__name__,
                                     "fin": True})
        self._pool.submit(run)
        return rid

    def _recibe(self, msg: dict) -> None:
        try:
            self.evento.emit(json.dumps(msg, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            log.exception("respuesta no serializable (%s)", msg.get("tipo"))

    # -------------------------------------------------------- ajustes
    @Slot(str, str)
    def ajustar(self, clave: str, valor_json: str) -> None:
        """Cambio de una preferencia (síncrono: solo escribe un JSON local)."""
        try:
            valor = json.loads(valor_json)
        except ValueError:
            valor = valor_json
        if clave == "langOrder":
            prefs.set_language_order(list(valor))
        elif clave in ("engine", "peerflixUrl", "extraAddonUrl", "playerMode", "downloadDir", "tmdbKey", "bigText"):
            prefs.set(clave, valor.strip() if isinstance(valor, str) else valor)
            if clave == "downloadDir":
                downloads.rescan()
        self._cambio.emit()

    @Slot(str)
    def abrirUrl(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    @Slot(str)
    def abrirCarpeta(self, ruta: str) -> None:
        p = Path(ruta)
        if p.is_file():
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            p.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    @Slot(str)
    def copiar(self, texto: str) -> None:
        QGuiApplication.clipboard().setText(texto)

    @Slot(result=str)
    def portapapeles(self) -> str:
        return QGuiApplication.clipboard().text()

    @Slot(str, result=str)
    def urlLocal(self, ruta: str) -> str:
        return QUrl.fromLocalFile(ruta).toString()

    @Slot(result=int)
    def descargasActivas(self) -> int:
        return downloads.active_count()

    @Slot(bool)
    def mantenerDespierto(self, si: bool) -> None:
        """Que Windows no apague la pantalla ni suspenda a mitad de película."""
        if sys.platform != "win32":
            return
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if si else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)

    def cerrar(self) -> None:
        downloads.pause_all()
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ============================================= pedidos (en hilo)
    # Cada _p_<tipo>(args, parcial) devuelve lo que llega a QML en `data`.

    def _p_catalogs(self, a, _):
        return tmdb.catalogs(a.get("type", "movie"), bool(a.get("kids")))

    def _p_discover(self, a, _):
        g = a.get("genre")
        return [t.to_dict() for t in tmdb.discover(a.get("type", "movie"), a.get("provider") or None,
                                                   int(g) if g not in (None, "") else None,
                                                   int(a.get("page", 1)), bool(a.get("kids")))]

    def _p_searchText(self, a, _):
        return [t.to_dict() for t in tmdb.search_text(a["query"].strip(), a.get("type", "movie"))]

    def _p_recs(self, a, _):
        tipo = a.get("type", "movie")
        seeds = watch_store.seeds(tipo) + [(f["tmdbId"], f["type"]) for f in sync.favorites if f["type"] == tipo]
        unicos, vistos = [], set()
        for s in seeds:
            if s[0] not in vistos:
                vistos.add(s[0])
                unicos.append(s)
        if not unicos:
            return []
        return [t.to_dict() for t in tmdb.recommendations(unicos[:6]) if t.type == tipo]

    def _p_detail(self, a, _):
        tipo, tid = a["type"], int(a["tmdbId"])
        futs = {
            "detail": self._aux.submit(tmdb.detail, tipo, tid),
            "imdb": self._aux.submit(tmdb.imdb_id, tipo, tid),
            "trailer": self._aux.submit(tmdb.trailer, tipo, tid),
        }
        out = {k: f.result() for k, f in futs.items() if k != "detail"}
        out["detail"] = futs["detail"].result()
        return out

    def _p_episodes(self, a, _):
        return tmdb.episodes(int(a["tmdbId"]), int(a["season"]))

    def _p_fuentes(self, a, parcial):
        err = fuentes.buscar(a.get("title", ""), a.get("type", "movie"), a.get("imdb"),
                             a.get("season"), a.get("episode"),
                             lambda lst, fin: parcial({"items": [r.to_dict() for r in lst], "fin": fin}))
        realdebrid.refresh_cached()
        return {"error": err}

    # ---- Real-Debrid
    def _p_rdStream(self, a, _):
        return realdebrid.stream_magnet(a["magnet"])

    def _p_rdPack(self, a, _):
        return realdebrid.pack_files(a["magnet"])

    def _p_rdUnrestrict(self, a, _):
        return realdebrid.unrestrict(a["link"])

    def _p_rdConnect(self, a, _):
        ok, msg = realdebrid.connect(a["token"])
        if ok and sync.signed_in():
            sync.save_account_rd_token(realdebrid.token)
            msg = f"Conectado como {msg} · vinculado a {sync.email}"
        elif ok:
            msg = f"Conectado como {msg}"
        return {"ok": ok, "msg": msg}

    def _p_rdDisconnect(self, a, _):
        realdebrid.disconnect()
        # También en la nube: si no, al arrancar se volvería a bajar
        sync.clear_account_rd_token()
        return {}

    def _p_rdInfo(self, a, _):
        realdebrid.refresh_info()
        return {}

    def _p_rdTorrents(self, a, _):
        downloads.rescan()
        if not realdebrid.configured():
            return []
        return realdebrid.torrents()

    def _p_rdFiles(self, a, _):
        return realdebrid.torrent_files(a["id"])

    def _p_rdDelete(self, a, _):
        err = realdebrid.delete_torrent(a["id"])
        rd_engine.invalidate()
        return {"error": err}

    def _p_addLink(self, a, _):
        """Pegado a mano en Descargas: un magnet va a la cuenta de RD; un enlace
        de hoster (1fichier, Mega…) se desbloquea y se descarga directamente."""
        v = links.tidy(a.get("text", ""))
        if v.lower().startswith("magnet:"):
            r = realdebrid.add_magnet(v)
            if r.get("id"):
                rd_engine.invalidate()
                return {"msg": "✅ Añadido (magnet). Real-Debrid lo está bajando a sus servidores; cuando ponga "
                               "«listo» ya se puede ver. Y a partir de ahora saldrá en la ficha del título, "
                               "en el buscador, como un enlace más.", "added": True}
            return {"error": r.get("error")}
        if links.looks_truncated(v):
            return {"error": "Parece que al enlace le falta el principio (el dominio). Cópialo entero otra vez."}
        if not v.lower().startswith("http"):
            return {"error": "Eso no parece ni un magnet ni un enlace."}
        r = realdebrid.unrestrict(v)
        if not r.get("url"):
            return {"error": r.get("error")}
        downloads.add(r["url"], r.get("filename") or "video")
        return {"msg": f"⬇ Descarga encolada: {r.get('filename') or ''}", "added": True}

    # ---- descargas
    def _p_dlAdd(self, a, _):
        return {"id": downloads.add(a["url"], a.get("name") or "video", a.get("magnet", ""))}

    def _p_dlPause(self, a, _):
        downloads.pause(a["id"])

    def _p_dlResume(self, a, _):
        downloads.resume(a["id"])

    def _p_dlRemove(self, a, _):
        downloads.remove(a["id"])

    def _p_dlRescan(self, a, _):
        downloads.rescan()

    # ---- cuenta
    def _p_signIn(self, a, _):
        ok, err = sync.sign_in_email(a.get("email", ""), a.get("password", ""))
        return {"ok": ok, "error": err}

    def _p_signUp(self, a, _):
        ok, err = sync.sign_up_email(a.get("email", ""), a.get("password", ""))
        return {"ok": ok, "error": err}

    def _p_resetPassword(self, a, _):
        ok, msg = sync.reset_password(a.get("email", ""))
        return {"ok": ok, "msg": msg}

    def _p_google(self, a, _):
        return google_login.iniciar()

    def _p_signOut(self, a, _):
        sync.sign_out()

    def _p_reload(self, a, _):
        sync.load_doc()

    def _p_profileSelect(self, a, _):
        sync.select_profile(a["id"])

    def _p_profileAdd(self, a, _):
        return {"error": sync.add_profile(a.get("name", ""), bool(a.get("kids")), a.get("avatar", ""))}

    def _p_profileUpdate(self, a, _):
        return {"error": sync.update_profile(a["id"], a.get("name", ""), bool(a.get("kids")), a.get("avatar", ""))}

    def _p_profileRemove(self, a, _):
        return {"error": sync.remove_profile(a["id"])}

    def _p_favToggle(self, a, _):
        return {"error": sync.toggle_favorite(a["title"])}

    def _p_alerts(self, a, _):
        return fuentes.episode_alerts(list(sync.favorites))

    # ---- reproducción
    def _p_progress(self, a, _):
        watch_store.record(int(a.get("tmdbId") or 0), a.get("type", "movie"), a.get("season"), a.get("episode"),
                           a.get("name", ""), a.get("poster"), float(a.get("position") or 0),
                           float(a.get("duration") or 0))

    def _p_nextEpisode(self, a, _):
        return fuentes.next_episode(int(a["tmdbId"]), int(a["season"]), int(a["episode"]),
                                    a.get("engine", ""), a.get("quality", ""), a.get("lang"))

    def _p_extraTest(self, a, _):
        return {"msg": motores.extra_test(a.get("url"))}

    def _p_subtitles(self, a, _):
        return _leer_subtitulos(a["path"])

    def _p_externalPlayer(self, a, _):
        """VLC con el enlace directo: se traga cualquier MKV con DTS o TrueHD. A
        cambio no guarda el «continuar viendo» ni pasa al siguiente episodio."""
        if not self._vlc:
            return {"error": "VLC no está instalado. Descárgalo de videolan.org o usa el reproductor de la app."}
        cmd = [self._vlc, a["url"], f"--meta-title={a.get('name') or 'VizPlay'}"]
        if a.get("resume"):
            cmd.append(f"--start-time={int(a['resume'])}")
        subprocess.Popen(cmd, close_fds=True)
        return {}


# ------------------------------------------------------ subtítulos externos
_TIEMPO = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})")


def _leer_subtitulos(ruta: str) -> dict:
    """SRT/VTT -> [{start, end, text}] en segundos. QtMultimedia no carga
    subtítulos externos, así que se pintan encima del vídeo desde QML."""
    p = Path(QUrl(ruta).toLocalFile() if ruta.startswith("file:") else ruta)
    crudo = p.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            txt = crudo.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    cues = []
    for bloque in re.split(r"\r?\n\r?\n", txt):
        lineas = [l for l in bloque.strip().splitlines() if l.strip()]
        idx = next((i for i, l in enumerate(lineas) if "-->" in l), -1)
        if idx < 0:
            continue
        t = _TIEMPO.findall(lineas[idx])
        if len(t) < 2:
            # VTT permite mm:ss.mmm sin horas
            t = [("0",) + m for m in re.findall(r"(\d{2}):(\d{2})[.](\d{3})", lineas[idx])]
            if len(t) < 2:
                continue
        def seg(m):
            h, mi, s, ms = m
            return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000
        texto = "\n".join(lineas[idx + 1:])
        texto = re.sub(r"<[^>]+>|\{[^}]+\}", "", texto)   # etiquetas HTML y de ASS
        cues.append({"start": seg(t[0]), "end": seg(t[1]), "text": texto})
    if not cues:
        raise ValueError("Ese fichero no parece un subtítulo SRT o VTT.")
    return {"cues": cues, "name": p.name}
