import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// La carátula de las filas (PosterCard / ContinueCard de Android): imagen 2:3,
// «✓ Visto» si ya se vio, título y año · nota. Con `progreso` >= 0 lleva la
// barra roja de «Continuar viendo». Al enfocar (teclado) o pasar el ratón, el
// anillo blanco y el pequeño zoom de la tele.
AbstractButton {
    id: p
    property var titulo: ({})
    property int ancho: Tema.poster
    property real progreso: -1
    property string subtitulo: ""
    property bool visto: false
    readonly property bool resaltado: p.visualFocus || p.activeFocus || p.hovered

    implicitWidth: ancho
    implicitHeight: col.implicitHeight
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    scale: resaltado ? 1.06 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }
    z: resaltado ? 5 : 0
    Keys.onReturnPressed: clicked()
    Keys.onEnterPressed: clicked()
    Keys.onSpacePressed: clicked()

    background: Item {}
    contentItem: Column {
        id: col
        spacing: Tema.px(6)
        Item {
            width: p.ancho
            height: Math.round(p.ancho * 1.5)
            Imagen {
                anchors.fill: parent
                source: p.titulo.poster || ""
                alternativo: p.titulo.title || p.titulo.name || ""
            }
            Rectangle {
                visible: p.visto
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: Tema.px(6)
                radius: Tema.px(6)
                color: "#cc34d399"
                width: vt.implicitWidth + Tema.px(12)
                height: vt.implicitHeight + Tema.px(4)
                Etiqueta { id: vt; anchors.centerIn: parent; text: "✓ Visto"; estilo: "labelSmall" }
            }
            Anillo { activo: p.resaltado }
        }
        Barra {
            visible: p.progreso >= 0
            width: p.ancho
            valor: p.progreso
        }
        Etiqueta {
            width: p.ancho
            text: p.titulo.title || p.titulo.name || ""
            estilo: "bodySmall"
            maximumLineCount: 1
            wrapMode: Text.NoWrap
        }
        Etiqueta {
            width: p.ancho
            visible: text !== ""
            text: p.subtitulo !== "" ? p.subtitulo
                  : ((p.titulo.year || "") + (p.titulo.rating > 0 ? "  ★ " + p.titulo.rating : ""))
            estilo: "labelSmall"
            secundario: true
            maximumLineCount: 1
            wrapMode: Text.NoWrap
        }
    }
}
