"""
Sincronización con la MISMA cuenta que Android y la web (Firebase Auth) y el
MISMO documento de Firestore. Port de `Sync.kt`.

    users/{uid} = {
      profiles: [{ id, name, kids, avatar }],
      states:   { [profileId]: { favorites: [...], progress: [...], settings: {} } },
      account:  { rdToken }
    }

En el PC no hay SDK de Firebase para Python que valga para esto (el Admin SDK
salta las reglas y necesita credenciales de servicio), así que se habla con las
**API REST** de Firebase como un cliente más, con el token del usuario: las
reglas de `firestore.rules` se aplican igual que en el móvil.

Las escrituras son siempre PARCIALES (`updateMask`), el equivalente al
`SetOptions.merge()` de Android: tocar los favoritos de un perfil no pisa el
progreso de otro ni lo que haya escrito la web a la vez.
"""
from __future__ import annotations

import json
import re
import threading
import time
import uuid
from typing import Callable

import requests

from . import almacen, lang, prefs, realdebrid, watch_store
from .red import sesion

API_KEY = "AIzaSyAOxy_O6R2BsYWNTe89njyzuIg3_O7weHY"   # no es secreta: identifica el proyecto
PROJECT = "torrent-7dd4b"
FIREBASE_CONFIG = {
    "apiKey": API_KEY,
    "authDomain": f"{PROJECT}.firebaseapp.com",
    "projectId": PROJECT,
    "appId": "1:457371422941:web:f91a3dab9fadb03d834b34",
}
_AUTH = "https://identitytoolkit.googleapis.com/v1/accounts"
_TOKEN = "https://securetoken.googleapis.com/v1/token"
_DOCS = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"

MIN_PASS = 6
MAX_PROFILES = 5

email: str | None = None
uid: str | None = None
profiles: list[dict] = []
active_profile: dict | None = None
favorites: list[dict] = []
loading = False
last_error = ""

_id_token = ""
_refresh = ""
_expira = 0.0
_doc: dict = {}
_lock = threading.RLock()
_oyentes: list[Callable[[], None]] = []


class ErrorSync(RuntimeError):
    pass


def al_cambiar(fn: Callable[[], None]) -> None:
    _oyentes.append(fn)


def _avisar() -> None:
    for fn in list(_oyentes):
        fn()


def enabled() -> bool:
    return True


def signed_in() -> bool:
    return bool(uid and _refresh)


def kids() -> bool:
    return bool(active_profile and active_profile.get("kids"))


# ------------------------------------------------------------------ sesión
def init() -> None:
    """Recupera la sesión guardada (el refresh token, cifrado) y lee la nube."""
    global _refresh, uid, email
    try:
        s = json.loads(almacen.secreto("firebase") or "{}")
    except ValueError:
        s = {}
    if s.get("refresh") and s.get("uid"):
        _refresh, uid, email = s["refresh"], s["uid"], s.get("email")
        threading.Thread(target=load_doc, daemon=True).start()


def _guardar_sesion() -> None:
    almacen.guardar_secreto("firebase", json.dumps({"refresh": _refresh, "uid": uid, "email": email})
                            if _refresh else "")


def _auth_error(code: str) -> str:
    """Los fallos de Firebase Auth, en castellano. El más probable la primera
    vez es el método sin activar: merece su propio mensaje."""
    c = code.split(":")[0].strip().upper()
    return {
        "OPERATION_NOT_ALLOWED": "Falta activar «Email/contraseña» en Firebase Console → Authentication → "
                                 "Sign-in method (Métodos de acceso).",
        "CONFIGURATION_NOT_FOUND": "Falta activar «Email/contraseña» en Firebase Console → Authentication → "
                                   "Sign-in method (Métodos de acceso).",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Demasiados intentos. Espera un rato antes de volver a probar.",
        "WEAK_PASSWORD": f"La contraseña es demasiado corta (mínimo {MIN_PASS} caracteres).",
        "EMAIL_EXISTS": "Ya existe una cuenta con ese email. Pulsa «Entrar».",
        "EMAIL_NOT_FOUND": "No hay ninguna cuenta con ese email. Pulsa «Crear cuenta».",
        # Con la protección de enumeración, Firebase contesta lo mismo para
        # email inexistente y contraseña mala: no se puede distinguir.
        "INVALID_PASSWORD": "Email o contraseña incorrectos.",
        "INVALID_LOGIN_CREDENTIALS": "Email o contraseña incorrectos.",
        "INVALID_EMAIL": "Escribe un email válido.",
        "USER_DISABLED": "Esta cuenta está desactivada.",
        "TOKEN_EXPIRED": "La sesión ha caducado: vuelve a entrar.",
        "INVALID_REFRESH_TOKEN": "La sesión ha caducado: vuelve a entrar.",
        "USER_NOT_FOUND": "La cuenta ya no existe.",
    }.get(c, code or "No se pudo iniciar sesión.")


