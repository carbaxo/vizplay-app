import QtQuick
import QtQuick.Layouts

// Card de Surface1 con título. El contenido va en una columna con separación.
Rectangle {
    id: t
    property string titulo: ""
    default property alias contenido: col.data
    property alias cabecera: extra.data
    property int relleno: Tema.px(16)
    color: Tema.surface1
    radius: Tema.radioTarjeta
    implicitHeight: col.implicitHeight + 2 * relleno
    Layout.fillWidth: true

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: t.relleno
        spacing: Tema.px(8)
        RowLayout {
            visible: t.titulo !== "" || extra.children.length > 0
            Layout.fillWidth: true
            Etiqueta { text: t.titulo; estilo: "titleSmall"; Layout.fillWidth: true }
            // Controles junto al título (p. ej. «Actualizar»)
            Row { id: extra; spacing: Tema.px(6) }
        }
    }
}
