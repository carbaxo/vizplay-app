import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Página con desplazamiento vertical y su barra fina. El contenido va en una
// columna con el margen de la app.
Flickable {
    id: f
    default property alias contenido: col.data
    property int margen: Tema.px(28)
    property int ancho: width
    contentWidth: width
    contentHeight: col.implicitHeight + 2 * Tema.px(18)
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickDeceleration: 4000
    maximumFlickVelocity: 5000
    ScrollBar.vertical: BarraScroll {}
    // Lleva a la vista lo que coge el foco con el teclado
    function asegurarVisible(item) {
        if (!item) return
        const p = item.mapToItem(col, 0, 0)
        if (p.y < contentY) contentY = Math.max(0, p.y - Tema.px(20))
        else if (p.y + item.height > contentY + height)
            contentY = Math.min(contentHeight - height, p.y + item.height - height + Tema.px(20))
    }
    Connections {
        target: f.Window.window
        function onActiveFocusItemChanged() {
            const it = f.Window.window ? f.Window.window.activeFocusItem : null
            if (it && f.visible && f.contentItem && isAncestor(f.contentItem, it)) f.asegurarVisible(it)
        }
    }
    function isAncestor(a, b) {
        for (let x = b; x; x = x.parent) if (x === a) return true
        return false
    }
    ColumnLayout {
        id: col
        x: f.margen
        y: Tema.px(18)
        width: Math.min(f.width - 2 * f.margen, f.ancho)
        spacing: Tema.px(14)
    }
}