def _post_auth(url: str, body: dict) -> dict:
    try:
        r = sesion.post(url, params={"key": API_KEY}, json=body, timeout=(10, 20))
    except requests.RequestException as e:
        raise ErrorSync("Sin conexión: no se pudo hablar con Firebase.") from e
    try:
        d = r.json()
    except ValueError:
        d = {}
    if not r.ok:
        raise ErrorSync(_auth_error(((d.get("error") or {}).get("message")) or f"HTTP {r.status_code}"))
    return d


def _check_creds(mail: str, password: str) -> str | None:
    if not mail.strip() or "@" not in mail:
        return "Escribe un email válido."
    if len(password) < MIN_PASS:
        return f"La contraseña necesita al menos {MIN_PASS} caracteres."
    return None


def _adoptar_sesion(id_token: str, refresh: str, user_id: str, mail: str | None, expira_en: float = 3600) -> None:
    global _id_token, _refresh, _expira, uid, email
    _id_token, _refresh, uid, email = id_token, refresh, user_id, mail
    _expira = time.time() + float(expira_en) - 120
    _guardar_sesion()
    _avisar()


def sign_in_email(mail: str, password: str) -> tuple[bool, str | None]:
    err = _check_creds(mail, password)
    if err:
        return False, err
    try:
        d = _post_auth(f"{_AUTH}:signInWithPassword",
                       {"email": mail.strip(), "password": password, "returnSecureToken": True})
    except ErrorSync as e:
        return False, str(e)
    _adoptar_sesion(d["idToken"], d["refreshToken"], d["localId"], d.get("email"), d.get("expiresIn", 3600))
    load_doc()
    return True, None


def sign_up_email(mail: str, password: str) -> tuple[bool, str | None]:
    """Crea la cuenta y entra, con un perfil "Principal" para que la app sea
    usable desde el primer momento (una cuenta nueva no trae ninguno)."""
    err = _check_creds(mail, password)
    if err:
        return False, err
    try:
        d = _post_auth(f"{_AUTH}:signUp", {"email": mail.strip(), "password": password, "returnSecureToken": True})
    except ErrorSync as e:
        return False, str(e)
    _adoptar_sesion(d["idToken"], d["refreshToken"], d["localId"], d.get("email"), d.get("expiresIn", 3600))
    p = {"id": str(uuid.uuid4()), "name": "Principal", "avatar": "🍿", "kids": False}
    try:
        _write_profiles([p])
    except ErrorSync:
        pass
    load_doc()
    return True, None


def reset_password(mail: str) -> tuple[bool, str]:
    m = mail.strip()
    if not m or "@" not in m:
        return False, "Escribe tu email primero."
    try:
        _post_auth(f"{_AUTH}:sendOobCode", {"requestType": "PASSWORD_RESET", "email": m})
    except ErrorSync as e:
        return False, str(e)
    return True, f"Te hemos enviado un correo a {m} para cambiar la contraseña."


def sign_in_with_tokens(id_token: str, refresh: str, user_id: str, mail: str | None) -> None:
    """Lo que devuelve el login con Google del navegador (ver google_login.py)."""
    _adoptar_sesion(id_token, refresh, user_id, mail)
    load_doc()


