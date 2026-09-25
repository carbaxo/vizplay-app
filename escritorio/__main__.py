"""
VizPlay para escritorio (Windows): PySide6 + QML.

    .venv\\Scripts\\pythonw.exe -m escritorio        (lo lanza arrancar-escritorio.bat)

Arranque: registro a fichero (con pythonw nadie ve la consola), instancia única
(la segunda llama a la primera y se va), fuentes Inter, caché de carátulas en
disco y el motor QML. Si algo falla al arrancar, sale un aviso nativo de Windows
con la ruta del registro: sin él, con pythonw el fallo sería una ventana que
simplemente no aparece.
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

AQUI = Path(__file__).resolve().parent
NOMBRE_INSTANCIA = "VizPlay-escritorio"


def _registro() -> Path:
    from .nucleo import almacen
    ruta = almacen.ruta("vizplay.log")
    handlers: list[logging.Handler] = [RotatingFileHandler(ruta, maxBytes=1_000_000, backupCount=2, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return ruta


def _aviso_nativo(titulo: str, texto: str) -> None:
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x10)
    else:
        print(titulo, texto, file=sys.stderr)


def crea_app(unica: bool = True, nombre: str = "VizPlay"):
    """Crea la app y la ventana. Devuelve (app, motor, puente) o None si ya había
    otra instancia (a la que se le ha pedido que se muestre).

    `nombre` separa los ajustes de Qt (tamaño y posición de la ventana, volumen):
    captura.py usa otro para que su ventana fuera de pantalla no se quede
    guardada como la de la app de verdad."""
    from PySide6.QtCore import QCoreApplication, QStandardPaths, Qt, QtMsgType, qInstallMessageHandler
    from PySide6.QtGui import QFontDatabase, QGuiApplication, QIcon
    from PySide6.QtNetwork import QLocalServer, QLocalSocket, QNetworkAccessManager, QNetworkDiskCache
    from PySide6.QtQml import QQmlApplicationEngine, QQmlNetworkAccessManagerFactory
    from PySide6.QtQuickControls2 import QQuickStyle

    log = logging.getLogger("vizplay")

    # El estilo "Basic" ANTES de crear la app: el de Windows no deja cambiar
    # fondos ni contenidos, y aquí todo lleva el aspecto de la app de la tele.
    QQuickStyle.setStyle("Basic")
    QCoreApplication.setOrganizationName("carbaxo")
    QCoreApplication.setApplicationName(nombre)
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    app.setWindowIcon(QIcon(str(AQUI / "icono.png")))

    if unica:
        s = QLocalSocket()
        s.connectToServer(NOMBRE_INSTANCIA)
        if s.waitForConnected(300):
            s.write(b"mostrar")
            s.flush()
            s.waitForBytesWritten(300)
            s.disconnectFromServer()
            return None

    if sys.platform == "win32":
        # Que la barra de tareas no la agrupe con python.exe ni le ponga su icono
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("carbaxo.VizPlay.escritorio")

    def mensajes_qml(tipo, contexto, msg):
        nivel = {QtMsgType.QtDebugMsg: logging.DEBUG, QtMsgType.QtInfoMsg: logging.INFO,
                 QtMsgType.QtWarningMsg: logging.WARNING}.get(tipo, logging.ERROR)
        log.log(nivel, "qt: %s", msg)
    qInstallMessageHandler(mensajes_qml)

    for f in sorted((AQUI / "fuentes").glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(f))

    from .nucleo import downloads, prefs, realdebrid, sync, watch_store
    prefs.init()
    watch_store.init()
    realdebrid.init()
    downloads.init()
    sync.init()

    from .puente import Puente
    puente = Puente()

    # Caché de carátulas en disco: cada fila de Descubrir son ~20 imágenes, y sin
    # esto se volvían a bajar todas al cambiar de pestaña o reabrir la app.
    class Fabrica(QQmlNetworkAccessManagerFactory):
        def create(self, parent):
            nam = QNetworkAccessManager(parent)
            cache = QNetworkDiskCache(nam)
            carpeta = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)) / "imagenes"
            cache.setCacheDirectory(str(carpeta))
            cache.setMaximumCacheSize(300 * 1024 * 1024)
            nam.setCache(cache)
            return nam

    motor = QQmlApplicationEngine()
    motor._fabrica = Fabrica()          # que Python no la recoja: Qt no se queda la referencia
    motor.setNetworkAccessManagerFactory(motor._fabrica)
    motor.rootContext().setContextProperty("backend", puente)
    motor.addImportPath(str(AQUI / "qml"))
    motor.load(str(AQUI / "qml" / "VizPlay" / "Main.qml"))
    if not motor.rootObjects():
        raise RuntimeError("No se pudo cargar la interfaz (Main.qml). Mira el registro.")
    ventana = motor.rootObjects()[0]

    if unica:
        servidor = QLocalServer(app)
        QLocalServer.removeServer(NOMBRE_INSTANCIA)   # por si quedó uno huérfano de un cierre brusco
        servidor.listen(NOMBRE_INSTANCIA)

        def traer_al_frente():
            con = servidor.nextPendingConnection()
            if con:
                con.readyRead.connect(con.readAll)
            if ventana.visibility() == ventana.Visibility.Minimized:
                ventana.showNormal()
            ventana.raise_()
            ventana.requestActivate()
        servidor.newConnection.connect(traer_al_frente)
        app._servidor = servidor

    app.aboutToQuit.connect(puente.cerrar)
    return app, motor, puente


def main() -> int:
    ruta_log = _registro()
    try:
        r = crea_app()
        if r is None:
            return 0
        app = r[0]
        return app.exec()
    except Exception:  # noqa: BLE001
        logging.getLogger("vizplay").error("fallo al arrancar:\n%s", traceback.format_exc())
        _aviso_nativo("VizPlay no ha podido arrancar",
                      f"{traceback.format_exc(limit=3)}\n\nEl registro completo está en:\n{ruta_log}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
