"""
Dónde y cómo se guardan las cosas en el PC.

Todo va en %APPDATA%\\VizPlay (la carpeta de datos de usuario de Windows), que
es el equivalente a las SharedPreferences de Android. Lo sensible (el token de
Real-Debrid y la sesión de Firebase) va cifrado con **DPAPI**, el almacén de
Windows atado a TU usuario: otro usuario del mismo PC, o el mismo fichero
copiado a otra máquina, no lo puede leer. Es lo que en Android hace
EncryptedSharedPreferences.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()


def carpeta_datos() -> Path:
    """%APPDATA%\\VizPlay, o ~/.vizplay fuera de Windows. VIZPLAY_DATA lo cambia (tests)."""
    propia = os.environ.get("VIZPLAY_DATA")
    if propia:
        base = Path(propia)
    elif os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"]) / "VizPlay"
    else:
        base = Path.home() / ".vizplay"
    base.mkdir(parents=True, exist_ok=True)
    return base


def ruta(nombre: str) -> Path:
    return carpeta_datos() / nombre


def leer_json(nombre: str, defecto: Any) -> Any:
    try:
        with open(ruta(nombre), "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def guardar_json(nombre: str, datos: Any) -> None:
    """Escritura atómica: se escribe a un temporal y se renombra encima.

    Sin esto, cerrar la app a mitad de guardar (o que se vaya la luz) deja el
    fichero a medias y al arrancar se pierde TODO lo que había: el historial, la
    lista de descargas…
    """
    destino = ruta(nombre)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    with _lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=1)
        os.replace(tmp, destino)


# ---------------------------------------------------------------- DPAPI
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> _Blob:
        buf = ctypes.create_string_buffer(data, len(data))
        return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _cifrar(data: bytes) -> bytes:
        entrada, salida = _blob(data), _Blob()
        if not _crypt32.CryptProtectData(ctypes.byref(entrada), "VizPlay", None, None, None, 0,
                                         ctypes.byref(salida)):
            raise OSError("CryptProtectData falló")
        try:
            return ctypes.string_at(salida.pbData, salida.cbData)
        finally:
            _kernel32.LocalFree(salida.pbData)

    def _descifrar(data: bytes) -> bytes:
        entrada, salida = _blob(data), _Blob()
        if not _crypt32.CryptUnprotectData(ctypes.byref(entrada), None, None, None, None, 0,
                                           ctypes.byref(salida)):
            raise OSError("CryptUnprotectData falló")
        try:
            return ctypes.string_at(salida.pbData, salida.cbData)
        finally:
            _kernel32.LocalFree(salida.pbData)
else:  # pragma: no cover - solo para poder probar fuera de Windows
    def _cifrar(data: bytes) -> bytes:
        return data

    def _descifrar(data: bytes) -> bytes:
        return data

_SECRETOS = "secretos.bin"


def _leer_secretos() -> dict:
    try:
        crudo = ruta(_SECRETOS).read_bytes()
        return json.loads(_descifrar(base64.b64decode(crudo)).decode("utf-8"))
    except (OSError, ValueError):
        # Ilegible (otro usuario, otra máquina, fichero roto): se empieza de cero
        # en vez de romper el arranque. Solo se pierde lo que había que volver a
        # pegar: el token.
        return {}


def secreto(clave: str) -> str:
    return str(_leer_secretos().get(clave, "") or "")


def guardar_secreto(clave: str, valor: str) -> None:
    with _lock:
        datos = _leer_secretos()
        if valor:
            datos[clave] = valor
        else:
            datos.pop(clave, None)
        cifrado = base64.b64encode(_cifrar(json.dumps(datos).encode("utf-8")))
        destino = ruta(_SECRETOS)
        tmp = destino.with_suffix(".tmp")
        tmp.write_bytes(cifrado)
        os.replace(tmp, destino)