def sign_out() -> None:
    global _id_token, _refresh, uid, email, active_profile, _doc
    _id_token, _refresh, uid, email = "", "", None, None
    profiles.clear()
    favorites.clear()
    active_profile, _doc = None, {}
    _guardar_sesion()
    # El token de RD es de la CUENTA, no del aparato: si se quedara, la
    # siguiente cuenta que entrara en este PC heredaría el Real-Debrid.
    realdebrid.disconnect()
    _avisar()


def _token() -> str:
    """ID token vigente (dura una hora); se renueva con el refresh token."""
    global _id_token, _refresh, _expira
    with _lock:
        if _id_token and time.time() < _expira:
            return _id_token
        if not _refresh:
            raise ErrorSync("Inicia sesión primero.")
        try:
            r = sesion.post(_TOKEN, params={"key": API_KEY}, timeout=(10, 20),
                            data={"grant_type": "refresh_token", "refresh_token": _refresh})
        except requests.RequestException as e:
            raise ErrorSync("Sin conexión: no se pudo hablar con Firebase.") from e
        d = r.json() if r.content else {}
        if not r.ok:
            msg = _auth_error(((d.get("error") or {}).get("message")) or "")
            if r.status_code in (400, 401):
                # Sesión revocada o caducada de verdad: se cierra aquí también
                threading.Thread(target=sign_out, daemon=True).start()
            raise ErrorSync(msg)
        _id_token, _refresh = d["id_token"], d.get("refresh_token", _refresh)
        _expira = time.time() + float(d.get("expires_in", 3600)) - 120
        _guardar_sesion()
        return _id_token


# ---------------------------------------------------- Firestore (REST)
def _dec(v: dict):
    """Valor tipado de Firestore -> Python."""
    if "stringValue" in v:
        return v["stringValue"]
    if "integerValue" in v:
        return int(v["integerValue"])
    if "doubleValue" in v:
        return float(v["doubleValue"])
    if "booleanValue" in v:
        return bool(v["booleanValue"])
    if "nullValue" in v:
        return None
    if "mapValue" in v:
        return {k: _dec(x) for k, x in (v["mapValue"].get("fields") or {}).items()}
    if "arrayValue" in v:
        return [_dec(x) for x in (v["arrayValue"].get("values") or [])]
    if "timestampValue" in v:
        return v["timestampValue"]
    return None


def _enc(v) -> dict:
    """Python -> valor tipado de Firestore (bool antes que int: es su subclase)."""
    if v is None:
        return {"nullValue": None}
    if isinstance(v, bool):
        return {"booleanValue": v}
    if isinstance(v, int):
        return {"integerValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, str):
        return {"stringValue": v}
    if isinstance(v, dict):
        return {"mapValue": {"fields": {str(k): _enc(x) for k, x in v.items()}}}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [_enc(x) for x in v]}}
    return {"stringValue": str(v)}


_SIMPLE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


def _campo(ruta: list[str]) -> str:
    """Ruta de campo de Firestore: los tramos raros (los id de perfil llevan
    guiones) van entre comillas invertidas."""
    return ".".join(s if _SIMPLE.match(s) else "`" + s.replace("\\", "\\\\").replace("`", "\\`") + "`"
                    for s in ruta)


def _doc_url() -> str:
    if not uid:
        raise ErrorSync("Inicia sesión primero.")
    return f"{_DOCS}/users/{uid}"


def _patch(cambios: list[tuple[list[str], object]]) -> None:
    """Escribe SOLO esas rutas (merge). Siempre añade updatedAt, como Android."""
    cambios = list(cambios) + [(["updatedAt"], watch_store.iso())]
    campos: dict = {}
    for ruta, valor in cambios:
        nodo = campos
        for s in ruta[:-1]:
            nodo = nodo.setdefault(s, {})
        nodo[ruta[-1]] = valor
    params = [("updateMask.fieldPaths", _campo(r)) for r, _ in cambios]
    try:
        r = sesion.patch(_doc_url(), params=params, timeout=(10, 20),
                         headers={"Authorization": f"Bearer {_token()}"},
                         json={"fields": {k: _enc(v) for k, v in campos.items()}})
    except requests.RequestException as e:
        raise ErrorSync("Sin conexión con Firestore.") from e
    if not r.ok:
        raise ErrorSync(f"Firestore respondió {r.status_code}.")
    # La copia local, al día: si no, cambiar de perfil después leería datos viejos
    with _lock:
        for ruta, valor in cambios:
            nodo = _doc
            for s in ruta[:-1]:
                if not isinstance(nodo.get(s), dict):
                    nodo[s] = {}
                nodo = nodo[s]
            nodo[ruta[-1]] = valor


