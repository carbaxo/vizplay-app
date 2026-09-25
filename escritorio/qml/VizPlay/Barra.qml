import QtQuick

// LinearProgressIndicator. valor 0..1; `indeterminada` para "no se sabe cuánto".
Rectangle {
    id: b
    property real valor: 0
    property bool indeterminada: false
    property color tinta: Tema.accent
    implicitHeight: Tema.px(4)
    radius: height / 2
    color: "#33ffffff"
    clip: true
    Rectangle {
        visible: !b.indeterminada
        height: parent.height
        radius: parent.radius
        width: parent.width * Math.max(0, Math.min(1, b.valor))
        color: b.tinta
    }
    Rectangle {
        id: onda
        visible: b.indeterminada
        height: parent.height
        width: parent.width * 0.3
        radius: parent.radius
        color: b.tinta
        NumberAnimation on x {
            running: b.indeterminada && b.visible
            from: -onda.width; to: b.width
            duration: 1200; loops: Animation.Infinite
        }
    }
}
