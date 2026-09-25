"""
«Entrar con Google» en el PC.

En Android lo resuelve Google Play Services; aquí no hay nada parecido, y el
flujo OAuth de escritorio pediría un cliente OAuth nuevo con su secreto. Se hace
como la app de Electron, que ya funciona: **el propio Firebase de la web**
(`signInWithPopup`) en una página servida desde `http://localhost`, que es un
dominio que Firebase ya tiene autorizado.

    1. Se levanta un servidor HTTP mínimo en localhost:<puerto libre>.
    2. Se abre el navegador del sistema en esa página: el usuario pulsa el botón y
       elige su cuenta de Google en la ventana de siempre (con su sesión de Google
       ya abierta, sin teclear nada).
    3. La página devuelve al servidor el ID token y el refresh token de Firebase,
       y a partir de ahí la app los usa por REST igual que con email/contraseña.

El servidor solo escucha en 127.0.0.1, solo acepta el POST con el `nonce` que
lleva la página que él mismo ha servido, y se apaga al terminar.
"""
from __future__ import annotations

import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import sync

_WEB = Path(__file__).resolve().parent.parent / "login"
_TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8"}


def iniciar(timeout: float = 300) -> dict:
    """Bloquea hasta que el usuario termina en el navegador (o hasta timeout).
    Devuelve {ok: True, email} o {error}."""
    nonce = secrets.token_urlsafe(24)
    hecho = threading.Event()
    resultado: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # sin ruido en la consola
            pass

        def _enviar(self, code: int, body: bytes, tipo: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path in ("/", "/index.html"):
                html = (_WEB / "index.html").read_text(encoding="utf-8")
                html = html.replace("__CONFIG__", json.dumps(sync.FIREBASE_CONFIG)).replace("__NONCE__", nonce)
                return self._enviar(200, html.encode("utf-8"), _TIPOS[".html"])
            f = (_WEB / path.lstrip("/")).resolve()
            if f.is_file() and _WEB in f.parents and f.suffix in _TIPOS:
                return self._enviar(200, f.read_bytes(), _TIPOS[f.suffix])
            self._enviar(404, b"no", "text/plain")

        def do_POST(self):
            if self.path != "/hecho":
                return self._enviar(404, b"no", "text/plain")
            try:
                n = int(self.headers.get("Content-Length") or 0)
                d = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
            except ValueError:
                return self._enviar(400, b"{}", "application/json")
            if d.get("nonce") != nonce:
                return self._enviar(403, b"{}", "application/json")
            if d.get("error"):
                resultado["error"] = str(d["error"])
            elif d.get("idToken") and d.get("refreshToken") and d.get("uid"):
                resultado.update(d)
            else:
                resultado["error"] = "Google no devolvió la sesión."
            self._enviar(200, b'{"ok":true}', "application/json")
            hecho.set()

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    puerto = srv.server_address[1]
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    try:
        # "localhost" y no 127.0.0.1: es el dominio que Firebase tiene autorizado
        webbrowser.open(f"http://localhost:{puerto}/")
        if not hecho.wait(timeout):
            return {"error": "Se acabó el tiempo sin terminar el inicio de sesión en el navegador."}
    finally:
        srv.shutdown()
        srv.server_close()
    if resultado.get("error"):
        return {"error": resultado["error"]}
    sync.sign_in_with_tokens(resultado["idToken"], resultado["refreshToken"], resultado["uid"],
                             resultado.get("email"))
    return {"ok": True, "email": resultado.get("email")}
