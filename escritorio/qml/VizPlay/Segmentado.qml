import QtQuick
import QtQuick.Controls.Basic

// El selector Películas / Series: un marco con borde y la opción elegida
// resaltada dentro. `opciones` = [[valor, etiqueta], …]
Rectangle {
    id: s
    property var opciones: []
    property string valor: ""
    signal elegido(string valor)

    implicitWidth: fila.implicitWidth + 8
    implicitHeight: Tema.px(38)
    radius: Tema.px(8)
    color: "transparent"
    border.width: 1
    border.color: Tema.outline

    Row {
        id: fila
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: s.opciones
            AbstractButton {
                id: o
                required property var modelData
                readonly property bool sel: s.valor === modelData[0]
                height: s.height - 8
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                leftPadding: Tema.px(16)
                rightPadding: Tema.px(16)
                onClicked: s.elegido(modelData[0])
                Keys.onReturnPressed: clicked()
                background: Rectangle {
                    radius: Tema.px(6)
                    color: o.sel ? Tema.chipSel : (o.hovered ? "#14ffffff" : "transparent")
                    Anillo { activo: o.visualFocus; radio: Tema.px(6) }
                }
                contentItem: Row {
                    spacing: Tema.px(6)
                    Icono { visible: o.sel; nombre: "ok"; tam: Tema.px(12); anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: o.modelData[1]
                        color: o.sel ? "white" : Tema.muted
                        font.family: Tema.familia
                        font.weight: o.sel ? Font.Bold : Font.DemiBold
                        font.pixelSize: Tema.labelLarge
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
}
