import QtQuick
import QtQuick.Controls.Basic

// OutlinedTextField de Material: la etiqueta encima y borde que se vuelve blanco
// al escribir. `clave` oculta el texto y añade el ojo para verlo.
Column {
    id: c
    property alias text: campo.text
    property alias placeholder: campo.placeholderText
    property string etiqueta: ""
    property bool clave: false
    property bool multilinea: false
    property alias campo: campo
    signal aceptado()
    spacing: Tema.px(4)

    Etiqueta {
        visible: c.etiqueta !== ""
        text: c.etiqueta
        estilo: "labelMedium"
        secundario: true
    }
    TextField {
        id: campo
        property bool ver: false
        width: parent.width
        color: "white"
        font.family: Tema.familia
        font.pixelSize: Tema.bodyMedium
        placeholderTextColor: "#80ffffff"
        selectByMouse: true
        selectionColor: Tema.accentDeep
        echoMode: c.clave && !ver ? TextInput.Password : TextInput.Normal
        leftPadding: Tema.px(12)
        rightPadding: c.clave ? Tema.px(40) : Tema.px(12)
        topPadding: Tema.px(10)
        bottomPadding: Tema.px(10)
        onAccepted: c.aceptado()
        background: Rectangle {
            radius: Tema.radio
            color: "#0dffffff"
            border.width: campo.activeFocus ? 2 : 1
            border.color: campo.activeFocus ? "white" : Tema.outline
        }
        AbstractButton {
            visible: c.clave
            anchors.right: parent.right
            anchors.rightMargin: Tema.px(6)
            anchors.verticalCenter: parent.verticalCenter
            width: Tema.px(30); height: width
            focusPolicy: Qt.NoFocus
            onClicked: campo.ver = !campo.ver
            contentItem: Icono { nombre: campo.ver ? "ocultar" : "ver"; color: campo.ver ? "white" : Tema.muted; tam: Tema.px(15) }
            ToolTip.visible: hovered
            ToolTip.text: campo.ver ? "Ocultar" : "Ver lo escrito"
        }
    }
}
