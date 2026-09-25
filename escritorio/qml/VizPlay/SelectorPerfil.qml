import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// «¿Quién está viendo?», al estilo de Netflix: avatares grandes en fila.
Dialogo {
    id: d
    titulo: "¿Quién está viendo?"
    ancho: Tema.px(760)
    signal gestionar()
    readonly property var perfiles: (App.st.sync && App.st.sync.profiles) || []

    Etiqueta {
        visible: d.perfiles.length === 0
        text: "Todavía no hay perfiles. Se crean en Ajustes → Cuenta."
        secundario: true; estilo: "bodySmall"
    }
    Flow {
        Layout.fillWidth: true
        Layout.topMargin: Tema.px(8)
        spacing: Tema.px(18)
        Repeater {
            model: d.perfiles
            AbstractButton {
                id: pb
                required property var modelData
                readonly property bool activo: App.st.sync.active && App.st.sync.active.id === modelData.id
                width: Tema.px(120)
                height: colP.implicitHeight
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                focus: activo      // el foco empieza en el perfil activo
                scale: visualFocus || hovered ? 1.06 : 1
                Behavior on scale { NumberAnimation { duration: 120 } }
                onClicked: { App.llamar("profileSelect", { id: modelData.id }); d.close() }
                Keys.onReturnPressed: clicked()
                background: Item {}
                contentItem: Column {
                    id: colP
                    spacing: Tema.px(8)
                    Rectangle {
                        width: Tema.px(120); height: width
                        radius: Tema.radio
                        color: pb.activo ? Tema.surface2 : "#1affffff"
                        border.width: pb.activo ? 2 : 0
                        border.color: Tema.accent
                        Text { anchors.centerIn: parent; text: pb.modelData.avatar; font.pixelSize: Tema.px(56) }
                        Anillo { activo: pb.visualFocus || pb.hovered }
                    }
                    Etiqueta {
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: pb.modelData.name
                        color: pb.activo ? "white" : Tema.muted
                        font.weight: pb.activo ? Font.Bold : Font.Normal
                        maximumLineCount: 1
                    }
                    Etiqueta {
                        visible: pb.modelData.kids
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        text: "Modo infantil"; secundario: true; estilo: "labelSmall"
                    }
                }
            }
        }
    }
    pie: [
        Boton { text: "Cerrar"; tipo: "texto"; onClicked: d.close() },
        Boton { text: "Gestionar perfiles"; tipo: "secundario"; onClicked: { d.close(); d.gestionar() } }
    ]
}
