import QtQuick
import QtQuick.Controls.Basic

// Botón de VizPlay. Como en Netflix:
//  - "primario": BLANCO con texto negro (el «Reproducir»).
//  - "secundario": borde blanco translúcido sobre transparente.
//  - "texto": sin fondo, para acciones menores.
//  - "acento": rojo, solo para lo que de verdad debe llamar la atención.
// Esquina casi recta (4 px) y el anillo de foco blanco + zoom de la tele.
Button {
    id: b
    property string tipo: "primario"
    property string icono: ""
    property bool cargando: false
    property bool compacto: false

    readonly property bool resaltado: b.visualFocus || b.hovered
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    padding: compacto ? Tema.px(6) : Tema.px(9)
    leftPadding: compacto ? Tema.px(10) : Tema.px(16)
    rightPadding: leftPadding
    scale: b.visualFocus ? 1.06 : 1.0
    Behavior on scale { NumberAnimation { duration: 120 } }
    z: b.visualFocus ? 2 : 0

    Keys.onReturnPressed: b.clicked()
    Keys.onEnterPressed: b.clicked()

    readonly property color _fondo: {
        if (!b.enabled) return tipo === "primario" ? "#66ffffff" : "transparent"
        if (tipo === "primario") return b.down ? "#cccccc" : (b.hovered ? "#e6e6e6" : "#ffffff")
        if (tipo === "acento") return b.down ? "#b20710" : (b.hovered ? "#f6121d" : Tema.accent)
        if (tipo === "texto") return b.hovered ? Tema.ringSoft : "transparent"
        return b.down ? "#40ffffff" : (b.hovered ? "#1affffff" : "transparent")
    }
    readonly property color _tinta: tipo === "primario" ? (b.enabled ? "#000000" : "#555555")
                                                     : (b.enabled ? "#ffffff" : "#80ffffff")

    background: Rectangle {
        implicitHeight: b.compacto ? Tema.px(30) : Tema.px(38)
        radius: Tema.radio
        color: b._fondo
        border.width: b.tipo === "secundario" ? 1 : 0
        border.color: b.hovered ? "#b3ffffff" : Tema.outline
        Anillo { activo: b.visualFocus }
    }

    contentItem: Row {
        spacing: Tema.px(8)
        BusyIndicator {
            visible: b.cargando
            running: b.cargando
            width: Tema.px(16); height: width
            anchors.verticalCenter: parent.verticalCenter
        }
        Icono {
            visible: b.icono !== "" && !b.cargando
            nombre: b.icono
            color: b._tinta
            tam: Tema.px(15)
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: b.text
            color: b._tinta
            font.family: Tema.familia
            font.weight: Font.Bold
            font.pixelSize: b.compacto ? Tema.labelMedium : Tema.labelLarge
            font.letterSpacing: 0.1
            anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
        }
    }
}
