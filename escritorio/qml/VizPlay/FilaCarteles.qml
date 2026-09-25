import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Una fila de carátulas con su título (las de Descubrir). La rueda del ratón
// sigue bajando por la página: la fila solo se mueve con las flechas laterales,
// con el teclado o deslizando en horizontal en el panel táctil.
ColumnLayout {
    id: fila
    property string titulo: ""
    property var items: []
    property bool verMas: false
    property bool continuar: false     // tarjetas de «Continuar viendo»
    signal abrir(var t)
    signal pedirMas()
    Layout.fillWidth: true
    spacing: Tema.px(8)

    Etiqueta { text: fila.titulo; estilo: "titleMedium"; Layout.fillWidth: true }

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: lista.height
        HoverHandler { id: sobre }

        ListView {
            id: lista
            width: parent.width
            height: Math.round(Tema.poster * 1.5) + Tema.px(fila.continuar ? 60 : 52) + 2 * margen
            readonly property int margen: Tema.px(10)
            orientation: ListView.Horizontal
            spacing: Tema.px(12)
            interactive: false          // la rueda vertical es de la página
            keyNavigationEnabled: true
            clip: true
            leftMargin: margen; rightMargin: margen; topMargin: margen; bottomMargin: margen
            model: fila.items.length + (fila.verMas ? 1 : 0)
            boundsBehavior: Flickable.StopAtBounds
            Behavior on contentX { enabled: !lista.moving; NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            delegate: Loader {
                required property int index
                sourceComponent: index < fila.items.length ? (fila.continuar ? tarjetaContinuar : tarjeta) : tarjetaMas
                property var dato: index < fila.items.length ? fila.items[index] : null
                onActiveFocusChanged: if (activeFocus && item) item.forceActiveFocus()
            }
            function desplazar(d) {
                const max = Math.max(0, contentWidth - width + leftMargin + rightMargin)
                contentX = Math.max(-leftMargin, Math.min(max - leftMargin, contentX + d))
            }
        }

        // La rueda: lo HORIZONTAL (panel táctil, Mayús+rueda) mueve la fila y lo
        // vertical sigue hasta la página. Con un WheelHandler no se podía: se
        // quedaba con todos los giros aunque se marcaran como no aceptados, y la
        // página dejaba de bajar en cuanto el ratón estaba encima de una fila.
        // Un MouseArea sin botones solo atiende a la rueda: clics y paso del
        // ratón llegan a las carátulas como siempre.
        MouseArea {
            anchors.fill: lista
            acceptedButtons: Qt.NoButton
            onWheel: function (ev) {
                const dx = ev.angleDelta.x !== 0 ? ev.angleDelta.x
                         : ((ev.modifiers & Qt.ShiftModifier) ? ev.angleDelta.y : 0)
                if (dx === 0) { ev.accepted = false; return }
                lista.desplazar(-dx)
            }
        }

        // Flechas laterales, al estilo de Netflix en el navegador
        Repeater {
            model: [-1, 1]
            AbstractButton {
                required property var modelData
                visible: sobre.hovered && (modelData < 0 ? lista.contentX > -lista.leftMargin + 2
                                                         : lista.contentX < lista.contentWidth - lista.width + lista.leftMargin - 2)
                anchors.verticalCenter: parent.verticalCenter
                anchors.verticalCenterOffset: -Tema.px(24)
                x: modelData < 0 ? 0 : parent.width - width
                width: Tema.px(44); height: Math.round(Tema.poster * 1.5)
                focusPolicy: Qt.NoFocus
                hoverEnabled: true
                z: 20
                onClicked: lista.desplazar(modelData * lista.width * 0.8)
                background: Rectangle { color: parent.hovered ? "#cc000000" : "#99000000"; radius: Tema.radio }
                contentItem: Icono { nombre: modelData < 0 ? "izquierda" : "derecha"; tam: Tema.px(22) }
            }
        }
    }

    Component {
        id: tarjeta
        Poster {
            titulo: dato
            visto: App.vistoTitulo(dato)
            onClicked: fila.abrir(dato)
            onActiveFocusChanged: if (activeFocus) lista.currentIndex = parent.index
        }
    }
    Component {
        id: tarjetaContinuar
        Poster {
            titulo: ({ title: dato.name, poster: dato.poster })
            progreso: dato.duration > 0 ? Math.min(1, dato.position / dato.duration) : 0
            subtitulo: dato.season ? ("T" + dato.season + " · E" + dato.episode) : "Película"
            onClicked: fila.abrir(dato)
            onActiveFocusChanged: if (activeFocus) lista.currentIndex = parent.index
        }
    }
    Component {
        id: tarjetaMas
        AbstractButton {
            id: mas
            width: Tema.poster
            height: Math.round(Tema.poster * 1.5)
            focusPolicy: Qt.StrongFocus
            hoverEnabled: true
            scale: (visualFocus || hovered) ? 1.06 : 1
            Behavior on scale { NumberAnimation { duration: 120 } }
            onClicked: fila.pedirMas()
            Keys.onReturnPressed: clicked()
            background: Rectangle {
                radius: Tema.radioTarjeta
                color: Tema.surface1
                Anillo { activo: mas.visualFocus || mas.hovered; radio: Tema.radioTarjeta }
            }
            contentItem: Etiqueta {
                text: "Ver más ›"
                color: Tema.accent
                estilo: "labelLarge"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
