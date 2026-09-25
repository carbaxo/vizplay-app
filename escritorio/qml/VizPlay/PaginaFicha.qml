import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// La ficha de un título (DetailScreen), con la disposición de la TELE: la
// carátula ENTERA a la izquierda con sus acciones debajo, y a la derecha la ficha
// y los enlaces, que así se ven de entrada. Detrás, el fondo del título
// difuminado.
//
// En películas los enlaces salen SOLOS al abrir (como Stremio). En series no se
// despliega nada solo: la temporada se ve entera y los enlaces salen al pulsar
// el episodio que quieras.
Item {
    id: ficha
    objectName: "ficha"
    property var titulo: ({})
    signal volver()

    property var detalle: null
    property string imdb: ""
    property bool imdbListo: false
    property string trailer: ""
    property string estado: "Cargando…"
    property var episodios: []
    property int temporada: -1
    property int abierto: -1           // episodio desplegado (-1 ninguno)
    property var fuentes: []
    property bool buscando: false
    property string etiqueta: ""
    property int ctxT: -1
    property int ctxE: -1
    property string nombreEp: ""
    property int busqueda: 0           // para descartar respuestas de búsquedas viejas

    readonly property bool serie: !!titulo && titulo.type === "series"
    readonly property var d: detalle || titulo

    // Se recarga TODO si cambia el título con la ficha abierta
    onTituloChanged: cargar()
    Component.onCompleted: cargar()
    function cargar() {
        if (!titulo || !titulo.tmdbId) return
        busqueda++
        detalle = null; imdb = ""; imdbListo = false; trailer = ""; estado = "Cargando…"
        episodios = []; temporada = -1; abierto = -1; fuentes = []; buscando = false; etiqueta = ""
        const pedido = titulo
        App.llamar("detail", { type: titulo.type, tmdbId: titulo.tmdbId }, function (m) {
            if (pedido !== ficha.titulo) return
            if (!m.ok) { ficha.estado = m.error; return }
            ficha.detalle = m.data.detail
            ficha.imdb = m.data.imdb || ""
            ficha.imdbListo = true
            ficha.trailer = m.data.trailer || ""
            ficha.estado = ""
            if (ficha.serie && m.data.detail.seasons.length > 0) {
                // Se abre en la temporada que se estaba viendo, si la hay
                let t = m.data.detail.seasons[0].season
                for (const p of (App.st.progress || []))
                    if (p.tmdbId === ficha.titulo.tmdbId && p.season) { t = p.season; break }
                ficha.temporada = t
            } else if (!ficha.serie) ficha.buscar(ficha.d.title, null, null)
        })
    }
    onTemporadaChanged: {
        abierto = -1
        episodios = []
        if (temporada < 0) return
        const t = temporada
        App.llamar("episodes", { tmdbId: titulo.tmdbId, season: t }, m => { if (t === ficha.temporada) ficha.episodios = m.ok ? m.data : [] })
    }

    function buscar(etq, s, e) {
        busqueda++
        const n = busqueda
        buscando = true
        fuentes = []
        etiqueta = etq
        ctxT = s === null ? -1 : s
        ctxE = e === null ? -1 : e
        App.llamar("fuentes", { title: d.title || titulo.title, type: titulo.type, imdb: imdb || null,
                                season: s, episode: e }, function (m) {
            if (n !== ficha.busqueda) return
            if (!m.ok) { buscando = false; ficha.estado = m.error; return }
            if (!m.fin) { ficha.fuentes = m.data.items; if (m.data.fin) ficha.buscando = false; return }
            ficha.buscando = false
            if (m.data && m.data.error) ficha.estado = m.data.error
            else if (ficha.fuentes.length === 0) ficha.estado = "Sin fuentes"
        })
    }

    // Contexto para el reproductor: marcar visto, reanudar y el siguiente episodio
    function ctx() {
        const s = ctxT > 0 ? ctxT : null, e = ctxE > 0 ? ctxE : null
        const key = serie && s !== null ? "series:" + titulo.tmdbId + ":" + s + ":" + (e || 1) : "movie:" + titulo.tmdbId
        const p = App.progresoDe(key)
        return { tmdbId: titulo.tmdbId, type: titulo.type, season: s, episode: e,
                 name: d.title || titulo.title, poster: d.poster || titulo.poster,
                 resume: p && !p.watched ? p.position : 0, query: d.originalTitle || titulo.title,
                 subtitle: s !== null ? "T" + s + " · E" + e + (nombreEp ? " · " + nombreEp : "") : "" }
    }

    // ----------------------------------------------------------- fondo
    Imagen {
        anchors.top: parent.top
        anchors.right: parent.right
        width: parent.width * 0.72
        height: width * 9 / 16
        source: ficha.d.backdrop || ""
        radio: 0
        anchoFuente: 1280
        opacity: 0.35
        visible: lista
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.25; color: Tema.bg }
            GradientStop { position: 1.0; color: "#00141414" }
        }
    }
    Rectangle {
        anchors.left: parent.left; anchors.right: parent.right
        y: parent.width * 0.72 * 9 / 16 * 0.55
        height: parent.width * 0.72 * 9 / 16 * 0.45 + 2
        gradient: Gradient {
            GradientStop { position: 0; color: "#00141414" }
            GradientStop { position: 1; color: Tema.bg }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Tema.px(24)
        spacing: Tema.px(28)

        // ---------------------------------- carátula y acciones
        ColumnLayout {
            // Ancho FIJO: un texto con fillWidth reclama el ancho de su línea
            // entera sin cortar y, sin tope, la columna se comía la ventana.
            Layout.preferredWidth: Tema.px(230)
            Layout.minimumWidth: Tema.px(230)
            Layout.maximumWidth: Tema.px(230)
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignTop
            spacing: Tema.px(12)
            Boton { id: volverBtn; text: "Volver"; icono: "atras"; tipo: "texto"; onClicked: ficha.volver(); focus: true }
            Imagen {
                Layout.fillWidth: true
                Layout.preferredHeight: Tema.px(230) * 1.5
                source: ficha.d.poster || ""
                alternativo: ficha.d.title || ""
                radio: Tema.px(10)
            }
            Boton {
                visible: ficha.trailer !== ""
                Layout.fillWidth: true
                text: "Tráiler"; icono: "play"; tipo: "acento"
                onClicked: backend.abrirUrl("https://www.youtube.com/watch?v=" + ficha.trailer)
            }
            Boton {
                visible: App.conSesion && App.st.sync.active
                Layout.fillWidth: true
                tipo: "secundario"
                icono: App.esFav(ficha.titulo) ? "corazonLleno" : "corazon"
                text: App.esFav(ficha.titulo) ? "En Mi lista" : "Añadir a Mi lista"
                onClicked: App.llamar("favToggle", { title: {
                    tmdbId: ficha.titulo.tmdbId, title: ficha.d.title, originalTitle: ficha.d.originalTitle || ficha.d.title,
                    year: ficha.d.year || "", poster: ficha.d.poster || null, type: ficha.titulo.type,
                    rating: ficha.d.rating || 0 } }, m => { if (m.ok && m.data.error) App.aviso(m.data.error) })
            }
            Etiqueta {
                visible: !App.conSesion
                Layout.fillWidth: true
                Layout.preferredWidth: 1
                text: "Entra con tu cuenta (Ajustes) para usar Mi lista y seguir por donde ibas en el móvil."
                secundario: true; estilo: "labelSmall"
            }
            Item { Layout.fillHeight: true }
        }

        // ---------------------------------- ficha y enlaces
        Pagina {
            id: derecha
            Layout.fillWidth: true
            Layout.fillHeight: true
            margen: 0

            Etiqueta { text: ficha.d.title || ""; estilo: "headlineMedium"; Layout.fillWidth: true }
            Etiqueta {
                Layout.fillWidth: true
                secundario: true
                estilo: "bodySmall"
                text: [ficha.serie ? "Serie" : "Película", ficha.d.year || "",
                       ficha.d.rating > 0 ? "★ " + ficha.d.rating : "",
                       ficha.detalle && ficha.detalle.runtime ? ficha.detalle.runtime + " min" : "",
                       ficha.detalle ? ficha.detalle.genres.join(" · ") : ""].filter(x => x).join("  ·  ")
            }
            Etiqueta {
                visible: text !== ""
                Layout.fillWidth: true
                Layout.maximumWidth: Tema.px(820)
                text: ficha.detalle ? ficha.detalle.overview : ""
                estilo: "bodyMedium"
                lineHeight: 1.2
            }
            Etiqueta { visible: ficha.estado !== ""; text: ficha.estado; secundario: true; estilo: "bodySmall" }

            // ----------------------------- película
            RowLayout {
                visible: !ficha.serie && ficha.detalle !== null
                Layout.fillWidth: true
                Layout.topMargin: Tema.px(8)
                Etiqueta { text: ficha.buscando ? "Buscando fuentes…" : "Enlaces"; estilo: "titleSmall"; Layout.fillWidth: true }
                Boton {
                    visible: !ficha.buscando
                    text: "Recargar"; icono: "recargar"; tipo: "texto"; compacto: true
                    onClicked: { ficha.estado = ""; ficha.buscar(ficha.d.title, null, null) }
                }
            }
            Fuentes {
                visible: !ficha.serie
                Layout.fillWidth: true
                fuentes: ficha.fuentes
                cargando: ficha.buscando
                etiqueta: ficha.etiqueta
                titulo: ficha.d
                construirCtx: ficha.ctx
            }

            // ----------------------------- serie
            Etiqueta {
                visible: ficha.serie && ficha.detalle !== null
                text: "Temporadas"; estilo: "titleSmall"
                Layout.topMargin: Tema.px(8)
            }
            Flow {
                visible: ficha.serie && ficha.detalle !== null
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Repeater {
                    model: ficha.detalle ? ficha.detalle.seasons : []
                    Chip {
                        required property var modelData
                        text: "T" + modelData.season + " · " + modelData.episodes + " ep."
                        seleccionado: ficha.temporada === modelData.season
                        onClicked: ficha.temporada = modelData.season
                    }
                }
            }
            Etiqueta {
                visible: ficha.serie && ficha.episodios.length > 0
                text: "Pulsa un episodio para ver sus enlaces."
                secundario: true; estilo: "labelSmall"
            }
            Repeater {
                model: ficha.serie ? ficha.episodios : []
                ColumnLayout {
                    id: ep
                    required property var modelData
                    readonly property bool abierto: ficha.abierto === modelData.episode
                    readonly property bool visto: App.vistoEpisodio(ficha.titulo.tmdbId, ficha.temporada, modelData.episode)
                    readonly property var prog: App.progresoDe("series:" + ficha.titulo.tmdbId + ":" + ficha.temporada + ":" + modelData.episode)
                    Layout.fillWidth: true
                    spacing: Tema.px(6)
                    AbstractButton {
                        id: filaEp
                        Layout.fillWidth: true
                        focusPolicy: Qt.StrongFocus
                        hoverEnabled: true
                        padding: Tema.px(10)
                        Keys.onReturnPressed: clicked()
                        onClicked: {
                            if (ep.abierto) { ficha.abierto = -1; return }
                            ficha.abierto = ep.modelData.episode
                            ficha.nombreEp = ep.modelData.name
                            ficha.estado = ""
                            ficha.buscar(ficha.d.title + " · T" + ficha.temporada + "E" + ep.modelData.episode + " · " + ep.modelData.name,
                                         ficha.temporada, ep.modelData.episode)
                        }
                        background: Rectangle {
                            radius: Tema.radioTarjeta
                            color: filaEp.hovered ? Tema.surface2 : Tema.surface1
                            Anillo { activo: filaEp.visualFocus; radio: Tema.radioTarjeta }
                        }
                        contentItem: RowLayout {
                            spacing: Tema.px(14)
                            Imagen {
                                visible: !!ep.modelData.still
                                Layout.preferredWidth: Tema.px(150)
                                Layout.preferredHeight: Tema.px(84)
                                source: ep.modelData.still || ""
                                anchoFuente: 300
                                Barra {
                                    visible: ep.prog !== null && !ep.visto && ep.prog.duration > 0
                                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                                    valor: ep.prog ? ep.prog.position / Math.max(1, ep.prog.duration) : 0
                                    radius: 0
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Tema.px(3)
                                Etiqueta {
                                    Layout.fillWidth: true
                                    text: (ep.visto ? "✓ " : "") + ep.modelData.episode + ". " + ep.modelData.name
                                    color: ep.visto ? Tema.ok : "white"
                                    estilo: "bodyMedium"
                                    font.weight: Font.DemiBold
                                    maximumLineCount: 1
                                    wrapMode: Text.NoWrap
                                }
                                Etiqueta {
                                    visible: text !== ""
                                    Layout.fillWidth: true
                                    text: ep.modelData.overview
                                    secundario: true; estilo: "labelSmall"
                                    maximumLineCount: 2
                                }
                            }
                            Icono { nombre: ep.abierto ? "arriba" : "abajo"; tam: Tema.px(14); color: Tema.muted }
                        }
                    }
                    // Enlaces JUSTO debajo del episodio elegido
                    Fuentes {
                        visible: ep.abierto
                        Layout.fillWidth: true
                        Layout.leftMargin: Tema.px(12)
                        fuentes: ep.abierto ? ficha.fuentes : []
                        cargando: ep.abierto && ficha.buscando
                        etiqueta: ficha.etiqueta
                        titulo: ficha.d
                        construirCtx: ficha.ctx
                    }
                }
            }
            Item { Layout.preferredHeight: Tema.px(24) }
        }
    }
}
