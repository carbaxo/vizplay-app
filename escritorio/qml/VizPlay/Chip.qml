import QtQuick
import QtQuick.Controls.Basic

// FilterChip de Material, al estilo de la app: el seleccionado con fondo blanco
// translúcido y una marca; los demás, solo con borde.
AbstractButton {
    id: c
    property bool seleccionado: false
    property string icono: ""
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    padding: Tema.px(6)
    leftPadding: Tema.px(12)
    rightPadding: Tema.px(12)
    scale: c.visualFocus ? 1.06 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }
    z: c.visualFocus ? 2 : 0
    Keys.onReturnPressed: c.clicked()
    Keys.onEnterPressed: c.clicked()

    background: Rectangle {
        implicitHeight: Tema.px(32)
        radius: Tema.px(8)
        color: c.seleccionado ? Tema.chipSel : (c.hovered ? "#14ffffff" : "transparent")
        border.width: c.seleccionado ? 0 : 1
        border.color: Tema.outline
        Anillo { activo: c.visualFocus; radio: Tema.px(8) }
    }
    contentItem: Row {
        spacing: Tema.px(6)
        Icono {
            visible: c.seleccionado || c.icono !== ""
            nombre: c.seleccionado ? "ok" : c.icono
            tam: Tema.px(12)
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: c.text
            color: "white"
            font.family: Tema.familia
            font.weight: Font.DemiBold
            font.pixelSize: Tema.labelLarge
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
