"""
Recorre las pantallas y guarda un PNG de cada una, para revisar la interfaz
sin ir pulsando a mano (patrón `app-escritorio-pyside6-qml` del cerebro).

    .venv\\Scripts\\python -m escritorio.captura [carpeta] [--ficha TIPO:TMDBID] [--video URL]

La ventana se abre fuera de la pantalla: la captura sale del render de Qt, no
del escritorio. Se deja ~1,5 s entre acciones porque la captura es del
fotograma siguiente y las carátulas llegan de la red.
"""
from __future__ import annotations

import faulthandler
import sys
import tempfile
from pathlib import Path


def main() -> int:
    args = [a for a in sys.argv[1:]]
    ficha = video = None
    demo = "--demo" in args
    if demo:
        args.remove("--demo")
    if "--ficha" in args:
        i = args.index("--ficha"); ficha = args[i + 1]; del args[i:i + 2]
    if "--video" in args:
        i = args.index("--video"); video = args[i + 1]; del args[i:i + 2]
    salida = Path(args[0]) if args else Path(tempfile.gettempdir()) / "vizplay-capturas"
    salida.mkdir(parents=True, exist_ok=True)
    faulthandler.dump_traceback_later(120, exit=True)

    from .__main__ import _registro, crea_app
    _registro()
    if demo:
        _modo_demo()
    sys.argv = ["vizplay"]
    app, motor, _ = crea_app(unica=False, nombre="VizPlay-captura")
    from PySide6.QtCore import QObject, QTimer
    ventana = motor.rootObjects()[0]
    ventana.setX(-4000)
    ventana.setY(40)
    ventana.setWidth(1400)
    ventana.setHeight(880)

    pasos: list[tuple[str, callable]] = [
        ("01-descubrir", lambda: None),
        ("02-buscar", lambda: ventana.setProperty("pagina", 1)),
        ("03-descargas", lambda: ventana.setProperty("pagina", 2)),
        ("04-ajustes", lambda: ventana.setProperty("pagina", 3)),
    ]
    if demo and not ficha:
        ficha = "movie:155"
    if ficha:
        tipo, tid = ficha.split(":")
        pasos.append(("05-ficha", lambda: (ventana.setProperty("pagina", 0), ventana.setProperty(
            "ficha", {"tmdbId": int(tid), "type": tipo, "title": "", "originalTitle": "", "year": "",
                      "poster": None, "rating": 0}))))
        pasos.append(("06-ficha-mas", lambda: None))
    if demo:
        pasos.append(("09-serie", lambda: (ventana.setProperty("ficha", None), ventana.setProperty(
            "ficha", {"tmdbId": 1396, "type": "series", "title": "Breaking Bad", "originalTitle": "Breaking Bad",
                      "year": "2008", "poster": None, "rating": 8.9}))))

        def abrir_episodio():
            from PySide6.QtCore import QMetaObject, Q_ARG, Qt
            f = ventana.findChild(QObject, "ficha")
            if f is None:
                return
            f.setProperty("abierto", 2)
            QMetaObject.invokeMethod(f, "buscar", Qt.DirectConnection, Q_ARG("QVariant", "Breaking Bad · T1E2"),
                                     Q_ARG("QVariant", 1), Q_ARG("QVariant", 2))
        pasos.append(("10-serie-episodio", abrir_episodio))
    if video:
        pasos.append(("07-reproductor", lambda: ventana.setProperty(
            "reproduciendo", {"url": video, "name": "Prueba de reproducción", "type": "movie", "tmdbId": -1,
                              "subtitle": "Vídeo de prueba"})))
        def controles():
            from PySide6.QtCore import QMetaObject, Qt
            r = ventana.findChild(QObject, "reproductor")
            if r is not None:
                QMetaObject.invokeMethod(r, "mostrarControles", Qt.DirectConnection)
        pasos.append(("08-reproductor-controles", controles))

    def siguiente(i=0):
        if i > 0:
            nombre = pasos[i - 1][0]
            img = ventana.grabWindow()
            img.save(str(salida / f"{nombre}.png"))
            print("captura", salida / f"{nombre}.png", flush=True)
        if i >= len(pasos):
            app.quit()
            return
        pasos[i][1]()
        espera = 9000 if pasos[i][0].startswith(("05", "07", "10")) else 3000
        QTimer.singleShot(espera if i else 4000, lambda: siguiente(i + 1))

    QTimer.singleShot(100, siguiente)
    return app.exec()


