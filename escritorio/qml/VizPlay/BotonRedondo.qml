import QtQuick
import QtQuick.Controls.Basic

// Botón de icono del reproductor: redondo, sin fondo hasta pasar por encima.
AbstractButton {
    id: b
    property string icono: ""
    property string texto: ""
    property string ayuda: ""
    property bool grande: false
    implicitWidth: grande ? Tema.px(52) : Tema.px(42)
    implicitHeight: implicitWidth
    hoverEnabled: true
    focusPolicy: Qt.NoFocus      // el teclado es del reproductor, no de sus botones
    ToolTip.visible: hovered && ayuda !== ""
    ToolTip.text: ayuda
    ToolTip.delay: 600
    background: Rectangle {
        radius: width / 2
        color: b.down ? "#40ffffff" : (b.hovered ? "#26ffffff" : "transparent")
    }
    contentItem: Item {
        Icono { anchors.centerIn: parent; visible: b.texto === ""; nombre: b.icono; tam: b.grande ? Tema.px(26) : Tema.px(19) }
        Text {
            anchors.centerIn: parent
            visible: b.texto !== ""
            text: b.texto
            color: "white"
            font.family: Tema.familia
            font.weight: Font.Bold
            font.pixelSize: Tema.labelLarge
        }
    }
}
