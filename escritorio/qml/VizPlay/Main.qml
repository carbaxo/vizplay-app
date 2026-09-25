import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Window
import QtCore

// Ventana principal, con la disposición de VizPlay en la TELE: las secciones en
// una barra a la izquierda (siempre se ve dónde estás) y el perfil activo al
// fondo. La ficha se abre en el hueco de la derecha y el reproductor ocupa la
// ventana entera.
ApplicationWindow {
    id: ventana
    width: 1400
    height: 880
    minimumWidth: 1024
    minimumHeight: 640
    visible: true
    title: "VizPlay"
    color: Tema.bg

    Settings {
        category: "ventana"
        property alias x: ventana.x
        property alias y: ventana.y
        property alias width: ventana.width
        property alias height: ventana.height
    }

    // La posición se recuerda, pero si ya no cae en ninguna pantalla (se ha
    // quitado un monitor, o quedó guardada una fuera de sitio) la ventana se
    // abría invisible. Se comprueba al arrancar y, si hace falta, se centra.
    Component.onCompleted: {
        const pantallas = Qt.application.screens
        let visible = false
        for (let i = 0; i < pantallas.length; i++) {
            const s = pantallas[i]
            const cx = x + Math.min(width, 200) / 2, cy = y + 20
            if (cx >= s.virtualX && cx < s.virtualX + s.width && cy >= s.virtualY && cy < s.virtualY + s.height) { visible = true; break }
        }
        if (!visible && pantallas.length > 0) {
            const s = pantallas[0]
            width = Math.min(width, s.desktopAvailableWidth - 40)
            height = Math.min(height, s.desktopAvailableHeight - 60)
            x = s.virtualX + Math.max(0, (s.width - width) / 2)
            y = s.virtualY + Math.max(0, (s.height - height) / 2)
        }
    }

    Binding { target: Tema; property: "k"; value: App.st.prefs && App.st.prefs.bigText ? 1.15 : 1.0 }

    property int pagina: 0
    property var ficha: null          // título abierto en la ficha
    property var reproduciendo: null  // contexto del reproductor
    property var preguntar: null      // ctx pendiente de «¿con qué lo abrimos?»
    readonly property var secciones: [["inicio", "Descubrir"], ["buscar", "Buscar"], ["descargar", "Descargas"], ["ajustes", "Ajustes"]]

    Connections {
        target: App
        function onAbrirFicha(t) { ventana.ficha = t }
        function onIrA(p) { ventana.ficha = null; ventana.pagina = p }
        function onAviso(t) { toast.mostrar(t) }
        function onReproducir(c) { ventana.reproducir(c) }
    }

    // Con qué se reproduce, según Ajustes → Reproducción
    function reproducir(c) {
        const modo = App.st.prefs.playerMode
        if (modo === "vlc" && App.st.vlc) return externo(c)
        if (modo === "ask" && App.st.vlc) { preguntar = c; dialogoReproductor.open(); return }
        reproduciendo = c
    }
    function externo(c) {
        App.llamar("externalPlayer", { url: c.url, name: c.name, resume: c.resume || 0 }, m => {
            const err = m.ok ? m.data.error : m.error
            toast.mostrar(err || "Abierto en VLC")
        })
    }

    function atras() {
        if (reproduciendo) return
        // Con un diálogo abierto, Esc es SUYO (lo cierra): no se vuelve atrás además
        const capa = ventana.Overlay.overlay
        if (capa) for (let i = 0; i < capa.children.length; i++) if (capa.children[i].visible) return
        if (ficha) { ficha = null; return }
        if (pagina === 0 && descubrir.item && descubrir.item.atras()) return
        pagina = 0
    }

    Shortcut { sequences: [StandardKey.Back, "Esc", "Backspace"]; enabled: !ventana.reproduciendo && !(ventana.activeFocusItem instanceof TextInput); onActivated: ventana.atras() }
    Shortcut { sequence: "Ctrl+F"; enabled: !ventana.reproduciendo; onActivated: { ventana.ficha = null; ventana.pagina = 1; buscar.item && buscar.item.enfocar() } }
    Repeater {
        model: 4
        Item {
            required property int index
            Shortcut {
                sequence: "Ctrl+" + (index + 1)
                enabled: !ventana.reproduciendo
                onActivated: { ventana.ficha = null; ventana.pagina = index }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        visible: !ventana.reproduciendo

        // --------------------------------------------- barra de secciones
        Rectangle {
            Layout.preferredWidth: Tema.px(220)
            Layout.fillHeight: true
            color: Tema.surface1
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Tema.px(18)
                anchors.rightMargin: Tema.px(10)
                spacing: Tema.px(6)
                Wordmark { tam: Tema.headlineSmall; Layout.bottomMargin: Tema.px(18); Layout.leftMargin: Tema.px(8) }
                Repeater {
                    model: ventana.secciones
                    AbstractButton {
                        id: sec
                        required property var modelData
                        required property int index
                        readonly property bool activa: ventana.pagina === index && !ventana.ficha
                        Layout.fillWidth: true
                        focusPolicy: Qt.StrongFocus
                        hoverEnabled: true
                        padding: Tema.px(12)
                        onClicked: { ventana.ficha = null; ventana.pagina = index }
                        Keys.onReturnPressed: clicked()
                        background: Rectangle {
                            radius: Tema.radioTarjeta
                            color: sec.visualFocus || sec.hovered ? Tema.ringSoft : "transparent"
                            border.width: sec.visualFocus ? 3 : 0
                            border.color: Tema.ring
                            // La sección activa, marcada en BLANCO (Netflix deja el rojo para lo importante)
                            Rectangle {
                                visible: ventana.pagina === sec.index
                                width: 3; height: parent.height * 0.6
                                anchors.verticalCenter: parent.verticalCenter
                                x: -Tema.px(8)
                                radius: 2
                                color: "white"
                            }
                        }
                        contentItem: RowLayout {
                            spacing: Tema.px(14)
                            Icono { nombre: sec.modelData[0]; color: ventana.pagina === sec.index ? "white" : Tema.dim; tam: Tema.px(18) }
                            Etiqueta {
                                Layout.fillWidth: true
                                text: sec.modelData[1]
                                estilo: "bodyLarge"
                                color: ventana.pagina === sec.index ? "white" : Tema.dim
                                font.weight: ventana.pagina === sec.index ? Font.Bold : Font.Normal
                            }
                        }
                    }
                }
                Item { Layout.fillHeight: true }

                // Aviso: sin Real-Debrid no se ve nada
                Rectangle {
                    visible: !App.rd
                    Layout.fillWidth: true
                    implicitHeight: colRd.implicitHeight + Tema.px(20)
                    radius: Tema.radioTarjeta
                    color: "#26fbbf24"
                    ColumnLayout {
                        id: colRd
                        anchors.fill: parent
                        anchors.margins: Tema.px(10)
                        Etiqueta { Layout.fillWidth: true; text: "Conecta Real-Debrid para ver y descargar."; color: Tema.warn; estilo: "labelSmall" }
                        Boton { text: "Ir a Ajustes"; compacto: true; tipo: "secundario"; onClicked: { ventana.ficha = null; ventana.pagina = 3 } }
                    }
                }

                // El perfil activo, al fondo de la barra: en la tele es donde se busca
                AbstractButton {
                    id: perfilBtn
                    visible: App.conSesion
                    Layout.fillWidth: true
                    focusPolicy: Qt.StrongFocus
                    hoverEnabled: true
                    padding: Tema.px(10)
                    onClicked: selector.open()
                    Keys.onReturnPressed: clicked()
                    background: Rectangle {
                        radius: Tema.radioTarjeta
                        color: perfilBtn.visualFocus || perfilBtn.hovered ? Tema.ringSoft : "transparent"
                        border.width: perfilBtn.visualFocus ? 3 : 0
                        border.color: Tema.ring
                    }
                    contentItem: RowLayout {
                        spacing: Tema.px(10)
                        Text { text: App.st.sync.active ? App.st.sync.active.avatar : "👤"; font.pixelSize: Tema.titleLarge }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            Etiqueta { text: "Perfil"; secundario: true; estilo: "labelSmall" }
                            Etiqueta {
                                Layout.fillWidth: true
                                text: App.st.sync.active ? App.st.sync.active.name + (App.kids ? "  🧒" : "") : "Elegir perfil"
                                estilo: "bodyMedium"
                                maximumLineCount: 1
                                wrapMode: Text.NoWrap
                            }
                        }
                        Icono { nombre: "derecha"; color: Tema.muted; tam: Tema.px(12) }
                    }
                }
            }
        }

        // ------------------------------------------------- contenido
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            StackLayout {
                anchors.fill: parent
                currentIndex: ventana.pagina
                visible: !ventana.ficha
                Loader { id: descubrir; sourceComponent: PaginaDescubrir {} }
                Loader { id: buscar; sourceComponent: PaginaBuscar {} }
                Loader { active: ventana.pagina === 2 || item !== null; sourceComponent: PaginaDescargas {} }
                Loader { active: ventana.pagina === 3 || item !== null; sourceComponent: PaginaAjustes {} }
            }
            Loader {
                id: fichaLoader
                anchors.fill: parent
                active: ventana.ficha !== null
                sourceComponent: PaginaFicha {
                    titulo: ventana.ficha
                    onVolver: ventana.ficha = null
                }
            }
        }
    }

    // El reproductor ocupa la ventana entera
    Loader {
        anchors.fill: parent
        active: ventana.reproduciendo !== null
        z: 50
        sourceComponent: Reproductor {
            ctx: ventana.reproduciendo
            onCerrar: ventana.reproduciendo = null
        }
    }

    // ------------------------------------------------------------ avisos
    Rectangle {
        id: toast
        z: 100
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: Tema.px(28)
        width: Math.min(toastTxt.implicitWidth + Tema.px(36), parent.width - 80)
        height: toastTxt.implicitHeight + Tema.px(22)
        radius: Tema.radio
        color: "#f0303030"
        border.color: Tema.outlineVariant
        opacity: 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
        Etiqueta { id: toastTxt; anchors.centerIn: parent; width: Math.min(implicitWidth, ventana.width - 120); text: ""; horizontalAlignment: Text.AlignHCenter }
        Timer { id: toastTimer; interval: 3200; onTriggered: toast.opacity = 0 }
        function mostrar(t) { toastTxt.text = t; opacity = 1; toastTimer.restart() }
    }

    SelectorPerfil {
        id: selector
        onGestionar: { ventana.ficha = null; ventana.pagina = 3 }
    }
    // Al entrar con una cuenta de varios perfiles, se pregunta quién ve (Netflix)
    property bool preguntado: false
    property int nPerfiles: (App.st.sync && App.st.sync.profiles) ? App.st.sync.profiles.length : 0
    onNPerfilesChanged: if (nPerfiles > 1 && !preguntado) { preguntado = true; selector.open() }

    Dialogo {
        id: dialogoReproductor
        titulo: "¿Con qué lo abrimos?"
        Etiqueta {
            Layout.fillWidth: true; secundario: true; estilo: "bodySmall"
            text: "VLC maneja mejor algún MKV raro; el de la app guarda el «continuar viendo» y pasa al siguiente episodio."
        }
        Boton { Layout.fillWidth: true; text: "Reproductor de la app"; onClicked: { dialogoReproductor.close(); ventana.reproduciendo = ventana.preguntar } }
        Boton { Layout.fillWidth: true; text: "VLC"; tipo: "secundario"; onClicked: { dialogoReproductor.close(); ventana.externo(ventana.preguntar) } }
        pie: [Boton { text: "Cancelar"; tipo: "texto"; onClicked: dialogoReproductor.close() }]
    }

    // Cerrar con descargas en marcha: se pausan (no se pierde nada), pero avisar
    property bool cerrarYa: false
    onClosing: function (close) {
        const n = backend.descargasActivas()
        if (n > 0 && !cerrarYa) { close.accepted = false; dialogoCerrar.n = n; dialogoCerrar.open() }
    }
    Dialogo {
        id: dialogoCerrar
        property int n: 0
        titulo: "Hay descargas en marcha"
        Etiqueta {
            Layout.fillWidth: true
            text: (dialogoCerrar.n === 1 ? "Hay 1 descarga en curso." : "Hay " + dialogoCerrar.n + " descargas en curso.")
                  + " Si cierras se pausan, y al volver a abrir VizPlay siguen desde donde iban."
            secundario: true
        }
        pie: [
            Boton { text: "Cerrar igualmente"; onClicked: { ventana.cerrarYa = true; dialogoCerrar.close(); ventana.close() } },
            Boton { text: "Seguir descargando"; tipo: "texto"; onClicked: dialogoCerrar.close() }
        ]
    }
}
