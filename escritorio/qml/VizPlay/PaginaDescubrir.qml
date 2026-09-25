import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Descubrir (DiscoverScreen). El selector Películas / Series manda en TODA la
// pantalla: «Continuar viendo», «Mi lista» y «Recomendado para ti» muestran
// solo lo del tipo elegido.
Item {
    id: pag
    property string tipo: "movie"
    property var filas: []
    property string estado: ""
    property var recs: []
    property var avisos: []
    // Explorar una plataforma o un género en rejilla: {provider|genre, name}
    property var explorar: null
    property bool avisosPedidos: false

    readonly property var generos: tipo === "movie"
        ? [[28, "Acción"], [35, "Comedia"], [18, "Drama"], [27, "Terror"], [878, "Ciencia ficción"],
           [16, "Animación"], [53, "Thriller"], [10749, "Romance"], [12, "Aventura"], [80, "Crimen"],
           [99, "Documental"], [14, "Fantasía"]]
        : [[10759, "Acción y aventura"], [35, "Comedia"], [18, "Drama"], [16, "Animación"], [80, "Crimen"],
           [9648, "Misterio"], [10765, "Ciencia ficción y fantasía"], [99, "Documental"], [10751, "Familia"]]

    readonly property var continuar: {
        const out = []
        for (const p of (App.st.progress || [])) {
            if (p.type !== tipo || p.watched || p.position <= 20) continue
            if (p.duration > 0 && p.position / p.duration >= 0.95) continue
            out.push(p)
        }
        out.sort((a, b) => a.updatedAt < b.updatedAt ? 1 : -1)
        return out
    }
    readonly property var miLista: (App.st.favorites || []).filter(f => f.type === tipo)

    function cargar() {
        if (!App.st.prefs.tmdbKey) { filas = []; estado = ""; return }
        estado = "Cargando catálogos…"
        filas = []
        const t = tipo
        App.llamar("catalogs", { type: t, kids: App.kids }, function (m) {
            if (t !== pag.tipo) return
            filas = m.ok ? m.data : []
            estado = m.ok ? "" : m.error
        })
    }
    function cargarRecs() {
        if (!App.st.prefs.tmdbKey || App.kids) { recs = []; return }
        const t = tipo
        App.llamar("recs", { type: t }, function (m) { if (t === pag.tipo) recs = m.ok ? m.data : [] })
    }
    onTipoChanged: { cargar(); cargarRecs() }
    Component.onCompleted: { cargar(); cargarRecs() }
    Connections {
        target: App
        function onKidsChanged() { pag.cargar(); pag.cargarRecs() }
    }
    // Las recomendaciones se recalculan con lo que se va viendo y guardando
    property int nProg: (App.st.progress || []).length
    property int nFav: (App.st.favorites || []).length
    onNProgChanged: recsTimer.restart()
    onNFavChanged: {
        recsTimer.restart()
        // Avisos de episodios nuevos: una vez por sesión, cuando llega Mi lista
        if (nFav > 0 && !avisosPedidos) {
            avisosPedidos = true
            App.llamar("alerts", {}, m => { if (m.ok) pag.avisos = m.data })
        }
    }
    Timer { id: recsTimer; interval: 1500; onTriggered: pag.cargarRecs() }
    property bool claveTmdb: App.st.prefs.tmdbKey
    onClaveTmdbChanged: { cargar(); cargarRecs() }

    Pagina {
        id: pagina
        anchors.fill: parent
        visible: pag.explorar === null

        RowLayout {
            Layout.fillWidth: true
            spacing: Tema.px(16)
            Etiqueta { text: "Descubrir"; estilo: "headlineSmall"; Layout.fillWidth: true }
            Segmentado {
                opciones: [["movie", "Películas"], ["series", "Series"]]
                valor: pag.tipo
                onElegido: v => pag.tipo = v
            }
        }

        // Sin clave de TMDB no hay catálogos: decirlo y llevar a donde se arregla
        Tarjeta {
            visible: !App.st.prefs.tmdbKey
            titulo: "Falta la clave de TMDB"
            Etiqueta {
                Layout.fillWidth: true
                secundario: true
                estilo: "bodySmall"
                text: "Los catálogos, las carátulas y las fichas salen de TMDB, que pide una clave gratuita. En la app de Android va dentro del APK; aquí se pega una vez en Ajustes."
            }
            Boton { text: "Ir a Ajustes"; onClicked: App.irA(3) }
        }

        // Géneros (fuera en modo infantil: solo catálogos familiares)
        ColumnLayout {
            visible: App.st.prefs.tmdbKey && !App.kids
            Layout.fillWidth: true
            spacing: Tema.px(6)
            Etiqueta { text: "Géneros"; estilo: "labelMedium"; secundario: true }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Repeater {
                    model: pag.generos
                    Chip {
                        required property var modelData
                        text: modelData[1]
                        onClicked: pag.explorar = { genre: modelData[0], name: modelData[1] }
                    }
                }
            }
        }

        Etiqueta { visible: pag.estado !== ""; text: pag.estado; secundario: true; estilo: "bodySmall" }

        // Episodios nuevos de las series de Mi lista
        Repeater {
            model: pag.avisos
            Rectangle {
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: filaAviso.implicitHeight + Tema.px(20)
                radius: Tema.radioTarjeta
                color: "#2ee50914"
                RowLayout {
                    id: filaAviso
                    anchors.fill: parent
                    anchors.margins: Tema.px(10)
                    spacing: Tema.px(12)
                    Etiqueta { text: "🔔"; estilo: "titleMedium" }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Etiqueta { text: modelData.title; estilo: "titleSmall" }
                        Etiqueta { text: modelData.text; estilo: "labelSmall"; secundario: true }
                    }
                    Boton {
                        text: "Ver"; compacto: true
                        onClicked: App.abrirFicha({ tmdbId: modelData.tmdbId, title: modelData.title,
                                                    originalTitle: modelData.title, year: "", poster: modelData.poster,
                                                    rating: 0, type: "series" })
                    }
                    Boton {
                        text: "Cerrar"; tipo: "texto"; compacto: true
                        onClicked: pag.avisos = pag.avisos.filter(a => a.tmdbId !== modelData.tmdbId)
                    }
                }
            }
        }

        FilaCarteles {
            visible: pag.continuar.length > 0
            titulo: "Continuar viendo"
            items: pag.continuar
            continuar: true
            onAbrir: p => App.abrirFicha({ tmdbId: p.tmdbId, title: p.name, originalTitle: p.name, year: "",
                                           poster: p.poster, rating: 0, type: p.type })
        }
        FilaCarteles {
            visible: pag.miLista.length > 0
            titulo: "Mi lista"
            items: pag.miLista
            onAbrir: t => App.abrirFicha(t)
        }
        FilaCarteles {
            visible: pag.recs.length > 0 && !App.kids
            titulo: "Recomendado para ti"
            items: pag.recs
            onAbrir: t => App.abrirFicha(t)
        }
        Repeater {
            model: pag.filas
            FilaCarteles {
                required property var modelData
                titulo: modelData.name
                items: modelData.items
                verMas: true
                onAbrir: t => App.abrirFicha(t)
                onPedirMas: pag.explorar = { provider: modelData.provider, name: modelData.name }
            }
        }
        Item { Layout.preferredHeight: Tema.px(12) }
    }

    Loader {
        anchors.fill: parent
        active: pag.explorar !== null
        sourceComponent: PaginaExplorar {
            filtro: pag.explorar
            tipo: pag.tipo
            onVolver: pag.explorar = null
        }
    }
    function atras() {
        if (explorar !== null) { explorar = null; return true }
        return false
    }
}
