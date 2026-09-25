pragma Singleton
import QtQuick

// Aspecto de VizPlay, el MISMO que la app de Android TV (Theme.kt): fondo casi
// negro, texto blanco con gris claro para lo secundario, rojo reservado para lo
// importante, botones rectos (el principal blanco con texto negro) y títulos
// gruesos y apretados, en Inter.
//
// `k` es la escala de la letra: 1 en el escritorio y 1.15 con «Modo tele»
// (Ajustes → Apariencia), para un PC conectado a la tele del salón.
QtObject {
    property real k: 1.0

    // ------------------------------------------------------------ colores
    readonly property color bg: "#141414"          // fondo de Netflix, no negro puro
    readonly property color surface1: "#202020"    // tarjetas y hojas
    readonly property color surface2: "#2a2a2a"
    readonly property color muted: "#b3b3b3"       // secundario: gris CLARO, se lee de lejos
    readonly property color dim: "#808080"         // secciones no activas
    readonly property color accent: "#e50914"      // lo que debe llamar la atención
    readonly property color accentDeep: "#c41e3a"  // el PLAY del logotipo
    readonly property color ok: "#34d399"
    readonly property color warn: "#fbbf24"
    readonly property color outline: "#59ffffff"   // borde de los botones secundarios
    readonly property color outlineVariant: "#26ffffff"
    readonly property color chipSel: "#33ffffff"   // chip seleccionado
    readonly property color ring: "#ffffff"        // anillo de foco: blanco puro
    readonly property color ringSoft: "#33ffffff"
    readonly property color castBar: "#1b2a25"

    // Esquina de botones y carátulas: casi recto, como Netflix
    readonly property int radio: 4
    readonly property int radioTarjeta: 10

    readonly property string familia: "Inter"
    readonly property string familiaDisplay: "Inter Display"
    readonly property string iconos: "Segoe MDL2 Assets"

    function px(v) { return Math.round(v * k) }

    // --------------------------------------- escala tipográfica (vizTypography)
    readonly property int headlineLarge: px(30)
    readonly property int headlineMedium: px(26)
    readonly property int headlineSmall: px(23)
    readonly property int titleLarge: px(20)
    readonly property int titleMedium: px(17)
    readonly property int titleSmall: px(15)
    readonly property int bodyLarge: px(16)
    readonly property int bodyMedium: px(14)
    readonly property int bodySmall: px(13)
    readonly property int labelLarge: px(14)
    readonly property int labelMedium: px(12)
    readonly property int labelSmall: px(11)

    // Anchos de carátula (en la tele 165, en el móvil 120; el PC va con la tele)
    readonly property int poster: px(165)
    readonly property int posterGrid: px(150)
}
