import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Fila con texto + explicación y un Switch a la derecha (como en Ajustes de Android).
RowLayout {
    id: r
    property alias checked: sw.checked
    property string texto: ""
    property string ayuda: ""
    signal cambiado(bool valor)
    Layout.fillWidth: true
    spacing: Tema.px(12)
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        Etiqueta { text: r.texto; Layout.fillWidth: true }
        Etiqueta { visible: r.ayuda !== ""; text: r.ayuda; estilo: "labelSmall"; secundario: true; Layout.fillWidth: true }
    }
    Switch {
        id: sw
        focusPolicy: Qt.StrongFocus
        onToggled: r.cambiado(checked)
        indicator: Rectangle {
            implicitWidth: Tema.px(44); implicitHeight: Tema.px(24)
            radius: height / 2
            color: sw.checked ? "white" : "#40ffffff"
            border.color: Tema.outline
            Rectangle {
                width: parent.height - 6; height: width; radius: width / 2
                y: 3
                x: sw.checked ? parent.width - width - 3 : 3
                color: sw.checked ? "black" : Tema.muted
                Behavior on x { NumberAnimation { duration: 120 } }
            }
            Anillo { activo: sw.visualFocus; radio: height / 2 }
        }
        contentItem: Item {}
    }
}
