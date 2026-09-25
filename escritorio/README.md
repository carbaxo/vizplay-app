# 🖥️ VizPlay — app de escritorio para Windows (PySide6 + QML)

App **nativa e independiente** para el PC, hermana de la de Android
([`android-standalone/`](../android-standalone)): la misma lógica portada a
Python y el mismo aspecto que la app de **Android TV**. No necesita el servidor
Node ni la web: habla directamente con TMDB, los addons de Stremio, Real-Debrid
y Firebase.

> ⚡ **Requiere una cuenta de Real-Debrid.** Igual que en Android, no hay motor
> BitTorrent: el magnet se le entrega a Real-Debrid y el vídeo llega por HTTPS
> desde sus servidores.

## Arrancar

Doble clic en **`arrancar-escritorio.bat`** (en la raíz del repositorio). La
primera vez crea el entorno de Python (`.venv`) e instala lo necesario; las
siguientes abre la app directamente. Si ya está abierta, la trae al frente.

Hace falta **Python 3.10 o posterior** instalado.

Para tenerla en el **escritorio y el menú Inicio** con su icono (el de Android:
la V sobre el círculo granate), una vez creado el entorno:

```bash
.venv\Scripts\python -m escritorio.accesos
```

La primera vez, en **Ajustes**:

1. **Cuenta**: «Entrar con Google» (se abre el navegador) o email y contraseña.
   Es la **misma cuenta** que Android y la web: llegan los perfiles, Mi lista,
   el «continuar viendo» y el token de Real-Debrid.
2. **Real-Debrid**: si no ha llegado con la cuenta, pega el token de
   <https://real-debrid.com/apitoken>.
3. **Catálogos (TMDB)**: pega una clave gratuita de
   <https://www.themoviedb.org/settings/api>. En Android va dentro del APK
   (secreto de GitHub); aquí el código es público, así que se pega una vez y se
   queda en el PC. También vale la variable de entorno `TMDB_KEY`.

## Por qué nativa y no la de Electron

La app de Electron ([`electron/`](../electron)) muestra la web, y la web
reproduce con el `<video>` del navegador, que **no lleva bien** lo típico de
Real-Debrid: MKV con vídeo HEVC y audio AC3/DTS/E-AC3. Esta usa **QtMultimedia**,
que por debajo es **FFmpeg**. Comprobado en este PC con vídeos reales por HTTPS:

| Prueba | Resultado |
|---|---|
| MKV H.264 | ✅ se decodifica |
| MP4 **HEVC** (H.265) | ✅ se decodifica |
| MKV H.264 + **DTS 4.0** | ✅ imagen y sonido |
| MKV H.264 + **E-AC3 5.1** | ✅ imagen y sonido |

> Ojo: `QMediaFormat.supportedVideoCodecs()` **no** lista HEVC ni DTS, pero los
> reproduce. Esa lista de Qt es parcial; lo que vale es probar.

## Qué hace (fases 1 y 2)

- **Descubrir**: filas de Netflix, Prime Video, HBO Max y Disney+ (TMDB),
  géneros, **Continuar viendo**, **Mi lista**, **Recomendado para ti**,
  exploración en rejilla («Ver más») y avisos de **episodios nuevos** de las
  series de Mi lista. El selector Películas / Series manda en toda la pantalla.
- **Buscar** por título (también con perfil infantil).
- **Ficha** con la disposición de la tele: carátula a la izquierda, ficha y
  enlaces a la derecha, tráiler y Mi lista. En películas los enlaces salen solos;
  en series, al pulsar el episodio.
- **Enlaces** de Peerflix, Torrentio, el addon extra y **tu propia cuenta de
  Real-Debrid**, pintados según contesta cada motor, con filtros por motor,
  idioma y calidad, **packs de temporada** con selector de capítulo y la ventana
  de «Real-Debrid lo está preparando…» con reintento automático.
- **Reproductor propio**: pista de audio, subtítulos internos o un `.srt`/`.vtt`
  tuyo, velocidad, pantalla completa, reanuda donde lo dejaste, guarda el
  progreso cada 10 s y **siguiente episodio** con el mismo motor, calidad e
  idioma. O, si se prefiere, **VLC** (Ajustes → Reproducción).
