import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Explorar una plataforma o un género en rejilla paginada (BrowseScreen).
Item {
    id: e
    property var filtro: ({})
    property string tipo: "movie"
    property var items: []
    property int pagina: 0
    property bool cargando: false
    property bool fin: false
    signal volver()

    function siguiente() {
        if (cargando || fin) return
        cargando = true
        const n = pagina + 1
        App.llamar("discover", { type: tipo, provider: filtro.provider || null, genre: filtro.genre || null,
                                 page: n, kids: App.kids }, function (m) {
            cargando = false
            if (!m.ok || m.data.length === 0) { fin = true; return }
            pagina = n
            items = items.concat(m.data)
        })
    }
    Component.onCompleted: siguiente()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tema.px(20)
        spacing: Tema.px(12)
        RowLayout {
            spacing: Tema.px(12)
            Boton { text: "Volver"; icono: "atras"; tipo: "texto"; onClicked: e.volver() }
            Etiqueta { text: e.filtro.name || ""; estilo: "titleLarge" }
        }
        GridView {
            id: rejilla
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            readonly property int columnas: Math.max(2, Math.floor(width / (Tema.posterGrid + Tema.px(20))))
            cellWidth: Math.floor(width / columnas)
            cellHeight: Math.round(Tema.posterGrid * 1.5) + Tema.px(70)
            model: e.items
            keyNavigationEnabled: true
            topMargin: Tema.px(8)
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: BarraScroll {}
            // Al llegar abajo, la página siguiente
            onAtYEndChanged: if (atYEnd && e.items.length > 0) e.siguiente()
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
            footer: Item {
                width: rejilla.width
                height: Tema.px(70)
                Etiqueta {
                    anchors.centerIn: parent
                    text: e.cargando ? "Cargando…" : (e.fin ? "No hay más resultados" : "")
                    secundario: true
                    estilo: "bodySmall"
                }
            }
        }
    }
}
