import QtQuick

// Texto con la escala tipográfica de la app (vizTypography). Los títulos van en
// Inter Display, gruesos y con la letra apretada; el cuerpo en Inter normal.
Text {
    id: raiz
    property string estilo: "bodyMedium"
    property bool secundario: false

    readonly property var _e: ({
        "headlineLarge": [Tema.headlineLarge, Font.Black, -0.6, true],
        "headlineMedium": [Tema.headlineMedium, Font.Black, -0.5, true],
        "headlineSmall": [Tema.headlineSmall, Font.Bold, -0.4, true],
        "titleLarge": [Tema.titleLarge, Font.Bold, -0.3, true],
        "titleMedium": [Tema.titleMedium, Font.Bold, -0.2, false],
        "titleSmall": [Tema.titleSmall, Font.Bold, 0, false],
        "bodyLarge": [Tema.bodyLarge, Font.Normal, 0, false],
        "bodyMedium": [Tema.bodyMedium, Font.Normal, 0, false],
        "bodySmall": [Tema.bodySmall, Font.Normal, 0, false],
        "labelLarge": [Tema.labelLarge, Font.Bold, 0.1, false],
        "labelMedium": [Tema.labelMedium, Font.DemiBold, 0, false],
        "labelSmall": [Tema.labelSmall, Font.Medium, 0, false]
    })
    readonly property var _s: _e[estilo] || _e["bodyMedium"]

    color: secundario ? Tema.muted : "white"
    font.family: _s[3] ? Tema.familiaDisplay : Tema.familia
    font.pixelSize: _s[0]
    font.weight: _s[1]
    font.letterSpacing: _s[2]
    wrapMode: Text.WordWrap
    elide: Text.ElideRight
    textFormat: Text.PlainText
}
