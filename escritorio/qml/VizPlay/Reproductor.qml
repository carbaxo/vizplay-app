import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import QtMultimedia
import QtCore

// El reproductor propio (PlayerActivity). QtMultimedia usa FFmpeg por debajo,
// así que se come los MKV de Real-Debrid con HEVC y audio AC3/DTS/EAC3 que el
// navegador (y por tanto la app de Electron) no reproduce, y deja elegir pista
// de audio y subtítulos como ExoPlayer.
//
// Guarda el «continuar viendo» cada 10 s y al salir, reanuda donde se dejó y
// ofrece el siguiente episodio buscándolo con el MISMO motor, calidad e idioma.
//
// Teclado: Espacio/K pausa · ←/→ 10 s · ↑/↓ volumen · F pantalla completa ·
// M silencio · N siguiente episodio · Esc salir de pantalla completa / cerrar.
Rectangle {
    id: rep
    objectName: "reproductor"
    color: "black"
    focus: true
    property var ctx: ({})
    signal cerrar()

    property bool reanudado: false
    property string error: ""
    property var cues: []
    property string nombreSub: ""
    property int velIdx: 0
    readonly property var velocidades: [1, 1.25, 1.5, 2, 0.5, 0.75]
    property bool buscandoSiguiente: false
    property string avisoTxt: ""
    readonly property bool esSerie: ctx.type === "series" && ctx.episode > 0
    readonly property real restante: (mp.duration - mp.position) / 1000

    Settings { id: ajustes; category: "reproductor"; property real volumen: 1.0; property bool mudo: false }

    MediaPlayer {
        id: mp
        source: rep.ctx.url || ""
        videoOutput: video
        audioOutput: AudioOutput { id: salida; volume: ajustes.volumen; muted: ajustes.mudo }
        onMediaStatusChanged: {
            // Reanudar donde se dejó, en cuanto el vídeo se deja mover
            if (!rep.reanudado && (mediaStatus === MediaPlayer.LoadedMedia || mediaStatus === MediaPlayer.BufferedMedia)) {
                rep.reanudado = true
                if (rep.ctx.resume > 5) { mp.position = rep.ctx.resume * 1000; rep.aviso("Seguimos donde lo dejaste: " + App.tiempo(rep.ctx.resume)) }
                mp.play()
            }
            if (mediaStatus === MediaPlayer.EndOfMedia) { rep.guardar(); controles.mostrar() }
        }
        onErrorOccurred: function (err, texto) { rep.error = texto || "No se pudo reproducir el vídeo." }
        onPlaybackStateChanged: backend.mantenerDespierto(playbackState === MediaPlayer.PlayingState)
    }
    VideoOutput { id: video; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectFit }

    // Subtítulo externo (.srt/.vtt), pintado encima: QtMultimedia no los carga
    Text {
        id: sub
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: controles.visible ? barraAbajo.height + Tema.px(16) : Tema.px(48)
        width: parent.width * 0.8
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: "white"
        style: Text.Outline
        styleColor: "black"
        font.family: Tema.familia
        font.weight: Font.DemiBold
        font.pixelSize: Math.max(18, Math.round(rep.height / 26))
        text: rep.cueEn(mp.position / 1000)
        visible: text !== ""
    }
    function cueEn(t) {
        // Búsqueda binaria: con miles de líneas no se recorre la lista entera
        let lo = 0, hi = cues.length - 1
        while (lo <= hi) {
            const m = (lo + hi) >> 1
            if (cues[m].end < t) lo = m + 1
            else if (cues[m].start > t) hi = m - 1
            else return cues[m].text
        }
        return ""
    }

    BusyIndicator {
        anchors.centerIn: parent
        // BufferingMedia NO: significa «cargando, pero hay para seguir». Solo
        // cuando de verdad está parado esperando datos.
        running: rep.error === "" && (mp.mediaStatus === MediaPlayer.LoadingMedia || mp.mediaStatus === MediaPlayer.StalledMedia)
        width: Tema.px(64); height: width
    }

    // Aviso central (saltos, volumen, cambios de pista)
    Rectangle {
        id: avisoCaja
        anchors.centerIn: parent
        visible: opacity > 0
        opacity: 0
        radius: Tema.px(8)
        color: "#cc000000"
        width: avisoTexto.implicitWidth + Tema.px(40)
        height: avisoTexto.implicitHeight + Tema.px(24)
        Etiqueta { id: avisoTexto; anchors.centerIn: parent; text: rep.avisoTxt; estilo: "titleMedium" }
        Behavior on opacity { NumberAnimation { duration: 150 } }
        Timer { id: avisoTimer; interval: 1100; onTriggered: avisoCaja.opacity = 0 }
    }
    function aviso(t, ms) { avisoTxt = t; avisoCaja.opacity = 1; avisoTimer.interval = ms || 1100; avisoTimer.restart() }

    // Error: lo normal es un códec que ni FFmpeg conoce, o el enlace caducado
    Rectangle {
        visible: rep.error !== ""
        anchors.centerIn: parent
        width: Math.min(parent.width - 80, Tema.px(560))
        height: colErr.implicitHeight + Tema.px(40)
        radius: Tema.px(12)
        color: Tema.surface1
        z: 30
        ColumnLayout {
            id: colErr
            anchors.fill: parent
            anchors.margins: Tema.px(20)
            spacing: Tema.px(10)
            Etiqueta { text: "No se ha podido reproducir"; estilo: "titleLarge" }
            Etiqueta { Layout.fillWidth: true; text: rep.error; secundario: true; estilo: "bodySmall" }
            Etiqueta {
                Layout.fillWidth: true
                visible: App.st.vlc !== ""
                text: "VLC sí está instalado: suele poder con lo que aquí falla."
                secundario: true; estilo: "bodySmall"
            }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Boton {
                    visible: App.st.vlc !== ""
                    text: "Abrir en VLC"
                    onClicked: {
                        App.llamar("externalPlayer", { url: rep.ctx.url, name: rep.ctx.name, resume: mp.position / 1000 })
                        rep.salir()
                    }
                }
                Boton { text: "Reintentar"; tipo: "secundario"; onClicked: { rep.error = ""; const u = mp.source; mp.source = ""; mp.source = u; mp.play() } }
                Boton { text: "Cerrar"; tipo: "texto"; onClicked: rep.salir() }
            }
        }
    }

    // ---------------------------------------------------------- controles
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: controles.visible ? Qt.ArrowCursor : Qt.BlankCursor
        onPositionChanged: controles.mostrar()
        onClicked: { rep.alternar(); controles.mostrar() }
        onDoubleClicked: rep.pantallaCompleta()
        acceptedButtons: Qt.LeftButton
    }

    Item {
        id: controles
        anchors.fill: parent
        visible: opacity > 0
        opacity: 1
        Behavior on opacity { NumberAnimation { duration: 200 } }
        function mostrar() { opacity = 1; ocultar.restart() }
        Timer {
            id: ocultar
            interval: 3500
            running: true
            onTriggered: if (mp.playbackState === MediaPlayer.PlayingState && !menuAudio.visible && !menuSub.visible
                             && !barraTiempo.pressed) controles.opacity = 0
        }

        Rectangle {
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            height: Tema.px(110)
            gradient: Gradient { GradientStop { position: 0; color: "#cc000000" } GradientStop { position: 1; color: "#00000000" } }
            RowLayout {
                anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                anchors.margins: Tema.px(18)
                spacing: Tema.px(14)
                BotonRedondo { icono: "atras"; ayuda: "Volver (Esc)"; onClicked: rep.salir() }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Etiqueta { text: rep.ctx.name || ""; estilo: "titleLarge"; Layout.fillWidth: true; maximumLineCount: 1; wrapMode: Text.NoWrap }
                    Etiqueta { visible: text !== ""; text: rep.ctx.subtitle || ""; secundario: true; estilo: "bodySmall"; Layout.fillWidth: true }
                }
            }
        }

        Rectangle {
            id: barraAbajo
            anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
            height: colAbajo.implicitHeight + Tema.px(50)
            gradient: Gradient { GradientStop { position: 0; color: "#00000000" } GradientStop { position: 1; color: "#e6000000" } }
            ColumnLayout {
                id: colAbajo
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                anchors.margins: Tema.px(20)
                spacing: Tema.px(6)

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tema.px(12)
                    Etiqueta { text: App.tiempo(mp.position / 1000); estilo: "labelLarge" }
                    Slider {
                        id: barraTiempo
                        Layout.fillWidth: true
                        from: 0; to: Math.max(1, mp.duration)
                        value: pressed ? value : mp.position
                        enabled: mp.seekable
                        focusPolicy: Qt.NoFocus
                        onMoved: mp.position = value
                        background: Rectangle {
                            x: barraTiempo.leftPadding; y: barraTiempo.topPadding + barraTiempo.availableHeight / 2 - height / 2
                            width: barraTiempo.availableWidth; height: barraTiempo.hovered ? 6 : 4; radius: 3
                            color: "#4dffffff"
                            Rectangle {
                                // lo que ya está en el búfer
                                width: parent.width * Math.min(1, mp.bufferProgress); height: parent.height; radius: 3
                                color: "#33ffffff"
                            }
                            Rectangle { width: barraTiempo.visualPosition * parent.width; height: parent.height; radius: 3; color: Tema.accent }
                        }
                        handle: Rectangle {
                            x: barraTiempo.leftPadding + barraTiempo.visualPosition * (barraTiempo.availableWidth - width)
                            y: barraTiempo.topPadding + barraTiempo.availableHeight / 2 - height / 2
                            width: Tema.px(16); height: width; radius: width / 2
                            color: Tema.accent
                            visible: barraTiempo.hovered || barraTiempo.pressed
                        }
                    }
                    Etiqueta { text: mp.duration > 0 ? "-" + App.tiempo(rep.restante) : "--:--"; estilo: "labelLarge"; secundario: true }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Tema.px(10)
                    BotonRedondo {
                        icono: mp.playbackState === MediaPlayer.PlayingState ? "pausa" : "play"
                        grande: true
                        ayuda: "Reproducir / pausa (Espacio)"
                        onClicked: rep.alternar()
                    }
                    BotonRedondo { texto: "−10"; ayuda: "Atrás 10 s (←)"; onClicked: rep.saltar(-10) }
                    BotonRedondo { texto: "+10"; ayuda: "Adelante 10 s (→)"; onClicked: rep.saltar(10) }
                    BotonRedondo {
                        icono: ajustes.mudo || ajustes.volumen === 0 ? "mudo" : "volumen"
                        ayuda: "Silencio (M)"
                        onClicked: ajustes.mudo = !ajustes.mudo
                    }
                    Slider {
                        id: vol
                        Layout.preferredWidth: Tema.px(110)
                        from: 0; to: 1
                        value: ajustes.volumen
                        focusPolicy: Qt.NoFocus
                        onMoved: { ajustes.volumen = value; ajustes.mudo = false }
                        background: Rectangle {
                            x: vol.leftPadding; y: vol.topPadding + vol.availableHeight / 2 - height / 2
                            width: vol.availableWidth; height: 4; radius: 2; color: "#4dffffff"
                            Rectangle { width: vol.visualPosition * parent.width; height: parent.height; radius: 2; color: "white" }
                        }
                        handle: Rectangle {
                            x: vol.leftPadding + vol.visualPosition * (vol.availableWidth - width)
                            y: vol.topPadding + vol.availableHeight / 2 - height / 2
                            width: Tema.px(12); height: width; radius: width / 2; color: "white"
                        }
                    }
                    Item { Layout.fillWidth: true }

                    Boton {
                        visible: rep.esSerie && (rep.restante < 90 || mp.mediaStatus === MediaPlayer.EndOfMedia)
                        text: rep.buscandoSiguiente ? "Buscando…" : "Siguiente episodio"
                        icono: "siguiente"
                        cargando: rep.buscandoSiguiente
                        enabled: !rep.buscandoSiguiente
                        onClicked: rep.siguiente()
                    }
                    BotonRedondo {
                        texto: rep.velocidades[rep.velIdx] + "×"
                        ayuda: "Velocidad"
                        onClicked: {
                            rep.velIdx = (rep.velIdx + 1) % rep.velocidades.length
                            mp.playbackRate = rep.velocidades[rep.velIdx]
                            rep.aviso("Velocidad " + rep.velocidades[rep.velIdx] + "×")
                        }
                    }
                    BotonRedondo {
                        icono: "audio"
                        ayuda: "Pista de audio"
                        onClicked: menuAudio.popup()
                        Menu {
                            id: menuAudio
                            Repeater {
                                model: mp.audioTracks
                                MenuItem {
                                    required property var modelData
                                    required property int index
                                    text: rep.nombrePista(modelData, index, "Pista")
                                    checkable: true
                                    checked: mp.activeAudioTrack === index
                                    onTriggered: { mp.activeAudioTrack = index; rep.aviso(text) }
                                }
                            }
                            MenuItem { enabled: false; visible: mp.audioTracks.length === 0; text: "Una sola pista" }
                        }
                    }
                    BotonRedondo {
                        icono: "subtitulos"
                        ayuda: "Subtítulos"
                        onClicked: menuSub.popup()
                        Menu {
                            id: menuSub
                            MenuItem {
                                text: "Sin subtítulos"
                                checkable: true
                                checked: mp.activeSubtitleTrack < 0 && rep.cues.length === 0
                                onTriggered: { mp.activeSubtitleTrack = -1; rep.cues = []; rep.nombreSub = "" }
                            }
                            Repeater {
                                model: mp.subtitleTracks
                                MenuItem {
                                    required property var modelData
                                    required property int index
                                    text: rep.nombrePista(modelData, index, "Subtítulo")
                                    checkable: true
                                    checked: mp.activeSubtitleTrack === index
                                    onTriggered: { rep.cues = []; mp.activeSubtitleTrack = index }
                                }
                            }
                            MenuItem {
                                text: rep.nombreSub ? "✓ " + rep.nombreSub : "Cargar un fichero .srt / .vtt…"
                                onTriggered: elegirSub.open()
                            }
                        }
                    }
                    BotonRedondo {
                        icono: rep.Window.window && rep.Window.window.visibility === Window.FullScreen ? "ventana" : "completa"
                        ayuda: "Pantalla completa (F)"
                        onClicked: rep.pantallaCompleta()
                    }
                }
            }
        }
    }

    FileDialog {
        id: elegirSub
        title: "Elige un subtítulo"
        nameFilters: ["Subtítulos (*.srt *.vtt)", "Todos los ficheros (*)"]
        onAccepted: App.llamar("subtitles", { path: selectedFile.toString() }, function (m) {
            if (!m.ok) { rep.aviso(m.error, 3000); return }
            mp.activeSubtitleTrack = -1
            rep.cues = m.data.cues
            rep.nombreSub = m.data.name
            rep.aviso("Subtítulo cargado")
        })
    }

    function nombrePista(meta, i, base) {
        const idi = meta.stringValue(MediaMetaData.Language)
        const tit = meta.stringValue(MediaMetaData.Title)
        const partes = [tit, idi].filter(x => x && x !== "")
        return partes.length ? partes.join(" · ") : base + " " + (i + 1)
    }
    function mostrarControles() { controles.mostrar() }
    function alternar() { mp.playbackState === MediaPlayer.PlayingState ? mp.pause() : mp.play() }
    function saltar(s) {
        mp.position = Math.max(0, Math.min(mp.duration, mp.position + s * 1000))
        aviso((s < 0 ? "⏪ " : "⏩ ") + (s > 0 ? "+" : "") + s + " s")
        controles.mostrar()
    }
    function volumen(d) {
        ajustes.volumen = Math.max(0, Math.min(1, ajustes.volumen + d))
        ajustes.mudo = false
        aviso("🔊 " + Math.round(ajustes.volumen * 100) + "%")
    }
    property int _visAntes: Window.Windowed
    function pantallaCompleta() {
        const w = rep.Window.window
        if (!w) return
        if (w.visibility === Window.FullScreen) w.visibility = _visAntes === Window.FullScreen ? Window.Windowed : _visAntes
        else { _visAntes = w.visibility; w.visibility = Window.FullScreen }
    }
    function salir() {
        guardar()
        mp.stop()
        backend.mantenerDespierto(false)
        const w = rep.Window.window
        if (w && w.visibility === Window.FullScreen) w.visibility = _visAntes === Window.FullScreen ? Window.Windowed : _visAntes
        rep.cerrar()
    }
    function guardar() {
        if (!(ctx.tmdbId > 0) || mp.position < 5000) return
        App.llamar("progress", { tmdbId: ctx.tmdbId, type: ctx.type, season: ctx.season, episode: ctx.episode,
                                 name: ctx.name, poster: ctx.poster, position: mp.position / 1000,
                                 duration: mp.duration > 0 ? mp.duration / 1000 : 0 })
    }
    Timer { interval: 10000; repeat: true; running: mp.playbackState === MediaPlayer.PlayingState; onTriggered: rep.guardar() }

    function siguiente() {
        if (!esSerie || buscandoSiguiente) return
        guardar()   // deja el actual registrado como visto
        buscandoSiguiente = true
        aviso("Buscando T" + ctx.season + "E" + (ctx.episode + 1) + "…", 4000)
        App.llamar("nextEpisode", { tmdbId: ctx.tmdbId, season: ctx.season, episode: ctx.episode,
                                    engine: ctx.engine || "", quality: ctx.quality || "", lang: ctx.lang || null }, function (m) {
            rep.buscandoSiguiente = false
            const d = m.ok ? m.data : { error: m.error }
            if (!d.url) { rep.aviso(d.error || "No hay fuentes del siguiente episodio", 3500); return }
            rep.ctx = Object.assign({}, rep.ctx, { url: d.url, season: d.season, episode: d.episode, resume: 0,
                                                   subtitle: "T" + d.season + " · E" + d.episode,
                                                   engine: d.result.engine, quality: d.result.quality, lang: d.result.lang })
            rep.reanudado = false
            rep.error = ""
            rep.cues = []
            rep.nombreSub = ""
            mp.play()
            rep.aviso("T" + d.season + "E" + d.episode, 2000)
        })
    }

    Keys.onPressed: function (ev) {
        controles.mostrar()
        switch (ev.key) {
        case Qt.Key_Space: case Qt.Key_K: case Qt.Key_MediaTogglePlayPause: case Qt.Key_MediaPlay: case Qt.Key_MediaPause:
            alternar(); break
        case Qt.Key_Left: case Qt.Key_J: saltar(-10); break
        case Qt.Key_Right: case Qt.Key_L: saltar(10); break
        case Qt.Key_Up: volumen(0.05); break
        case Qt.Key_Down: volumen(-0.05); break
        case Qt.Key_F: pantallaCompleta(); break
        case Qt.Key_M: ajustes.mudo = !ajustes.mudo; aviso(ajustes.mudo ? "Silencio" : "Sonido"); break
        case Qt.Key_N: case Qt.Key_MediaNext: siguiente(); break
        case Qt.Key_Escape: case Qt.Key_Back: case Qt.Key_Backspace: {
            const w = rep.Window.window
            if (w && w.visibility === Window.FullScreen && ev.key === Qt.Key_Escape) pantallaCompleta()
            else salir()
            break
        }
        default: return
        }
        ev.accepted = true
    }
    Component.onCompleted: { forceActiveFocus(); controles.mostrar() }
}