def _patch_async(cambios) -> None:
    """Las escrituras "de fondo" (progreso, idioma) no deben frenar la UI."""
    def run():
        global last_error
        try:
            _patch(cambios)
        except ErrorSync as e:
            last_error = str(e)
    threading.Thread(target=run, daemon=True).start()


def load_doc() -> None:
    """Lee el documento entero (perfiles + estados + cuenta)."""
    global loading, _doc, last_error
    if not uid:
        return
    loading = True
    _avisar()
    try:
        r = sesion.get(_doc_url(), headers={"Authorization": f"Bearer {_token()}"}, timeout=(10, 20))
        if r.status_code == 404:
            data = {}
        elif not r.ok:
            raise ErrorSync(f"Firestore respondió {r.status_code}.")
        else:
            data = {k: _dec(v) for k, v in (r.json().get("fields") or {}).items()}
    except (ErrorSync, requests.RequestException, ValueError) as e:
        last_error = str(e)
        loading = False
        _avisar()
        return
    last_error = ""
    with _lock:
        _doc = data
        profiles[:] = [
            {"id": str(p["id"]), "name": str(p.get("name") or "Perfil"),
             "avatar": str(p.get("avatar") or "🍿"), "kids": p.get("kids") is True}
            for p in (data.get("profiles") or []) if isinstance(p, dict) and p.get("id")
        ]
    loading = False
    if profiles:
        last = prefs.get("lastProfile")
        pick = next((p for p in profiles if p["id"] == last), profiles[0])
        select_profile(pick["id"])
    # El token de RD va con la cuenta: si la cuenta trae uno, manda; si no tiene
    # y este PC sí, se sube para vincularlo. Si la clave existe VACÍA fue una
    # desconexión hecha en otro aparato: no se resube, que la desharía.
    account = data.get("account") if isinstance(data.get("account"), dict) else {}
    rd = str(account.get("rdToken") or "").strip()
    if rd:
        realdebrid.adopt_token(rd)
    elif "rdToken" not in account and realdebrid.configured():
        save_account_rd_token(realdebrid.token)
    _avisar()


def select_profile(pid: str) -> None:
    """Adopta el estado (favoritos, progreso, idioma) de un perfil."""
    global active_profile
    p = next((x for x in profiles if x["id"] == pid), None)
    if not p:
        return
    active_profile = p
    prefs.set("lastProfile", pid)
    with _lock:
        state = ((_doc.get("states") or {}).get(pid) or {}) if isinstance(_doc.get("states"), dict) else {}
    out = []
    for f in state.get("favorites") or []:
        fid = str(f.get("id") or "")
        if not fid:
            continue
        m = re.search(r"(\d+)", fid)
        poster = f.get("poster")
        out.append({
            "id": fid, "tmdbId": int(m.group(1)) if m else 0, "title": str(f.get("title") or ""),
            "year": str(f.get("year") or ""), "poster": poster if poster and poster != "null" else None,
            "type": "series" if f.get("type") == "series" else "movie",
            "rating": float(f.get("rating") or 0), "originalTitle": str(f.get("title") or ""),
        })
    favorites[:] = out
    watch_store.load_from_maps(state.get("progress") or [])
    # El idioma del perfil (settings.language) manda en el orden local
    cloud = lang.from_tmdb(((state.get("settings") or {}).get("language")))
    if cloud:
        resto = [c for c in prefs.language_order() if c != cloud]
        prefs.set_language_order([cloud] + resto, subir=False)
    _avisar()


def is_fav(fid: str) -> bool:
    return any(f["id"] == fid for f in favorites)


