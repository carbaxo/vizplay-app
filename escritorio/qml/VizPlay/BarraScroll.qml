import QtQuick
import QtQuick.Controls.Basic

// Barra de desplazamiento fina: solo aparece mientras se usa y si hay algo que
// desplazar (el estilo Basic la dejaba pintada aunque todo cupiera).
ScrollBar {
    id: sb
    policy: ScrollBar.AsNeeded
    minimumSize: 0.08
    contentItem: Rectangle {
        implicitWidth: 6
        radius: 3
        color: sb.pressed ? "#99ffffff" : "#55ffffff"
        opacity: sb.size < 1.0 && (sb.active || sb.hovered) ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
    }
    background: Item {}
}
