import QtQuick

// El logotipo: VIZ en blanco y PLAY en granate, en Inter Display Black y con la
// letra apretada. En un solo sitio para que no puedan quedar distintos.
Text {
    property int tam: Tema.titleLarge
    textFormat: Text.StyledText
    text: "VIZ<font color='" + Tema.accentDeep + "'>PLAY</font>"
    color: "white"
    font.family: Tema.familiaDisplay
    font.weight: Font.Black
    font.pixelSize: tam
    font.letterSpacing: -0.04 * tam
}
