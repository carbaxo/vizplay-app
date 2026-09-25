import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// La lista de enlaces de un título o un episodio (SourcesSection de Android).
//
// Filtros: MOTOR (se recuerda entre títulos, como Stremio), IDIOMA (arranca en
// «mis idiomas»; los de idioma desconocido no se esconden nunca, porque la
// detección por el nombre falla a menudo) y CALIDAD (lo que no se identifica va
// a «Otras», nunca desaparece). Lo que ya está en tu Real-Debrid sale arriba y
// en todos los motores: no es una fuente aparte, es el mismo torrent.
ColumnLayout {
    id: f
    property var fuentes: []
    property bool cargando: false
    property string etiqueta: ""
    property var titulo: ({})
    property var construirCtx: function () { return {} }
    spacing: Tema.px(8)

    property string filtroIdioma: "mine"
    property string filtroCalidad: "all"
    property bool plegado: false
    readonly property string motor: App.st.prefs.engine || "all"
    readonly property var misIdiomas: App.st.prefs.langOrder || []

    function deMotor(r, e) { return e === "all" || r.engine.indexOf(e) >= 0 || r.engine === "rd" }
    readonly property var porMotor: fuentes.filter(r => deMotor(r, motor))
    readonly property var porIdioma: filtroIdioma === "all" ? porMotor
        : filtroIdioma === "mine" ? porMotor.filter(r => r.lang === null || misIdiomas.indexOf(r.lang) >= 0)
        : porMotor.filter(r => r.lang === filtroIdioma)
    readonly property var filtradas: filtroCalidad === "all" ? porIdioma : porIdioma.filter(r => r.quality === filtroCalidad)
    // Los packs al final (son el plan B) y lo que ya está en tu RD, arriba.
    // sort es estable, así que dentro de cada grupo se mantiene el orden por
    // motor, idioma y semillas que ya trae del núcleo.
    readonly property var mostradas: {
        const l = filtradas.slice()
        l.sort((a, b) => (App.enRd(b.infoHash) - App.enRd(a.infoHash)) || ((a.pack ? 1 : 0) - (b.pack ? 1 : 0)))
        return l
    }
    readonly property int alInstante: mostradas.filter(r => App.enRd(r.infoHash)).length

    onFuentesChanged: if (fuentes.length === 0) { filtroCalidad = "all" }

    // ------------------------------------------------------ filtros
    Flow {
        Layout.fillWidth: true
        spacing: Tema.px(8)
        Repeater {
            model: ["all"].concat(App.st.prefs.extraConfigured ? ["extra"] : []).concat(["peerflix", "torrentio"])
            Chip {
                required property var modelData
                readonly property int n: modelData === "all" ? f.fuentes.length
                                         : f.fuentes.filter(r => f.deMotor(r, modelData)).length
                text: ({ all: "Todos", extra: "Extra", peerflix: "Peerflix", torrentio: "Torrentio" })[modelData]
                      + (f.fuentes.length ? " (" + n + ")" : "")
                seleccionado: f.motor === modelData
                onClicked: App.ajustar("engine", modelData)
            }
        }
    }
    Flow {
        readonly property var idiomas: {
            const s = []
            for (const r of f.porMotor) if (r.lang && s.indexOf(r.lang) < 0) s.push(r.lang)
            return s
        }
        readonly property int sinIdioma: f.porMotor.filter(r => r.lang === null).length
        visible: idiomas.length > 1 || (idiomas.length > 0 && sinIdioma > 0)
        Layout.fillWidth: true
        spacing: Tema.px(8)
        Chip {
            text: "Mis idiomas (" + f.porMotor.filter(r => r.lang === null || f.misIdiomas.indexOf(r.lang) >= 0).length + ")"
            seleccionado: f.filtroIdioma === "mine"
            onClicked: f.filtroIdioma = "mine"
        }
        Repeater {
            model: parent.idiomas
            Chip {
                required property var modelData
                text: App.idioma(modelData) + " " + f.porMotor.filter(r => r.lang === modelData).length
                seleccionado: f.filtroIdioma === modelData
                onClicked: f.filtroIdioma = modelData
                ToolTip.visible: hovered
                ToolTip.text: App.nombreIdioma(modelData)
            }
        }
        Chip {
            text: "Todos (" + f.porMotor.length + ")"
            seleccionado: f.filtroIdioma === "all"
            onClicked: f.filtroIdioma = "all"
        }
    }
    Flow {
        readonly property var presentes: {
            const orden = ["4K", "1080p", "720p", "480p", "SD", "Unknown"]
            return orden.filter(q => f.porMotor.some(r => r.quality === q))
        }
        visible: presentes.length > 1
        Layout.fillWidth: true
        spacing: Tema.px(8)
        Chip { text: "Todas"; seleccionado: f.filtroCalidad === "all"; onClicked: f.filtroCalidad = "all" }
        Repeater {
            model: parent.presentes
            Chip {
                required property var modelData
                text: (modelData === "Unknown" ? "Otras" : modelData) + " (" + f.porMotor.filter(r => r.quality === modelData).length + ")"
                seleccionado: f.filtroCalidad === modelData
                onClicked: f.filtroCalidad = modelData
            }
        }
    }

    RowLayout {
        visible: f.cargando
        spacing: Tema.px(8)
        BusyIndicator { running: f.cargando; Layout.preferredWidth: Tema.px(20); Layout.preferredHeight: Tema.px(20) }
        Etiqueta { text: "Buscando fuentes…"; secundario: true; estilo: "bodySmall" }
    }
    Etiqueta {
        visible: f.fuentes.length > 0 && f.mostradas.length === 0
        Layout.fillWidth: true
        color: Tema.warn
        estilo: "bodySmall"
        text: f.porMotor.length === 0 ? "Sin enlaces de este motor para este título; prueba «Todos»."
            : f.porIdioma.length === 0 ? "Ningún enlace en tus idiomas; pulsa «Todos» para verlos igual."
            : "Ningún enlace con esa calidad; prueba «Todas»."
    }

    AbstractButton {
        visible: f.fuentes.length > 0
        Layout.fillWidth: true
        focusPolicy: Qt.StrongFocus
        onClicked: f.plegado = !f.plegado
        Keys.onReturnPressed: clicked()
        padding: Tema.px(4)
        background: Rectangle { color: parent.hovered ? "#0dffffff" : "transparent"; radius: Tema.radio; Anillo { activo: parent.parent.visualFocus } }
        contentItem: RowLayout {
            Etiqueta {
                Layout.fillWidth: true
                estilo: "titleSmall"
                text: "Enlaces (" + f.mostradas.length + ")" + (f.alInstante > 0 ? " · ⚡" + f.alInstante + " al instante" : "")
                      + (f.etiqueta ? " · " + f.etiqueta : "")
            }
            Icono { nombre: f.plegado ? "abajo" : "arriba"; tam: Tema.px(14) }
        }
    }

    Repeater {
        model: f.plegado ? [] : f.mostradas
        Rectangle {
            id: tarjeta
            required property var modelData
            Layout.fillWidth: true
            implicitHeight: colEnlace.implicitHeight + Tema.px(24)
            radius: Tema.radioTarjeta
            color: Tema.surface1
            ColumnLayout {
                id: colEnlace
                anchors.fill: parent
                anchors.margins: Tema.px(12)
                spacing: Tema.px(6)
                Etiqueta {
                    visible: tarjeta.modelData.pack
                    text: "📦 Pack de temporada · al abrirlo eliges el capítulo"
                    color: Tema.warn; estilo: "labelSmall"; font.weight: Font.Bold
                }
                Etiqueta {
                    visible: App.enRd(tarjeta.modelData.infoHash)
                    text: "⚡ Ya en tu Real-Debrid · se reproduce al instante"
                    color: Tema.ok; estilo: "labelSmall"; font.weight: Font.Bold
                }
                Etiqueta {
                    Layout.fillWidth: true
                    text: tarjeta.modelData.name
                    estilo: "bodySmall"
                    maximumLineCount: 2
                    wrapMode: Text.WrapAnywhere
                }
                Etiqueta {
                    Layout.fillWidth: true
                    secundario: true
                    estilo: "labelSmall"
                    // "0 seeders" no significa muerto: significa que el addon no
                    // manda el dato. Mostrarlo hacía parecer inservible a Peerflix.
                    text: [tarjeta.modelData.engineLabel ? "⚙ " + tarjeta.modelData.engineLabel : "",
                           tarjeta.modelData.lang ? App.idioma(tarjeta.modelData.lang) + " · " + App.nombreIdioma(tarjeta.modelData.lang)
                                                  : "Idioma desconocido",
                           tarjeta.modelData.quality !== "Unknown" ? tarjeta.modelData.quality : "",
                           tarjeta.modelData.seeders > 0 ? "▲ " + tarjeta.modelData.seeders + " seeders" : "",
                           tarjeta.modelData.sizeBytes > 0 ? tarjeta.modelData.size : ""].filter(x => x).join("  ·  ")
                }
                Etiqueta {
                    visible: tarjeta.modelData.info !== ""
                    Layout.fillWidth: true
                    text: tarjeta.modelData.info
                    secundario: true
                    estilo: "labelSmall"
                    maximumLineCount: 2
                }
                Flow {
                    visible: App.rd
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton {
                        text: tarjeta.modelData.pack ? "Elegir capítulo" : "Ver"
                        icono: tarjeta.modelData.pack ? "abrir" : "play"
                        onClicked: tarjeta.modelData.pack ? f.abrirPack(tarjeta.modelData, 0) : f.preparar(tarjeta.modelData, false, 0)
                    }
                    Boton {
                        text: "Descargar"; icono: "descargar"; tipo: "secundario"
                        onClicked: f.preparar(tarjeta.modelData, true, 0)
                    }
                    Boton {
                        text: "Copiar magnet"; icono: "enlace"; tipo: "texto"
                        onClicked: { backend.copiar(tarjeta.modelData.magnet); App.aviso("Magnet copiado") }
                    }
                }
                Etiqueta {
                    visible: !App.rd
                    text: "Conecta Real-Debrid en Ajustes para ver o descargar."
                    color: Tema.warn; estilo: "labelSmall"
                }
            }
        }
    }

    // --------------------------------------- Real-Debrid prepara el enlace
    // prep = {descarga, msg, error, magnet, enRd, cancelado}
    property var prep: null
    property var capitulos: null

    function preparar(r, descarga, intento) {
        if (intento === 0) prep = { descarga: descarga, msg: descarga ? "Pidiendo el enlace a Real-Debrid…" : "Preparando el vídeo…",
                                    error: "", magnet: r.magnet, enRd: false }
        App.llamar("rdStream", { magnet: r.magnet }, function (m) {
            if (!f.prep || f.prep.magnet !== r.magnet) return   // cancelado por el usuario
            const d = m.ok ? m.data : { error: m.error }
            if (d.url) {
                f.prep = null
                if (descarga) {
                    App.llamar("dlAdd", { url: d.url, name: d.filename || f.titulo.title, magnet: r.magnet })
                    App.aviso("⬇ Descarga en marcha: " + (d.filename || ""))
                    App.irA(2)
                } else {
                    const c = f.construirCtx()
                    c.url = d.url; c.engine = r.engine; c.quality = r.quality; c.lang = r.lang
                    App.reproducir(c)
                }
            } else if (d.progress !== undefined && intento < 25) {
                // No es que el archivo no exista: RD no lo tenía en caché y lo
                // está bajando él. Y eso depende de las semillas del torrent.
                f.prep = Object.assign({}, f.prep, { enRd: true,
                    msg: "Real-Debrid no lo tenía en caché y lo está bajando a sus servidores: " + d.progress + "%. Cuando acabe, se verá al instante."
                         + (r.seeders === 0 ? "\n\n⚠️ Este enlace no declara semillas. Si nadie lo comparte, puede no avanzar: mejor prueba otro con semillas." : "") })
                reintento.lanzar(function () { if (f.prep && f.prep.magnet === r.magnet) f.preparar(r, descarga, intento + 1) })
            } else if (d.progress !== undefined) {
                f.prep = Object.assign({}, f.prep, { error: "Real-Debrid sigue bajándolo a sus servidores (" + d.progress + "%). No se pierde: sigue en tu cuenta y el progreso se ve en Descargas." })
            } else {
                f.prep = Object.assign({}, f.prep, { error: d.error || "Error de Real-Debrid" })
            }
        })
    }

    function abrirPack(r, intento) {
        if (intento === 0) prep = { descarga: false, msg: "Abriendo el pack en Real-Debrid…", error: "", magnet: r.magnet, enRd: false }
        App.llamar("rdPack", { magnet: r.magnet }, function (m) {
            if (!f.prep || f.prep.magnet !== r.magnet) return
            const d = m.ok ? m.data : { error: m.error }
            if (d.files) { f.prep = null; f.capitulos = d.files }
            else if (d.progress !== undefined && intento < 25) {
                f.prep = Object.assign({}, f.prep, { enRd: true, msg: "Real-Debrid está bajando el pack a sus servidores: " + d.progress + "%.\nEsto solo pasa la primera vez; luego los capítulos salen al instante." })
                reintento.lanzar(function () { if (f.prep && f.prep.magnet === r.magnet) f.abrirPack(r, intento + 1) })
            } else if (d.progress !== undefined) {
                f.prep = Object.assign({}, f.prep, { error: "Real-Debrid sigue con el pack (" + d.progress + "%). No se pierde: sigue en tu cuenta y puedes ver el progreso en Descargas." })
            } else f.prep = Object.assign({}, f.prep, { error: d.error || "No se pudo abrir el pack." })
        })
    }

    function capitulo(file, descarga) {
        capitulos = null
        prep = { descarga: descarga, msg: "Preparando " + file.short + "…", error: "", magnet: "pack:" + file.link, enRd: false }
        App.llamar("rdUnrestrict", { link: file.link }, function (m) {
            if (!f.prep || f.prep.magnet !== "pack:" + file.link) return
            const d = m.ok ? m.data : { error: m.error }
            if (!d.url) { f.prep = Object.assign({}, f.prep, { error: d.error || "No se pudo preparar el capítulo." }); return }
            f.prep = null
            if (descarga) {
                App.llamar("dlAdd", { url: d.url, name: d.filename || file.short })
                App.aviso("⬇ Descarga en marcha: " + (d.filename || file.short))
                App.irA(2)
            } else {
                const c = f.construirCtx()
                c.url = d.url
                App.reproducir(c)
            }
        })
    }

    Timer {
        id: reintento
        property var accion: null
        interval: 4000
        function lanzar(a) { accion = a; restart() }
        onTriggered: if (accion) accion()
    }

    // Los Popup se abren y cierran a mano: un binding a `visible` se rompe en
    // cuanto el usuario cierra con Esc y ya no volvería a abrirse.
    onPrepChanged: prep ? ventanaPrep.open() : ventanaPrep.close()
    onCapitulosChanged: capitulos ? ventanaCapitulos.open() : ventanaCapitulos.close()

    Dialogo {
        id: ventanaPrep
        titulo: f.prep ? (f.prep.descarga ? "Preparando la descarga" : "Cargando…") : ""
        onClosed: f.prep = null
        RowLayout {
            Layout.fillWidth: true
            spacing: Tema.px(14)
            BusyIndicator { visible: f.prep && !f.prep.error; running: visible; Layout.preferredWidth: Tema.px(32); Layout.preferredHeight: Tema.px(32) }
            Etiqueta {
                Layout.fillWidth: true
                text: f.prep ? (f.prep.error || f.prep.msg) : ""
                color: f.prep && f.prep.error ? Tema.warn : "white"
            }
        }
        pie: [
            Boton { text: f.prep && f.prep.error ? "Cerrar" : "Cancelar"; tipo: "texto"; onClicked: f.prep = null },
            // Si RD lo ha RECHAZADO por copyright no hay nada que esperar: eso
            // solo lo saca un cliente BitTorrent, así que se ofrece pasárselo.
            Boton {
                visible: !!(f.prep && f.prep.error && f.prep.error.indexOf("bloqueados por copyright") >= 0 && f.prep.magnet.indexOf("magnet:") === 0)
                text: "Abrir en tu app de torrents"; tipo: "secundario"
                onClicked: { backend.abrirUrl(f.prep.magnet); f.prep = null }
            },
            // Si RD no pudo (no lo tiene en caché, o se borró), meterlo en la
            // cuenta a mano y esperar a que lo baje.
            Boton {
                visible: !!(f.prep && f.prep.error && f.prep.error.indexOf("bloqueados por copyright") < 0 && f.prep.magnet.indexOf("magnet:") === 0)
                text: "Añadirlo a Real-Debrid"; tipo: "secundario"
                onClicked: { App.pegarEnDescargas(f.prep.magnet); f.prep = null }
            },
            // Mientras RD lo baja no hay que quedarse mirando: sigue solo
            Boton {
                visible: !!(f.prep && !f.prep.error && f.prep.enRd)
                text: "Ver progreso"; tipo: "secundario"
                onClicked: { f.prep = null; App.irA(2) }
            }
        ]
    }

    Dialogo {
        id: ventanaCapitulos
        titulo: "Elige el capítulo"
        ancho: Tema.px(640)
        onClosed: f.capitulos = null
        Etiqueta {
            Layout.fillWidth: true
            text: (f.capitulos ? f.capitulos.length : 0) + " capítulos en el pack. Ya están todos en tu Real-Debrid: cualquiera se ve al instante."
            secundario: true; estilo: "labelSmall"
        }
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, Tema.px(420))
            clip: true
            model: f.capitulos || []
            keyNavigationEnabled: true
            focus: true
            ScrollBar.vertical: BarraScroll {}
            delegate: AbstractButton {
                id: cap
                required property var modelData
                width: ListView.view.width
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                padding: Tema.px(10)
                onClicked: f.capitulo(modelData, false)
                Keys.onReturnPressed: clicked()
                background: Rectangle {
                    radius: Tema.radio
                    color: cap.hovered || cap.activeFocus ? Tema.ringSoft : "transparent"
                    border.width: cap.activeFocus ? 2 : 0
                    border.color: Tema.ring
                }
                contentItem: RowLayout {
                    spacing: Tema.px(10)
                    Etiqueta { Layout.fillWidth: true; text: cap.modelData.short; maximumLineCount: 2 }
                    Etiqueta { text: cap.modelData.bytes > 0 ? cap.modelData.size : ""; secundario: true; estilo: "labelSmall" }
                    Boton { text: "Descargar"; compacto: true; tipo: "texto"; onClicked: f.capitulo(cap.modelData, true) }
                }
            }
        }
        pie: [Boton { text: "Cerrar"; tipo: "texto"; onClicked: f.capitulos = null }]
    }
}
