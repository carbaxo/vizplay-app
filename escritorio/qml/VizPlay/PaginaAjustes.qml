import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs

// Ajustes (SettingsScreen), con las mismas secciones que Android menos las que
// son del móvil (datos móviles, Chromecast, huella SHA-1) y con dos del PC: la
// clave de TMDB y el «modo tele».
Item {
    id: pag
    readonly property var s: App.st.sync || {}
    readonly property var rdi: App.st.rd || {}
    readonly property var pr: App.st.prefs || {}

    Pagina {
        anchors.fill: parent
        ancho: Tema.px(860)

        Etiqueta { text: "Ajustes"; estilo: "headlineSmall" }

        // ============================================================ Cuenta
        Tarjeta {
            titulo: "Cuenta"
            ColumnLayout {
                visible: !pag.s.signedIn
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Etiqueta {
                    Layout.fillWidth: true; secundario: true; estilo: "bodySmall"
                    text: "Inicia sesión para tener tus perfiles, Mi lista, lo que estás viendo y el token de Real-Debrid en todos tus dispositivos: es la MISMA cuenta que la app de Android y la web."
                }
                Boton {
                    text: "Entrar con Google"
                    cargando: cuenta.google
                    enabled: !cuenta.google
                    onClicked: {
                        cuenta.google = true
                        cuenta.msg = "Se ha abierto el navegador: elige tu cuenta de Google allí y vuelve aquí."
                        App.llamar("google", {}, function (m) {
                            cuenta.google = false
                            const d = m.ok ? m.data : { error: m.error }
                            cuenta.msg = d.error || ""
                        })
                    }
                }
                Etiqueta {
                    Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                    text: "Si en el móvil entras con Google, usa este botón para encontrar tus datos de siempre."
                }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#22ffffff"; Layout.topMargin: Tema.px(4) }
                Etiqueta { text: "O con email y contraseña"; estilo: "labelMedium"; secundario: true }
                Campo { id: mail; Layout.fillWidth: true; etiqueta: "Email"; onAceptado: clave.campo.forceActiveFocus() }
                Campo { id: clave; Layout.fillWidth: true; etiqueta: "Contraseña (mínimo 6)"; clave: true; onAceptado: cuenta.entrar("signIn") }
                Flow {
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton { text: "Entrar"; enabled: !cuenta.ocupado; onClicked: cuenta.entrar("signIn") }
                    Boton { text: "Crear cuenta"; tipo: "secundario"; enabled: !cuenta.ocupado; onClicked: cuenta.entrar("signUp") }
                    Boton {
                        text: "Olvidé la contraseña"; tipo: "texto"; enabled: !cuenta.ocupado
                        onClicked: {
                            cuenta.ocupado = true
                            App.llamar("resetPassword", { email: mail.text }, m => { cuenta.ocupado = false; cuenta.msg = m.ok ? m.data.msg : m.error })
                        }
                    }
                }
            }
            QtObject {
                id: cuenta
                property bool ocupado: false
                property bool google: false
                property string msg: ""
                function entrar(tipo) {
                    ocupado = true
                    msg = tipo === "signIn" ? "Entrando…" : "Creando la cuenta…"
                    App.llamar(tipo, { email: mail.text, password: clave.text }, function (m) {
                        cuenta.ocupado = false
                        const d = m.ok ? m.data : { ok: false, error: m.error }
                        cuenta.msg = d.ok ? "" : (d.error || "Error")
                        if (d.ok) clave.text = ""
                    })
                }
            }
            Etiqueta { visible: cuenta.msg !== ""; Layout.fillWidth: true; text: cuenta.msg; color: Tema.warn; estilo: "labelSmall" }

            // ---- con sesión: perfiles
            ColumnLayout {
                visible: !!pag.s.signedIn
                Layout.fillWidth: true
                spacing: Tema.px(8)
                RowLayout {
                    Layout.fillWidth: true
                    Etiqueta { text: "👤 " + (pag.s.email || ""); Layout.fillWidth: true }
                    Etiqueta { visible: !!pag.s.loading; text: "Sincronizando…"; secundario: true; estilo: "labelSmall" }
                    Boton { text: "Releer de la nube"; icono: "recargar"; tipo: "texto"; compacto: true; onClicked: App.llamar("reload", {}) }
                }
                Etiqueta { visible: !!pag.s.error; Layout.fillWidth: true; text: pag.s.error || ""; color: Tema.warn; estilo: "labelSmall" }
                Etiqueta { text: "Perfiles"; estilo: "labelMedium"; secundario: true; visible: (pag.s.profiles || []).length > 0 }
                Etiqueta {
                    visible: (pag.s.profiles || []).length === 0 && !pag.s.loading
                    text: "No hay perfiles todavía. Crea el primero aquí abajo."
                    secundario: true; estilo: "labelSmall"
                }
                Repeater {
                    model: pag.s.profiles || []
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: Tema.px(6)
                        Chip {
                            Layout.fillWidth: true
                            text: modelData.avatar + "  " + modelData.name + (modelData.kids ? "  🧒" : "")
                            seleccionado: pag.s.active && pag.s.active.id === modelData.id
                            onClicked: App.llamar("profileSelect", { id: modelData.id })
                        }
                        BotonRedondo { icono: "editar"; ayuda: "Editar perfil"; onClicked: perfil.editar(modelData) }
                        BotonRedondo {
                            visible: (pag.s.profiles || []).length > 1
                            icono: "cerrar"; ayuda: "Borrar perfil"
                            onClicked: App.llamar("profileRemove", { id: modelData.id }, m => perfil.msg = (m.ok ? m.data.error : m.error) || "")
                        }
                    }
                }
                ColumnLayout {
                    id: perfil
                    property string editId: ""
                    property bool abierto: false
                    property string msg: ""
                    function editar(p) { editId = p.id; nombreP.text = p.name; avatarP.text = p.avatar; kidsP.checked = p.kids; abierto = true; msg = "" }
                    function nuevo() { editId = ""; nombreP.text = ""; avatarP.text = ""; kidsP.checked = false; abierto = true; msg = "" }
                    Layout.fillWidth: true
                    visible: abierto
                    spacing: Tema.px(8)
                    Etiqueta { text: perfil.editId ? "Editar perfil" : "Nuevo perfil"; estilo: "labelMedium"; secundario: true }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Tema.px(8)
                        Campo { id: nombreP; Layout.fillWidth: true; etiqueta: "Nombre" }
                        Campo { id: avatarP; Layout.preferredWidth: Tema.px(120); etiqueta: "Emoji (opcional)" }
                    }
                    Interruptor { id: kidsP; texto: "Modo infantil"; ayuda: "Solo catálogos familiares y sin recomendaciones." }
                    Flow {
                        Layout.fillWidth: true
                        spacing: Tema.px(8)
                        Boton {
                            text: "Guardar"
                            onClicked: {
                                const a = { id: perfil.editId, name: nombreP.text, kids: kidsP.checked, avatar: avatarP.text }
                                App.llamar(perfil.editId ? "profileUpdate" : "profileAdd", a, function (m) {
                                    const err = m.ok ? m.data.error : m.error
                                    if (err) perfil.msg = err; else perfil.abierto = false
                                })
                            }
                        }
                        Boton { text: "Cancelar"; tipo: "texto"; onClicked: perfil.abierto = false }
                    }
                }
                Etiqueta { visible: perfil.msg !== ""; text: perfil.msg; color: Tema.warn; estilo: "labelSmall" }
                Flow {
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton { visible: !perfil.abierto && (pag.s.profiles || []).length < 5; text: "Nuevo perfil"; icono: "mas"; tipo: "secundario"; onClicked: perfil.nuevo() }
                    Boton { text: "Cerrar sesión"; icono: "salir"; tipo: "texto"; onClicked: App.llamar("signOut", {}) }
                }
            }
        }

        // =========================================================== Idiomas
        Tarjeta {
            titulo: "Idiomas"
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "bodySmall"
                text: "Orden de preferencia: al buscar, las fuentes salen primero en el idioma de arriba (y el primero es el de los catálogos y las fichas)."
            }
            Repeater {
                model: pag.pr.langOrder || []
                RowLayout {
                    required property var modelData
                    required property int index
                    Layout.fillWidth: true
                    Etiqueta { text: (index + 1) + ".  " + App.idioma(modelData) + "  ·  " + App.nombreIdioma(modelData); Layout.fillWidth: true }
                    BotonRedondo {
                        icono: "arriba"; ayuda: "Subir"; enabled: index > 0; opacity: enabled ? 1 : 0.3
                        onClicked: { const l = pag.pr.langOrder.slice(); l.splice(index - 1, 0, l.splice(index, 1)[0]); App.ajustar("langOrder", l) }
                    }
                    BotonRedondo {
                        icono: "abajo"; ayuda: "Bajar"; enabled: index < pag.pr.langOrder.length - 1; opacity: enabled ? 1 : 0.3
                        onClicked: { const l = pag.pr.langOrder.slice(); l.splice(index + 1, 0, l.splice(index, 1)[0]); App.ajustar("langOrder", l) }
                    }
                    BotonRedondo {
                        icono: "cerrar"; ayuda: "Quitar"; enabled: pag.pr.langOrder.length > 1; opacity: enabled ? 1 : 0.3
                        onClicked: App.ajustar("langOrder", pag.pr.langOrder.filter(c => c !== modelData))
                    }
                }
            }
            Flow {
                readonly property var faltan: (App.st.langs || []).filter(l => (pag.pr.langOrder || []).indexOf(l.code) < 0)
                visible: faltan.length > 0
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Etiqueta { text: "Añadir:"; secundario: true; estilo: "labelMedium"; height: Tema.px(32); verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: parent.faltan
                    Chip { required property var modelData; icono: "mas"; text: modelData.label; onClicked: App.ajustar("langOrder", pag.pr.langOrder.concat([modelData.code])) }
                }
            }
        }

        // ======================================================= Real-Debrid
        Tarjeta {
            titulo: "Real-Debrid"
            ColumnLayout {
                visible: !!pag.rdi.configured
                Layout.fillWidth: true
                spacing: Tema.px(4)
                Etiqueta { text: "⚡ Conectado" + (pag.rdi.account ? " · " + pag.rdi.account : (pag.rdi.info ? " · " + pag.rdi.info.username : "")); color: Tema.ok }
                Etiqueta {
                    readonly property var a: pag.rdi.info
                    visible: !a
                    text: pag.rdi.infoLoading ? "Leyendo la cuenta…" : (pag.rdi.infoError || "")
                    color: pag.rdi.infoError ? Tema.warn : Tema.muted
                    estilo: "labelSmall"
                }
                ColumnLayout {
                    readonly property var a: pag.rdi.info
                    visible: !!a
                    Layout.fillWidth: true
                    spacing: Tema.px(3)
                    Etiqueta {
                        text: parent.a ? (parent.a.premium ? "⏳ Premium: quedan " + parent.a.days + " días" + (parent.a.expiration ? "  ·  hasta el " + parent.a.expiresPretty : "")
                                                          : "⚠️ Esta cuenta NO es premium: Real-Debrid no dará enlaces.") : ""
                        color: parent.a && (!parent.a.premium || parent.a.days <= 7) ? Tema.warn : Tema.muted
                        estilo: "labelSmall"
                    }
                    Etiqueta { text: parent.a ? "🎟 Puntos de fidelidad: " + parent.a.points : ""; secundario: true; estilo: "labelSmall" }
                    Etiqueta {
                        visible: !!(parent.a && parent.a.slotsKnown)
                        text: parent.a ? "📥 Torrents activos: " + parent.a.slotsUsed + " / " + parent.a.slotsLimit : ""
                        color: parent.a && parent.a.slotsFull ? Tema.warn : Tema.muted
                        estilo: "labelSmall"
                    }
                    Barra {
                        visible: !!(parent.a && parent.a.slotsKnown)
                        Layout.fillWidth: true
                        implicitHeight: 3
                        valor: parent.a && parent.a.slotsLimit > 0 ? parent.a.slotsUsed / parent.a.slotsLimit : 0
                    }
                    Etiqueta {
                        visible: !!(parent.a && parent.a.slotsFull)
                        Layout.fillWidth: true
                        text: "Sin huecos libres: hasta que acaben o borres alguno, Real-Debrid rechazará los magnets nuevos. Se quitan en Descargas → En tu Real-Debrid."
                        color: Tema.warn; estilo: "labelSmall"
                    }
                }
                Etiqueta {
                    Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                    text: pag.s.signedIn ? "Vinculado a la cuenta " + pag.s.email + ": el mismo Real-Debrid en todos tus dispositivos con esa cuenta. Al cerrar sesión se queda con la cuenta, no en este PC."
                                         : "Guardado solo en este PC (cifrado con tu usuario de Windows). Inicia sesión arriba para tenerlo en todos tus dispositivos."
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton { text: "Actualizar datos"; tipo: "texto"; cargando: !!pag.rdi.infoLoading; onClicked: App.llamar("rdInfo", {}) }
                    Boton { text: "Desconectar"; tipo: "secundario"; onClicked: App.llamar("rdDisconnect", {}) }
                }
            }
            ColumnLayout {
                visible: !pag.rdi.configured
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Etiqueta {
                    Layout.fillWidth: true; color: Tema.warn; estilo: "bodySmall"
                    text: "⚠️ Real-Debrid es imprescindible: la app no descarga por BitTorrent, todo el vídeo llega por streaming directo desde los servidores de RD. Pega tu token para empezar (si entras con tu cuenta y ya lo tenías en el móvil, llega solo)."
                }
                Campo { id: tokenRd; Layout.fillWidth: true; etiqueta: "Token de Real-Debrid"; clave: true; onAceptado: conectarRd.clicked() }
                Flow {
                    Layout.fillWidth: true
                    spacing: Tema.px(8)
                    Boton {
                        id: conectarRd
                        text: "Conectar"; enabled: tokenRd.text.trim() !== "" && !rdMsg.ocupado; cargando: rdMsg.ocupado
                        onClicked: {
                            rdMsg.ocupado = true; rdMsg.text = "Validando…"
                            App.llamar("rdConnect", { token: tokenRd.text }, function (m) {
                                rdMsg.ocupado = false
                                rdMsg.text = m.ok ? m.data.msg : m.error
                                if (m.ok && m.data.ok) tokenRd.text = ""
                            })
                        }
                    }
                    Boton { text: "Conseguir el token"; icono: "enlace"; tipo: "texto"; onClicked: backend.abrirUrl("https://real-debrid.com/apitoken") }
                }
            }
            Etiqueta { id: rdMsg; property bool ocupado: false; visible: text !== ""; Layout.fillWidth: true; secundario: true; estilo: "bodySmall" }
        }

        // ====================================================== Reproducción
        Tarjeta {
            titulo: "Reproducción"
            Etiqueta { text: "¿Con qué se abre el vídeo al pulsar Ver?"; secundario: true; estilo: "bodySmall" }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Repeater {
                    model: [["app", "Reproductor de la app"], ["vlc", "Siempre VLC"], ["ask", "Preguntar"]]
                    Chip { required property var modelData; text: modelData[1]; seleccionado: pag.pr.playerMode === modelData[0]; onClicked: App.ajustar("playerMode", modelData[0]) }
                }
            }
            Etiqueta {
                visible: App.st.vlc === "" && pag.pr.playerMode !== "app"
                Layout.fillWidth: true
                text: "⚠️ VLC no está instalado en este PC, así que se usará el de la app."
                color: Tema.warn; estilo: "labelSmall"
            }
            Boton { visible: App.st.vlc === ""; text: "Descargar VLC"; icono: "enlace"; tipo: "texto"; onClicked: backend.abrirUrl("https://www.videolan.org/vlc/") }
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                text: "El de la app lee los MKV con HEVC y audio Dolby/DTS, deja elegir pista de audio y subtítulos (también un .srt tuyo), guarda el «continuar viendo» y pasa al siguiente episodio. «Siempre VLC» va directo a VLC: a cambio se pierden el «continuar viendo» y el siguiente episodio."
            }
        }

        // ========================================================= Descargas
        Tarjeta {
            titulo: "Descargas"
            Etiqueta { text: "Carpeta de descargas"; estilo: "bodyMedium" }
            Etiqueta { text: pag.pr.downloadDir || ""; color: Tema.ok; estilo: "labelSmall"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Boton { text: "Elegir carpeta…"; icono: "carpeta"; onClicked: elegirCarpeta.open() }
                Boton { text: "Usar Descargas\\VizPlay"; tipo: "secundario"; onClicked: App.ajustar("downloadDir", "") }
                Boton { text: "Abrir"; tipo: "texto"; onClicked: backend.abrirCarpeta(pag.pr.downloadDir) }
            }
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                text: "Afecta a las descargas NUEVAS; las que ya están siguen donde estaban. Los vídeos que dejes en esa carpeta (bajados con otra app) aparecen también en Descargas, listos para ver."
            }
            FolderDialog {
                id: elegirCarpeta
                title: "Carpeta para las descargas"
                onAccepted: App.ajustar("downloadDir", decodeURIComponent(selectedFolder.toString().replace(/^file:\/\/\//, "")))
            }
        }

        // ======================================================== Buscadores
        Tarjeta {
            titulo: "Buscadores"
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "bodySmall"
                text: "Peerflix (DonTorrent, MejorTorrent, Wolfmax4k, Popcorntime, Bitsearch: las webs españolas) y Torrentio. Se puede añadir un tercero. Además se busca siempre en TU Real-Debrid: lo que añadas en Descargas sale en la ficha como un enlace más, y es el que va primero."
            }
            Campo { id: peerflix; Layout.fillWidth: true; etiqueta: "URL propia de Peerflix (opcional)"; placeholder: "https://peerflix.mov"; text: pag.pr.peerflixUrl || "" }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Boton { text: "Guardar"; onClicked: { App.ajustar("peerflixUrl", peerflix.text); App.aviso("Guardado") } }
                Boton { visible: !!pag.pr.peerflixUrl; text: "Usar la pública"; tipo: "secundario"; onClicked: { App.ajustar("peerflixUrl", ""); peerflix.text = "" } }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: Tema.surface2 }
            Campo { id: extra; Layout.fillWidth: true; etiqueta: "Addon extra de Stremio (opcional)"; placeholder: "https://…/manifest.json"; text: pag.pr.extraAddonUrl || "" }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Boton { text: "Guardar"; onClicked: { App.ajustar("extraAddonUrl", extra.text); prueba.text = "" } }
                Boton {
                    text: "Probar"; tipo: "secundario"
                    onClicked: { prueba.text = "Probando…"; App.llamar("extraTest", { url: extra.text }, m => prueba.text = m.ok ? m.data.msg : m.error) }
                }
                Boton { visible: !!pag.pr.extraAddonUrl; text: "Quitar"; tipo: "texto"; onClicked: { App.ajustar("extraAddonUrl", ""); extra.text = ""; prueba.text = "" } }
            }
            Etiqueta { id: prueba; visible: text !== ""; Layout.fillWidth: true; color: text.indexOf("✅") === 0 ? Tema.ok : Tema.warn; estilo: "labelSmall" }
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                text: "Vale cualquier addon de Stremio que dé torrents (MediaFusion, Comet, Jackettio…): pega su URL, con /manifest.json o sin él, y dale a «Probar». No hace falta configurarlo con Real-Debrid: la app manda el magnet a tu cuenta ella sola."
            }
        }

        // ========================================================= Catálogos
        Tarjeta {
            titulo: "Catálogos (TMDB)"
            Etiqueta {
                Layout.fillWidth: true
                text: pag.pr.tmdbKey ? "✓ Clave de TMDB puesta" + (pag.pr.tmdbFromEnv ? " (variable de entorno TMDB_KEY)" : "") : "Sin clave: no hay catálogos, carátulas ni fichas."
                color: pag.pr.tmdbKey ? Tema.ok : Tema.warn
                estilo: "bodySmall"
            }
            Campo { id: tmdbKey; Layout.fillWidth: true; etiqueta: "Clave de la API de TMDB (v3)"; clave: true; placeholder: pag.pr.tmdbKey ? "•••••••• (pon otra para cambiarla)" : "" }
            Flow {
                Layout.fillWidth: true
                spacing: Tema.px(8)
                Boton { text: "Guardar"; enabled: tmdbKey.text.trim() !== ""; onClicked: { App.ajustar("tmdbKey", tmdbKey.text); tmdbKey.text = ""; App.aviso("Clave guardada") } }
                Boton { text: "Conseguir una clave"; icono: "enlace"; tipo: "texto"; onClicked: backend.abrirUrl("https://www.themoviedb.org/settings/api") }
            }
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                text: "Es gratuita. En la app de Android va dentro del APK (secreto de GitHub); aquí el código es público, así que se pega una vez y se queda en este PC."
            }
        }

        // ======================================================== Apariencia
        Tarjeta {
            titulo: "Apariencia"
            Interruptor {
                texto: "Modo tele"
                ayuda: "Letra y carátulas un 15 % más grandes, para un PC conectado a la tele del salón (lo que se lee a 60 cm no se lee a 3 m)."
                checked: !!pag.pr.bigText
                onCambiado: v => App.ajustar("bigText", v)
            }
        }

        // ======================================================== Aplicación
        Tarjeta {
            titulo: "Aplicación"
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "bodySmall"
                text: "Al cerrar no queda nada corriendo: la app no tiene servicio en segundo plano ni motor de torrents. Las descargas en curso se pausan y continúan desde donde iban al volver a abrirla."
            }
            Etiqueta {
                Layout.fillWidth: true; secundario: true; estilo: "labelSmall"
                text: "Teclado: Esc vuelve atrás · Ctrl+F busca · Ctrl+1…4 cambian de sección · Tab y las flechas mueven el foco, Intro abre. En el reproductor: Espacio pausa, ←/→ 10 s, ↑/↓ volumen, F pantalla completa, N siguiente episodio."
            }
        }
        Item { Layout.preferredHeight: Tema.px(12) }
    }
}
