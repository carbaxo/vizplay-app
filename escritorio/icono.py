r"""
Genera el icono de la app de escritorio a partir del MISMO dibujo que el de
Android (res/drawable/ic_launcher*.xml, que a su vez sale de
android-standalone/scripts/logo.py): la V blanca y rosa sobre el degradado
granate, recortado en círculo como lo enseña el launcher de Android.

    .venv\Scripts\python -m escritorio.icono

Escribe icono.png (ventana y barra de tareas) e icono.ico (accesos directos).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPolygonF

AQUI = Path(__file__).resolve().parent

# Geometría del icono adaptativo de Android, en su lienzo de 108 dp. El launcher
# solo enseña el círculo central de 72 dp (de 18 a 90): eso es lo que se pinta.
CLARO, OSCURO = "#D93650", "#5A0A18"
BRAZO_IZQ = [(30, 34), (54, 76), (54, 53.25), (43, 34)]
BRAZO_DER = [(78, 34), (54, 76), (54, 53.25), (65, 34)]
BLANCO, ROSA = "#FFFFFF", "#F2A7B3"
VISIBLE = (18, 90)


def pinta(tam: int) -> QImage:
    img = QImage(tam, tam, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    k = tam / (VISIBLE[1] - VISIBLE[0])
    p.scale(k, k)
    p.translate(-VISIBLE[0], -VISIBLE[0])

    circulo = QPainterPath()
    circulo.addEllipse(QPointF(54, 54), 36, 36)
    grad = QLinearGradient(0, 0, 108, 108)     # el degradado ocupa los 108 dp, como en Android
    grad.setColorAt(0, QColor(CLARO))
    grad.setColorAt(1, QColor(OSCURO))
    p.fillPath(circulo, grad)

    p.setPen(Qt.PenStyle.NoPen)
    for puntos, color in ((BRAZO_IZQ, BLANCO), (BRAZO_DER, ROSA)):
        p.setBrush(QColor(color))
        p.drawPolygon(QPolygonF([QPointF(x, y) for x, y in puntos]))
    p.end()
    return img


def _png(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def escribe_ico(ruta: Path, tamanos=(16, 24, 32, 48, 64, 128, 256)) -> None:
    """ICO con varias resoluciones, cada una en PNG (Windows Vista en adelante).
    Qt solo sabe escribir una por fichero, y Windows elige la que le toca."""
    imagenes = [_png(pinta(t)) for t in tamanos]
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    entradas, datos = b"", b""
    desplazamiento = 6 + 16 * len(imagenes)
    for t, png in zip(tamanos, imagenes):
        lado = 0 if t >= 256 else t          # 0 significa 256 en el formato ICO
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(png), desplazamiento + len(datos))
        datos += png
    ruta.write_bytes(cabecera + entradas + datos)


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)  # noqa: F841 - QPainter necesita la app
    pinta(256).save(str(AQUI / "icono.png"))
    escribe_ico(AQUI / "icono.ico")
    print("icono.png e icono.ico generados en", AQUI)
    return 0


if __name__ == "__main__":
    sys.exit(main())