- **Descargas** con **pausa y continuación** (HTTP `Range`) y **renovación del
  enlace** de Real-Debrid si caduca. Al cerrar la app se pausan (avisa antes) y
  siguen desde donde iban al volver. Carpeta elegible (por defecto
  `Descargas\VizPlay`); los vídeos que haya en ella aparecen listos para ver.
- **Añadir a Real-Debrid a mano** (magnet o enlace de hoster) y la lista de la
  cuenta con su estado real, huecos de torrent y borrar.
- **Cuenta y perfiles** (hasta 5, con **modo infantil**), sincronizados con
  Firestore en el mismo documento que Android y la web.
- **Modo tele** (Ajustes → Apariencia): todo un 15 % más grande, para un PC
  conectado a la tele.

**Aún no** (a propósito): TV en directo (IPTV), canales de YouTube y Chromecast.

## Teclado

Esc vuelve atrás · Ctrl+F busca · Ctrl+1…4 cambia de sección · Tab y flechas
mueven el foco (con el anillo blanco de la tele) · Intro abre.
En el reproductor: Espacio pausa · ←/→ 10 s · ↑/↓ volumen · F pantalla
completa · M silencio · N siguiente episodio.

## Arquitectura

```
arrancar-escritorio.bat     en la raíz: crea .venv, instala y lanza con pythonw
escritorio/
  __main__.py               registro, instancia única, fuentes, motor QML
  puente.py                 QObject "backend": estado (JSON) + pedidos asíncronos
  captura.py                recorre las pantallas y guarda PNG (revisión de UI)
  nucleo/                   la lógica de Android, sin interfaz, un módulo por .kt
    lang.py                 Lang.kt         idioma de cada fuente
    search.py               Search.kt       modelo de enlace, calidad, episodeFit
    motores.py              Addon/Torrentio/Peerflix/ExtraAddon.kt
    rd_engine.py            RdEngine.kt     tu cuenta de RD como motor
    realdebrid.py           RealDebrid.kt   magnet -> URL directa, cuenta, packs
    tmdb.py                 Tmdb.kt         catálogos y fichas
    watch_store.py          WatchStore.kt   progreso y vistos
    sync.py                 Sync.kt         Firebase Auth + Firestore por REST
    google_login.py         (nuevo)         Google con el Firebase de la web
    downloads.py            Downloads.kt    pausa, continuar, renovar enlace
    fuentes.py              MainActivity/PlayerActivity: búsqueda y siguiente ep.
    prefs.py · links.py · almacen.py (rutas, JSON atómico, DPAPI) · red.py
  qml/VizPlay/              la interfaz: Tema.qml (Theme.kt), App.qml (estado)…
  login/                    página local del login con Google (Firebase compat)
  fuentes/                  Inter e Inter Display (las mismas del APK)
  tests/test_nucleo.py      pruebas sin red
```

- **Datos** en `%APPDATA%\VizPlay`. El token de Real-Debrid y la sesión de
  Firebase van cifrados con **DPAPI** (atados a tu usuario de Windows).
- **Firebase por REST**: no hay SDK de cliente para Python, así que la app habla
  con Identity Toolkit, Secure Token y Firestore como un cliente más, con el
  token del usuario: se aplican las mismas reglas de `firestore.rules`. Las
  escrituras son parciales (`updateMask`), el `SetOptions.merge()` de Android.
- **Entrar con Google**: una página en `http://localhost:<puerto>` con el mismo
  Firebase de la web (`signInWithPopup`); `localhost` ya está autorizado porque
  lo usa la app de Electron. Solo escucha en 127.0.0.1 y exige el `nonce` de la
  página que sirve.

## Pruebas

```bash
.venv\Scripts\python -m unittest discover -s escritorio/tests
.venv\Scripts\python -m escritorio.captura <carpeta> --demo --video <url>
```

`--demo` sustituye solo las respuestas de TMDB (para revisar la interfaz sin
clave); los buscadores y Real-Debrid siguen siendo los de verdad.

El registro está en `%APPDATA%\VizPlay\vizplay.log`.
