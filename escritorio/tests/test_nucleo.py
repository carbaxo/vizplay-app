"""
Pruebas del núcleo, sin red. Los casos de episode_fit son los nombres REALES
con los que se comprobó en Android (comentario de `Search.episodeFit`).

    .venv\\Scripts\\python -m unittest discover -s escritorio/tests
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ["VIZPLAY_DATA"] = tempfile.mkdtemp(prefix="vizplay-test-")

from escritorio.nucleo import almacen, lang, links, motores, prefs, sync, watch_store  # noqa: E402
from escritorio.nucleo import search as S  # noqa: E402

prefs.init()


class EpisodeFit(unittest.TestCase):
    CASOS = [
        ("Padre De Familia Temp.11 [Cap.1101]", 11, 1, S.Fit.OK),
        ("Padre De Familia Temp.11 [Cap.1101]", 9, 1, S.Fit.NO),
        ("Peppa.Pig.S05E31", 5, 31, S.Fit.OK),
        ("Peppa.Pig.S05E31", 5, 30, S.Fit.NO),
        ("Peppa.Pig.1.Temporada.1x01.al.1x13", 1, 7, S.Fit.PACK),
        ("Peppa.Pig.1.Temporada.1x01.al.1x13", 2, 7, S.Fit.NO),
        ("Family Guy Seasons 1 to 17 Complete", 5, 3, S.Fit.PACK),
        ("Family Guy - 101 - Death Has A Shadow", 1, 1, S.Fit.OK),
        ("Bluey Temporada 1 [Cap.104_106]", 1, 5, S.Fit.PACK),
        ("Bluey Temporada 1 [Cap.104_106]", 1, 1, S.Fit.NO),
        ("Oliver y Benji Campeones 3 Temporada", 3, 4, S.Fit.PACK),
        ("Oliver y Benji Campeones 3 Temporada", 1, 4, S.Fit.NO),
    ]

    def test_casos_reales(self):
        for name, s, e, esperado in self.CASOS:
            with self.subTest(name=name, s=s, e=e):
                self.assertEqual(S.episode_fit(name, s, e), esperado)


class Idioma(unittest.TestCase):
    def test_bandera_espanola_gana(self):
        self.assertEqual(lang.detect_from_title("Torrentio 🇪🇸 🇬🇧 1080p"), "es-ES")

    def test_varias_banderas_sin_espana_es_multi(self):
        self.assertEqual(lang.detect_from_title("🇲🇽 🇺🇸"), "multi")

    def test_castellano_antes_que_dual(self):
        self.assertEqual(lang.detect("Oliver y Benji Dual Castellano Japonés"), "es-ES")

    def test_cast_no_casa_con_podcast(self):
        self.assertIsNone(lang.detect("The.Podcast.Castle.2019.mkv"))
        self.assertEqual(lang.detect("Pelicula.[CAST].1080p.mkv"), "es-ES")

    def test_rank(self):
        order = ["es-ES", "en"]
        self.assertLess(lang.rank("es-ES", order), lang.rank("en", order))
        self.assertLess(lang.rank("multi", order), lang.rank(None, order))


class Calidad(unittest.TestCase):
    def test_formas_espanolas(self):
        self.assertEqual(S.quality("Pelicula [MicroHD][1080 px]"), "1080p")
        self.assertEqual(S.quality("serie 1920x1080 x264"), "1080p")
        self.assertEqual(S.quality("Peli.2160p.HDR"), "4K")
        self.assertEqual(S.quality("cap.HDTV.avi"), "720p")
        self.assertEqual(S.quality("algo raro"), "Unknown")


class Utilidades(unittest.TestCase):
    def test_orden_natural(self):
        nombres = ["04x10.avi", "04x2.avi", "04x1.avi"]
        self.assertEqual(sorted(nombres, key=S.natural_key), ["04x1.avi", "04x2.avi", "04x10.avi"])

    def test_merge_une_motores(self):
        a = S.Result("A", "h", 5, 0, "m", engine="peerflix")
        b = S.Result("A.2020.1080p.mkv", "h", 9, 100, "m", engine="torrentio", quality="1080p")
        r = S.merge_results([a, b])
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].engine, "peerflix+torrentio")
        self.assertEqual(r[0].name, "A.2020.1080p.mkv")
        self.assertEqual(r[0].seeders, 9)

    def test_orden_motor(self):
        rs = [S.Result("t", "1", 99, 0, "", engine="torrentio"),
              S.Result("p", "2", 1, 0, "", engine="peerflix"),
              S.Result("r", "3", 0, 0, "", engine="rd")]
        self.assertEqual([r.engine for r in S.sort_by_engine_and_lang(rs, ["es-ES"])], ["rd", "peerflix", "torrentio"])

    def test_pick_info_quita_lo_repetido(self):
        detail = "Peli.2020.1080p.mkv\n👤 12 💾 4.38 GB ⚙️ Wolfmax4k\n🇪🇸"
        self.assertEqual(S.pick_info(detail, "Peli.2020.1080p.mkv"), "⚙️ Wolfmax4k  ·  🇪🇸")

    def test_human_size(self):
        self.assertEqual(S.human_size(0), "?")
        self.assertEqual(S.human_size(4.38 * 1024 ** 3), "4,4 GB")
        self.assertEqual(S.human_size(700 * 1024 ** 2), "700 MB")


class Addons(unittest.TestCase):
    def test_clean_base(self):
        for raw in ("https://x.io/abc/manifest.json", "https://x.io/abc/configure", "https://x.io/abc/"):
            self.assertEqual(motores.clean_base(raw), "https://x.io/abc")

    def test_parse_streams_lee_description(self):
        body = {"streams": [{"infoHash": "ABC", "name": "Peerflix 🇪🇸 1080p",
                             "description": "Serie.S01E02.1080p.mkv\n👤 7 💾 1.2 GB",
                             "behaviorHints": {"bingeGroup": "peerflix|1080p"}}]}
        r = motores.parse_streams(body, "peerflix")[0]
        self.assertEqual(r.name, "Serie.S01E02.1080p.mkv")
        self.assertEqual(r.seeders, 7)
        self.assertEqual(r.lang, "es-ES")
        self.assertEqual(r.quality, "1080p")
        self.assertGreater(r.size_bytes, 1024 ** 3)
        self.assertEqual(r.info_hash, "abc")

    def test_stream_path(self):
        self.assertEqual(motores.stream_path("series", "tt1", 2, 5), "/stream/series/tt1:2:5.json")
        self.assertEqual(motores.stream_path("movie", "tt1", None, None), "/stream/movie/tt1.json")


class Enlaces(unittest.TestCase):
    def test_tidy(self):
        self.assertEqual(links.tidy("dontorrent.management/serie/1#:~:text=hola"),
                         "https://dontorrent.management/serie/1")
        self.assertTrue(links.tidy(" magnet:?xt=urn:btih:abc ").startswith("magnet:"))

    def test_truncado(self):
        self.assertTrue(links.looks_truncated("02/33703/Oliver-y-Benji"))
        self.assertFalse(links.looks_truncated("https://a.b/c/d"))


class Progreso(unittest.TestCase):
    def setUp(self):
        watch_store.lista.clear()

    def test_visto_y_continuar(self):
        watch_store.record(10, "series", 1, 2, "Serie", None, 600, 1200)
        watch_store.record(20, "movie", None, None, "Peli", None, 1150, 1200)
        self.assertFalse(watch_store.is_watched_episode(10, 1, 2))
        self.assertTrue(watch_store.is_watched_title("movie", 20))
        cont = watch_store.continue_watching("series")
        self.assertEqual([p["key"] for p in cont], ["series:10:1:2"])
        self.assertEqual(watch_store.continue_watching("movie"), [])

    def test_ignora_poco_rato(self):
        watch_store.record(30, "movie", None, None, "x", None, 3, 100)
        self.assertIsNone(watch_store.progress_for("movie:30"))


class Firestore(unittest.TestCase):
    def test_ida_y_vuelta(self):
        v = {"a": [1, 2.5, True, None, "x"], "b": {"c": "d"}}
        self.assertEqual(sync._dec(sync._enc(v)), v)

    def test_bool_no_es_int(self):
        self.assertEqual(sync._enc(True), {"booleanValue": True})

    def test_ruta_con_guiones(self):
        self.assertEqual(sync._campo(["states", "1a2b-c3", "favorites"]), "states.`1a2b-c3`.favorites")


class Secretos(unittest.TestCase):
    def test_dpapi_ida_y_vuelta(self):
        almacen.guardar_secreto("prueba", "valor-secreto")
        self.assertEqual(almacen.secreto("prueba"), "valor-secreto")
        self.assertNotIn(b"valor-secreto", almacen.ruta("secretos.bin").read_bytes())
        almacen.guardar_secreto("prueba", "")
        self.assertEqual(almacen.secreto("prueba"), "")


if __name__ == "__main__":
    unittest.main()
