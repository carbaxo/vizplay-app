import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Descargas (DownloadsScreen): separa lo que está EN CURSO de lo que ya está
// LISTO PARA VER, y arriba el «Añadir a Real-Debrid» a mano con la lista de la
// cuenta y su estado real (leyendo el magnet, en cola, descargando con su %,
// listo, sin semillas…).
Item {
    id: pag
    readonly property var todas: App.st.downloads || []
    readonly property var listas: todas.filter(d => d.state === "done")
    readonly property var enCurso: todas.filter(d => d.state !== "done")

    property var torrents: []
    property string errLista: ""
    property string msg: ""
    property bool ocupado: false
    property bool desplegado: true
    property var elegir: null          // {files, descarga}
    readonly property int trabajando: torrents.filter(t => t.working).length

    function refrescar() {
        App.llamar("rdTorrents", {}, function (m) {
            if (m.ok) { pag.torrents = m.data; pag.errLista = "" } else pag.errLista = m.error
        })
    }
    onVisibleChanged: if (visible) { refrescar(); if (App.rd) App.llamar("rdInfo", {}) }
    // Rápido mientras RD esté trabajando, lento si no hay nada en marcha
    Timer {
        running: pag.visible && App.rd
        repeat: true
        interval: pag.trabajando > 0 ? 4000 : 20000
        onTriggered: pag.refrescar()
    }
    Connections {
        target: App
        function onPegarMagnet(m) { entrada.text = m; pag.desplegado = true; pag.msg = "Pegado. Pulsa «Añadir a Real-Debrid»." }
    }

    function anadir() {
        ocupado = true
        msg = entrada.text.trim().toLowerCase().indexOf("magnet:") === 0 ? "Añadiendo el magnet a Real-Debrid…" : "Preparando el enlace con Real-Debrid…"
        App.llamar("addLink", { text: entrada.text }, function (m) {
            pag.ocupado = false
            const d = m.ok ? m.data : { error: m.error }
            if (d.error) { pag.msg = d.error; return }
            pag.msg = d.msg
            entrada.text = ""
            pag.refrescar()
        })
    }
    function usarEnlace(link, descarga, nombre) {
        ocupado = true
        msg = "Preparando el enlace…"
        App.llamar("rdUnrestrict", { link: link }, function (m) {
            pag.ocupado = false
            const d = m.ok ? m.data : { error: m.error }
            if (!d.url) { pag.msg = d.error || "No se pudo preparar el enlace."; return }
            if (descarga) { App.llamar("dlAdd", { url: d.url, name: d.filename }); pag.msg = "⬇ Descarga encolada: " + d.filename }
            else { pag.msg = ""; App.reproducir({ url: d.url, name: nombre || d.filename, type: "movie", tmdbId: -1 }) }
        })
    }
    function abrirTorrent(t, descarga) {
        ocupado = true
        msg = "Mirando qué archivos tiene…"
        App.llamar("rdFiles", { id: t.id }, function (m) {
            pag.ocupado = false
            const d = m.ok ? m.data : { error: m.error }
            if (!d.files) { pag.msg = d.error || "No se pudo leer el torrent."; return }
            pag.msg = ""
            if (d.files.length === 1) pag.usarEnlace(d.files[0].link, descarga, d.files[0].short)
            else pag.elegir = { files: d.files, descarga: descarga }
        })
    }
    onElegirChanged: elegir ? ventanaElegir.open() : ventanaElegir.close()

    Pagina {
        anchors.fill: parent
        ancho: Tema.px(1100)

        Etiqueta { text: "Descargas"; estilo: "headlineSmall" }
        RowLayout {
            spacing: Tema.px(10)
            Etiqueta { text: "Libre: " + App.st.freeSpace + "  ·  Se guardan en " + App.st.downloadsFolder; secundario: true; estilo: "labelSmall" }
            Boton { text: "Abrir carpeta"; icono: "carpeta"; tipo: "texto"; compacto: true; onClicked: backend.abrirCarpeta(App.st.downloadsFolder) }
        }
        Etiqueta {
            visible: pag.todas.length === 0
            Layout.fillWidth: true
            secundario: true
            estilo: "bodySmall"
            text: "Aún no hay descargas. Abre un título, busca fuentes y pulsa «Descargar». Se pueden pausar y continuar; si cierras la app se pausan y siguen desde donde iban al volver."
        }

        // ---------------------------------------- Añadir a Real-Debrid
        Tarjeta {
            titulo: "Añadir a Real-Debrid"
            cabecera: [BotonRedondo { visible: App.rd; icono: "recargar"; ayuda: "Actualizar"; onClicked: pag.refrescar() }]
            Etiqueta {
                visible: !App.rd
                Layout.fillWidth: true
                text: "Conecta Real-Debrid en Ajustes para poder añadir magnets."
                color: Tema.warn; estilo: "bodySmall"
            }
            ColumnLayout {
                visible: App.rd
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Etiqueta {
                    Layout.fillWidth: true
                    secundario: true; estilo: "bodySmall"
                    text: "Pega un magnet y Real-Debrid lo baja a sus servidores; luego se ve al instante. Lo que añadas aquí aparecerá después en la ficha del título como un enlace más. Un enlace de hoster (1fichier, Mega…) se prepara y se descarga directamente."
                }
                TextArea {
                    id: entrada
                    Layout.fillWidth: true
                    Layout.preferredHeight: Tema.px(70)
                    placeholderText: "magnet:?xt=… o un enlace de hoster"
                    placeholderTextColor: "#80ffffff"
                    wrapMode: TextEdit.WrapAnywhere
                    color: "white"
                    font.family: Tema.familia
                    font.pixelSize: Tema.bodySmall
                    selectByMouse: true
                    background: Rectangle {
                        radius: Tema.radio
                        color: "#0dffffff"
                        border.width: entrada.activeFocus ? 2 : 1
                        border.color: entrada.activeFocus ? "white" : Tema.outline
                    }
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton { text: "Añadir a Real-Debrid"; enabled: entrada.text.trim() !== "" && !pag.ocupado; cargando: pag.ocupado; onClicked: pag.anadir() }
                    Boton {
                        text: "Pegar"; icono: "pegar"; tipo: "secundario"
                        onClicked: { const t = backend.portapapeles(); if (t.trim()) { entrada.text = t; pag.msg = "" } else pag.msg = "No hay nada copiado." }
                    }
                }
                Etiqueta { visible: pag.msg !== ""; Layout.fillWidth: true; text: pag.msg; secundario: true; estilo: "labelSmall" }

                // Lo que hay en la cuenta de RD
                AbstractButton {
                    Layout.fillWidth: true
                    focusPolicy: Qt.StrongFocus
                    padding: Tema.px(4)
                    onClicked: pag.desplegado = !pag.desplegado
                    Keys.onReturnPressed: clicked()
                    background: Rectangle { color: parent.hovered ? "#0dffffff" : "transparent"; radius: Tema.radio; Anillo { activo: parent.parent.visualFocus } }
                    contentItem: RowLayout {
                        Etiqueta {
                            Layout.fillWidth: true
                            text: "En tu Real-Debrid (" + pag.torrents.length + ")" + (pag.trabajando > 0 ? " · " + pag.trabajando + " en marcha" : "")
                            estilo: "bodyMedium"; font.weight: Font.Bold
                        }
                        Icono { nombre: pag.desplegado ? "arriba" : "abajo"; tam: Tema.px(14) }
                    }
                }
                Etiqueta {
                    readonly property var a: App.st.rd.info
                    visible: !!(a && a.slotsKnown)
                    text: a ? "Huecos de torrent: " + a.slotsUsed + " / " + a.slotsLimit + (a.slotsFull ? " — sin huecos: borra alguno para poder añadir" : "") : ""
                    color: a && a.slotsFull ? Tema.warn : Tema.muted
                    estilo: "labelSmall"
                }
                Etiqueta { visible: pag.errLista !== ""; text: pag.errLista; color: Tema.warn; estilo: "labelSmall" }
                Etiqueta { visible: pag.desplegado && pag.torrents.length === 0 && pag.errLista === ""; text: "No hay nada en la cuenta."; secundario: true; estilo: "labelSmall" }
                Repeater {
                    model: pag.desplegado ? pag.torrents : []
                    ColumnLayout {
                        id: t
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Tema.px(3)
                        Rectangle { Layout.fillWidth: true; height: 1; color: "#22ffffff" }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: Tema.px(4)
                            spacing: Tema.px(8)
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: Tema.px(3)
                                Etiqueta { Layout.fillWidth: true; text: t.modelData.name; estilo: "bodySmall"; maximumLineCount: 2; wrapMode: Text.WrapAnywhere }
                                Etiqueta {
                                    Layout.fillWidth: true
                                    estilo: "labelSmall"
                                    color: t.modelData.ready ? Tema.ok : (t.modelData.working ? Tema.muted : Tema.warn)
                                    text: [t.modelData.statusEs,
                                           t.modelData.working && t.modelData.status !== "queued" ? t.modelData.progress + "%" : "",
                                           t.modelData.speed > 0 ? App.tamano(t.modelData.speed) + "/s" : "",
                                           t.modelData.status === "downloading" && t.modelData.seeders > 0 ? t.modelData.seeders + " semillas" : "",
                                           t.modelData.bytes > 0 ? t.modelData.size : "",
                                           t.modelData.ready && t.modelData.links > 1 ? t.modelData.links + " archivos" : ""].filter(x => x).join("  ·  ")
                                }
                                Barra { visible: t.modelData.working && t.modelData.progress > 0 && t.modelData.progress < 100; Layout.fillWidth: true; valor: t.modelData.progress / 100; implicitHeight: 3 }
                            }
                            Boton { visible: t.modelData.ready; text: "Ver"; icono: "play"; tipo: "texto"; compacto: true; onClicked: pag.abrirTorrent(t.modelData, false) }
                            Boton { visible: t.modelData.ready; text: "Descargar"; icono: "descargar"; tipo: "texto"; compacto: true; onClicked: pag.abrirTorrent(t.modelData, true) }
                            BotonRedondo {
                                icono: "borrar"; ayuda: "Quitar de Real-Debrid"
                                onClicked: App.llamar("rdDelete", { id: t.modelData.id }, m => { if (m.ok && m.data.error) pag.msg = m.data.error; pag.refrescar() })
                            }
                        }
                    }
                }
            }
        }

        // --------------------------------------------- En curso
        Etiqueta { visible: pag.enCurso.length > 0; text: "⏳ En curso"; estilo: "titleMedium"; Layout.topMargin: Tema.px(8) }
        Repeater { model: pag.enCurso; TarjetaDescarga { required property var modelData; d: modelData } }

        // ---------------------------------------- Listas para ver
        Etiqueta { visible: pag.listas.length > 0; text: "▶ Listas para ver"; color: Tema.ok; estilo: "titleMedium"; Layout.topMargin: Tema.px(8) }
        Repeater { model: pag.listas; TarjetaDescarga { required property var modelData; d: modelData } }
        Item { Layout.preferredHeight: Tema.px(16) }
    }

    Dialogo {
        id: ventanaElegir
        titulo: pag.elegir && pag.elegir.descarga ? "¿Cuál descargo?" : "¿Cuál pongo?"
        ancho: Tema.px(640)
        onClosed: pag.elegir = null
        ListView {
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(contentHeight, Tema.px(420))
            clip: true
            model: pag.elegir ? pag.elegir.files : []
            ScrollBar.vertical: BarraScroll {}
            delegate: AbstractButton {
                id: fe
                required property var modelData
                width: ListView.view.width
                padding: Tema.px(10)
                hoverEnabled: true
                focusPolicy: Qt.StrongFocus
                onClicked: { const e = pag.elegir; pag.elegir = null; pag.usarEnlace(modelData.link, e.descarga, modelData.short) }
                Keys.onReturnPressed: clicked()
                background: Rectangle { radius: Tema.radio; color: fe.hovered || fe.activeFocus ? Tema.ringSoft : "transparent" }
                contentItem: RowLayout {
                    Etiqueta { Layout.fillWidth: true; text: fe.modelData.short; estilo: "bodySmall"; maximumLineCount: 2 }
                    Etiqueta { text: fe.modelData.bytes > 0 ? fe.modelData.size : ""; secundario: true; estilo: "labelSmall" }
                }
            }
        }
        pie: [Boton { text: "Cancelar"; tipo: "texto"; onClicked: pag.elegir = null }]
    }
}
