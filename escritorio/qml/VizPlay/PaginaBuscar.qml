import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Buscar por título (SearchScreen). Está también con perfil infantil: sin
// buscador no se puede pedir una serie por su nombre, que es justo lo que se
// quiere hacer con los niños.
Item {
    id: b
    property string tipo: "movie"
    property var resultados: []
    property string estado: ""
    function enfocar() { campo.campo.forceActiveFocus() }

    function buscar() {
        const q = campo.text.trim()
        if (!q) return
        if (!App.st.prefs.tmdbKey) { estado = "Falta la clave de TMDB (Ajustes → Catálogos)."; return }
        estado = "Buscando…"
        resultados = []
        App.llamar("searchText", { query: q, type: tipo }, function (m) {
            resultados = m.ok ? m.data : []
            estado = m.ok ? (resultados.length + " resultados") : m.error
        })
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tema.px(28)
        anchors.topMargin: Tema.px(18)
        spacing: Tema.px(12)
        Etiqueta { text: "Buscar"; estilo: "headlineSmall" }
        RowLayout {
            Layout.fillWidth: true
            spacing: Tema.px(10)
            Campo {
                id: campo
                Layout.fillWidth: true
                Layout.maximumWidth: Tema.px(640)
                placeholder: "Película o serie…"
                onAceptado: b.buscar()
            }
            Segmentado {
                opciones: [["movie", "Películas"], ["series", "Series"]]
                valor: b.tipo
                onElegido: v => { b.tipo = v; if (campo.text.trim()) b.buscar() }
            }
            Boton { text: "Buscar"; icono: "buscar"; onClicked: b.buscar() }
            Item { Layout.fillWidth: true }
        }
        Etiqueta { visible: b.estado !== ""; text: b.estado; secundario: true; estilo: "bodySmall" }
        GridView {
            id: rejilla
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            readonly property int columnas: Math.max(2, Math.floor(width / (Tema.posterGrid + Tema.px(20))))
            cellWidth: Math.floor(width / columnas)
            cellHeight: Math.round(Tema.posterGrid * 1.5) + Tema.px(70)
            model: b.resultados
            keyNavigationEnabled: true
            topMargin: Tema.px(8)
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: BarraScroll {}
            delegate: Item {
                required property var modelData
                required property int index
                width: rejilla.cellWidth
                height: rejilla.cellHeight
                Poster {
                    anchors.horizontalCenter: parent.horizontalCenter
                    y: Tema.px(6)
                    ancho: Tema.posterGrid
                    titulo: modelData
                    visto: App.vistoTitulo(modelData)
                    onClicked: App.abrirFicha(modelData)
                    onActiveFocusChanged: if (activeFocus) rejilla.currentIndex = index
                }
            }
        }
    }
}
