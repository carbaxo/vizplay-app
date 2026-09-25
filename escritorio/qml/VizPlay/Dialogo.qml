import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// AlertDialog: modal, centrado, con título, cuerpo y botones al pie.
Popup {
    id: d
    property string titulo: ""
    default property alias contenido: cuerpo.data
    property alias pie: botones.data
    property int ancho: Tema.px(520)
    parent: Overlay.overlay
    modal: true
    focus: true
    anchors.centerIn: parent
    width: Math.min(ancho, (parent ? parent.width : ancho) - 48)
    padding: Tema.px(22)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    Overlay.modal: Rectangle { color: "#b3000000" }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 120 } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 100 } }

    background: Rectangle {
        color: Tema.surface1
        radius: Tema.px(16)
        border.color: Tema.outlineVariant
    }
    contentItem: ColumnLayout {
        spacing: Tema.px(14)
        Etiqueta { text: d.titulo; estilo: "titleLarge"; Layout.fillWidth: true; visible: d.titulo !== "" }
        ColumnLayout {
            id: cuerpo
            Layout.fillWidth: true
            spacing: Tema.px(8)
        }
        Flow {
            id: botones
            Layout.fillWidth: true
            Layout.topMargin: Tema.px(4)
            spacing: Tema.px(8)
            layoutDirection: Qt.RightToLeft
        }
    }
}
