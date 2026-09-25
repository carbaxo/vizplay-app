import QtQuick
import QtQuick.Effects

// Imagen remota con las esquinas redondeadas (Image no sabe hacerlo sola) y un
// hueco gris con el título mientras carga o si no hay carátula.
Item {
    id: r
    property url source
    property int radio: Tema.radio
    property string alternativo: ""
    property int fillMode: Image.PreserveAspectCrop
    property int anchoFuente: 342
    readonly property bool lista: img.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: r.radio
        color: Tema.surface2
        visible: !r.lista
        Etiqueta {
            anchors.fill: parent
            anchors.margins: Tema.px(8)
            text: r.alternativo
            estilo: "labelMedium"
            secundario: true
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            maximumLineCount: 4
        }
    }
    Image {
        id: img
        anchors.fill: parent
        source: r.source
        asynchronous: true
        cache: true
        fillMode: r.fillMode
        sourceSize.width: r.anchoFuente
        visible: false
        smooth: true
        mipmap: true
    }
    Rectangle {
        id: mascara
        anchors.fill: parent
        radius: r.radio
        visible: false
        layer.enabled: true
        layer.smooth: true
    }
    MultiEffect {
        anchors.fill: parent
        source: img
        visible: r.lista
        maskEnabled: true
        maskSource: mascara
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
    }
}
