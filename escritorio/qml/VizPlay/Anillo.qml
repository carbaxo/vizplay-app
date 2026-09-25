import QtQuick

// El anillo de foco de la tele (TvUi.kt): blanco grueso, fuera del elemento.
// Es lo que sitúa cuando se maneja con el teclado o un mando, y con el ratón
// marca qué se va a pulsar.
Rectangle {
    property bool activo: false
    property int radio: Tema.radio
    anchors.fill: parent
    anchors.margins: -4
    radius: radio + 3
    color: "transparent"
    border.width: 3
    border.color: Tema.ring
    visible: activo
    z: 10
}
