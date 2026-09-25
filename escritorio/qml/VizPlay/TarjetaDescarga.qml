import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

// Una descarga: progreso, velocidad y pausar / continuar. «Continuar» no
// reempieza: sigue desde el byte que haya en disco, y si el enlace de
// Real-Debrid ha caducado se pide otro por dentro.
Rectangle {
    id: t
    property var d: ({})
    readonly property bool hecha: d.state === "done"
    readonly property bool corriendo: d.state === "running"
    readonly property bool pausada: d.state === "paused"
    readonly property bool fallida: d.state === "error"
    readonly property bool conocido: d.total > 0
    Layout.fillWidth: true
    implicitHeight: col.implicitHeight + Tema.px(24)
    radius: Tema.radioTarjeta
    color: Tema.surface1

    ColumnLayout {
        id: col
        anchors.fill: parent
        anchors.margins: Tema.px(12)
        spacing: Tema.px(6)
        Etiqueta { Layout.fillWidth: true; text: t.d.name; estilo: "bodyMedium"; maximumLineCount: 2; wrapMode: Text.WrapAnywhere }
        Barra {
            Layout.fillWidth: true
            visible: t.hecha || t.conocido || t.corriendo
            valor: t.hecha ? 1 : t.d.pct
            indeterminada: !t.hecha && !t.conocido && t.corriendo
        }
        Etiqueta {
            Layout.fillWidth: true
            estilo: "bodySmall"
            color: t.hecha ? Tema.ok : (t.fallida ? Tema.warn : Tema.muted)
            text: t.hecha ? "✓ Disponible sin conexión  ·  " + App.tamano(t.d.total)
                : t.fallida ? (t.d.error || "Error en la descarga")
                : t.pausada ? "⏸ Pausada  ·  " + Math.round(t.d.pct * 100) + "%  ·  " + App.tamano(t.d.bytes) + (t.conocido ? " / " + App.tamano(t.d.total) : "")
                : t.conocido ? Math.round(t.d.pct * 100) + "%  ·  " + App.tamano(t.d.bytes) + " / " + App.tamano(t.d.total)
                               + (t.d.speed > 0 ? "  ·  " + App.tamano(t.d.speed) + "/s" : "")
                               + (t.d.speed > 0 && t.conocido ? "  ·  quedan " + App.tiempo((t.d.total - t.d.bytes) / t.d.speed) : "")
                : t.d.bytes > 0 ? "Descargando… " + App.tamano(t.d.bytes)
                : "En cola…"
        }
        // Un aviso mientras corre (p. ej. «Renovando el enlace en Real-Debrid…»)
        Etiqueta { visible: !t.fallida && !t.hecha && (t.d.error || "") !== ""; text: t.d.error || ""; color: Tema.warn; estilo: "labelSmall" }
        Flow {
            Layout.fillWidth: true
            spacing: Tema.px(8)
            Boton { visible: t.hecha; text: "Ver"; icono: "play"; onClicked: t.ver() }
            Boton { visible: t.corriendo || t.d.state === "queued"; text: "Pausar"; icono: "pausa"; tipo: "secundario"; onClicked: App.llamar("dlPause", { id: t.d.id }) }
            Boton { visible: t.pausada || t.fallida; text: "Continuar"; icono: "play"; onClicked: App.llamar("dlResume", { id: t.d.id }) }
            // Un fichero a medias se puede ir viendo
            Boton { visible: !t.hecha && t.d.bytes > 0; text: "Ver lo bajado"; tipo: "secundario"; onClicked: t.ver() }
            Boton { text: "Mostrar en la carpeta"; icono: "carpeta"; tipo: "texto"; onClicked: backend.abrirCarpeta(t.d.file) }
            Boton { text: "Borrar"; icono: "borrar"; tipo: "texto"; onClicked: confirmar.open() }
        }
    }
    function ver() { App.reproducir({ url: backend.urlLocal(t.d.file), name: t.d.name, type: "movie", tmdbId: -1 }) }

    Dialogo {
        id: confirmar
        titulo: "¿Borrar la descarga?"
        Etiqueta { Layout.fillWidth: true; text: "Se borra también el vídeo del disco:\n" + t.d.file; secundario: true; estilo: "bodySmall"; wrapMode: Text.WrapAnywhere }
        pie: [
            Boton { text: "Borrar"; tipo: "acento"; onClicked: { confirmar.close(); App.llamar("dlRemove", { id: t.d.id }) } },
            Boton { text: "Cancelar"; tipo: "texto"; onClicked: confirmar.close() }
        ]
    }
}