def _modo_demo() -> None:
    """TMDB de mentira: unos pocos títulos reales (con sus IMDb id de verdad,
    para que los buscadores devuelvan enlaces reales) y sus carátulas del CDN
    público de TMDB, que no pide clave."""
    from .nucleo import tmdb
    img = "https://image.tmdb.org/t/p/w342"
    pelis = [
        tmdb.Title(155, "El caballero oscuro", "The Dark Knight", "2008", img + "/qJ2tW6WMUDux911r6m7haRef0WH.jpg", 8.5, "movie"),
        tmdb.Title(27205, "Origen", "Inception", "2010", img + "/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg", 8.4, "movie"),
        tmdb.Title(157336, "Interstellar", "Interstellar", "2014", img + "/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg", 8.4, "movie"),
        tmdb.Title(603, "Matrix", "The Matrix", "1999", img + "/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg", 8.2, "movie"),
        tmdb.Title(680, "Pulp Fiction", "Pulp Fiction", "1994", img + "/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg", 8.5, "movie"),
        tmdb.Title(13, "Forrest Gump", "Forrest Gump", "1994", img + "/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg", 8.5, "movie"),
        tmdb.Title(550, "El club de la lucha", "Fight Club", "1999", img + "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg", 8.4, "movie"),
        tmdb.Title(120, "El Señor de los Anillos: La Comunidad del Anillo", "The Lord of the Rings", "2001",
                   img + "/6oom5QYQ2yQTMJIbnvbkBL9cHo6.jpg", 8.4, "movie"),
        tmdb.Title(238, "El padrino", "The Godfather", "1972", img + "/3bhkrj58Vtu7enYsRolD1fZdja1.jpg", 8.7, "movie"),
        tmdb.Title(424, "La lista de Schindler", "Schindler's List", "1993", img + "/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg", 8.6, "movie"),
    ]
    imdbs = {155: "tt0468569", 27205: "tt1375666", 157336: "tt0816692", 603: "tt0133093", 1396: "tt0903747"}
    tmdb.has_key = lambda: True
    tmdb.catalogs = lambda tipo, kids=False: [
        {"name": n, "provider": p, "items": [t.to_dict() for t in (pelis[i:] + pelis[:i])]}
        for i, (n, p) in enumerate([("Netflix", "8"), ("Prime Video", "9|119"), ("HBO Max", "384"), ("Disney+", "337")])]
    tmdb.recommendations = lambda seeds: pelis[3:9]
    tmdb.discover = lambda *a, **k: pelis
    tmdb.search_text = lambda q, t: pelis[:4]
    tmdb.imdb_id = lambda tipo, i: imdbs.get(int(i))
    tmdb.trailer = lambda tipo, i: "EXeTwQWrcwY"
    tmdb.last_episode = lambda i: None

    def detalle(tipo, i):
        if tipo == "series":
            return {"tmdbId": 1396, "type": "series", "title": "Breaking Bad", "originalTitle": "Breaking Bad",
                    "year": "2008", "overview": "Un profesor de química con cáncer terminal se asocia con un antiguo "
                    "alumno para fabricar y vender metanfetamina y asegurar el futuro de su familia.",
                    "backdrop": "https://image.tmdb.org/t/p/w1280/tsRy63Mu5cu8etL1X7ZLyf7UP1M.jpg",
                    "poster": img + "/ggFHVNu6YYI5L9pCfOacjizRGt.jpg", "rating": 8.9,
                    "genres": ["Drama", "Crimen"], "runtime": 0,
                    "seasons": [{"season": n, "name": f"Temporada {n}", "episodes": e}
                                for n, e in [(1, 7), (2, 13), (3, 13), (4, 13), (5, 16)]]}
        t = next(p for p in pelis if p.tmdbId == int(i))
        return {"tmdbId": t.tmdbId, "type": "movie", "title": t.title, "originalTitle": t.originalTitle,
                "year": t.year, "overview": "Batman se enfrenta al Joker, un criminal que siembra el caos en Gotham "
                "y pone a prueba todo aquello en lo que cree el caballero oscuro.",
                "backdrop": "https://image.tmdb.org/t/p/w1280/nMKdUUepR0i5zn0y1T4CsSB5chy.jpg",
                "poster": t.poster, "rating": t.rating, "genres": ["Drama", "Acción", "Crimen"], "runtime": 152,
                "seasons": []}
    tmdb.detail = detalle
    tmdb.episodes = lambda i, s: [
        {"episode": n, "name": nombre, "overview": "Walter White empieza una nueva vida al margen de la ley.",
         "still": None, "runtime": 47, "airDate": ""}
        for n, nombre in enumerate(["Piloto", "El gato está en la bolsa…", "…y la bolsa en el río", "Hombre con cáncer",
                                    "Materia gris", "Un puñado de nada", "Un acuerdo sin rodeos"], start=1)]


if __name__ == "__main__":
    sys.exit(main())