# --------------------------------------------------------------- perfiles
def _write_profiles(lst: list[dict]) -> None:
    _patch([(["profiles"], [{"id": p["id"], "name": p["name"], "avatar": p["avatar"], "kids": p["kids"]}
                            for p in lst])])


def add_profile(name: str, kids_: bool, avatar: str) -> str | None:
    if not signed_in():
        return "Inicia sesión primero"
    if len(profiles) >= MAX_PROFILES:
        return f"Máximo {MAX_PROFILES} perfiles"
    nm = name.strip()[:24]
    if not nm:
        return "Escribe un nombre"
    p = {"id": str(uuid.uuid4()), "name": nm, "avatar": avatar.strip() or ("🧒" if kids_ else "🍿"), "kids": kids_}
    try:
        _write_profiles(profiles + [p])
    except ErrorSync as e:
        return str(e)
    profiles.append(p)
    if not active_profile:
        select_profile(p["id"])
    _avisar()
    return None


def update_profile(pid: str, name: str, kids_: bool, avatar: str) -> str | None:
    if not signed_in():
        return "Inicia sesión primero"
    idx = next((i for i, p in enumerate(profiles) if p["id"] == pid), -1)
    if idx < 0:
        return "Perfil no encontrado"
    nm = name.strip()[:24]
    if not nm:
        return "Escribe un nombre"
    nuevo = dict(profiles[idx], name=nm, kids=kids_, avatar=avatar.strip() or ("🧒" if kids_ else "🍿"))
    lst = list(profiles)
    lst[idx] = nuevo
    try:
        _write_profiles(lst)
    except ErrorSync as e:
        return str(e)
    global active_profile
    profiles[idx] = nuevo
    if active_profile and active_profile["id"] == pid:
        active_profile = nuevo
    _avisar()
    return None


def remove_profile(pid: str) -> str | None:
    if not signed_in():
        return "Inicia sesión primero"
    if len(profiles) <= 1:
        return "Debe quedar al menos un perfil"
    lst = [p for p in profiles if p["id"] != pid]
    try:
        _write_profiles(lst)
    except ErrorSync as e:
        return str(e)
    profiles[:] = lst
    if active_profile and active_profile["id"] == pid:
        select_profile(profiles[0]["id"])
    _avisar()
    return None


# ------------------------------------------------ favoritos y progreso
def toggle_favorite(t: dict) -> str | None:
    """Añade/quita de Mi lista en el perfil activo (merge por perfil)."""
    if not signed_in() or not active_profile:
        return "Inicia sesión para usar Mi lista."
    fid = f"tmdb:{t['tmdbId']}"
    if is_fav(fid):
        favorites[:] = [f for f in favorites if f["id"] != fid]
    else:
        favorites.insert(0, {"id": fid, "tmdbId": t["tmdbId"], "title": t.get("title", ""),
                             "year": t.get("year", ""), "poster": t.get("poster"),
                             "type": t.get("type", "movie"), "rating": float(t.get("rating") or 0),
                             "originalTitle": t.get("originalTitle") or t.get("title", "")})
    _avisar()
    arr = [{"id": f["id"], "title": f["title"], "year": f["year"], "poster": f["poster"],
            "type": f["type"], "rating": f["rating"], "addedAt": watch_store.iso()} for f in favorites]
    try:
        _patch([(["states", active_profile["id"], "favorites"], arr)])
    except ErrorSync as e:
        return str(e)
    return None


def save_progress_cloud(progress: list[dict]) -> None:
    if signed_in() and active_profile:
        _patch_async([(["states", active_profile["id"], "progress"], progress)])


def save_account_rd_token(tok: str) -> None:
    """El token de RD va con la cuenta, compartido entre dispositivos."""
    if signed_in():
        _patch_async([(["account", "rdToken"], tok)])


def clear_account_rd_token() -> None:
    """Desvincula RD de la cuenta: si solo se borrara aquí, el siguiente
    arranque lo volvería a bajar de la nube."""
    save_account_rd_token("")


def save_settings_language(tmdb_lang: str) -> None:
    if signed_in() and active_profile:
        _patch_async([(["states", active_profile["id"], "settings", "language"], tmdb_lang)])
