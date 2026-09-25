pragma Singleton
import QtQuick

// El estado de la app y el embudo de pedidos al backend, accesibles desde
// cualquier pantalla.
//
//  - App.st: lo que manda el backend (sesión, perfiles, Mi lista, progreso,
//    descargas, Real-Debrid, ajustes). Se relee solo cuando cambia.
//  - App.llamar(tipo, args, cb): pedido asíncrono; cb(m) recibe {ok, data,
//    error, fin}. La búsqueda de fuentes llama a cb varias veces (una por motor).
QtObject {
    id: app
    // Se actualiza SOLO cuando el backend avisa (y no con un binding a
    // backend.estado): al cerrar la app el backend desaparece antes que la
    // interfaz, y un binding reevaluaría todo con un estado vacío.
    property var st: ({ prefs: {}, sync: {}, rd: {} })
    Component.onCompleted: st = JSON.parse(backend.estado)
    property var _cbs: ({})
    property Connections _estado: Connections {
        target: backend
        function onEstadoChanged() { app.st = JSON.parse(backend.estado) }
    }

    // Navegación y avisos, para que cualquier pantalla pueda pedirlos
    signal abrirFicha(var titulo)
    signal reproducir(var ctx)
    signal aviso(string texto)
    signal irA(int pagina)
    // Un magnet que hay que añadir a mano: Descargas lo recoge (MagnetInbox)
    signal pegarMagnet(string magnet)
    function pegarEnDescargas(m) { pegarMagnet(m); irA(2) }

    readonly property bool kids: st.sync && st.sync.kids === true
    readonly property bool rd: st.rd && st.rd.configured === true
    readonly property bool conSesion: st.sync && st.sync.signedIn === true

    // Qué se ha visto, por título y por episodio (para «✓ Visto»)
    readonly property var _vistos: {
        const t = {}, e = {}
        for (const p of (st.progress || [])) {
            if (!p.watched) continue
            t[p.titleId] = true
            e[p.key] = true
        }
        return { titulos: t, episodios: e }
    }
    readonly property var _favs: {
        const m = {}
        for (const f of (st.favorites || [])) m[f.id] = true
        return m
    }
    readonly property var _cached: {
        const m = {}
        for (const h of (st.cached || [])) m[h] = true
        return m
    }

    function vistoTitulo(t) {
        if (!t || !t.tmdbId) return false
        return _vistos.titulos[(t.type === "series" ? "series:" : "movie:") + t.tmdbId] === true
    }
    function vistoEpisodio(tmdbId, s, e) { return _vistos.episodios["series:" + tmdbId + ":" + s + ":" + e] === true }
    function esFav(t) { return t && _favs["tmdb:" + t.tmdbId] === true }
    function enRd(hash) { return _cached[hash] === true }
    function progresoDe(key) {
        for (const p of (st.progress || [])) if (p.key === key) return p
        return null
    }

    function llamar(tipo, args, cb) {
        const id = backend.pedir(tipo, JSON.stringify(args || {}))
        if (cb) _cbs[id] = cb
        return id
    }
    function olvidar(id) { delete _cbs[id] }
    function ajustar(clave, valor) { backend.ajustar(clave, JSON.stringify(valor)) }

    property Connections _eventos: Connections {
        target: backend
        function onEvento(j) {
            const m = JSON.parse(j)
            const cb = app._cbs[m.id]
            if (!cb) return
            if (m.fin) delete app._cbs[m.id]
            try { cb(m) } catch (e) { console.warn("respuesta de", m.tipo, ":", e) }
        }
    }

    // Etiqueta corta de idioma. Windows no pinta las banderas emoji (salen las
    // letras sueltas), así que en el PC va el código, que se lee igual de rápido.
    function idioma(code) {
        return ({ "es-ES": "ES", "es-LA": "LAT", "en": "EN", "multi": "MULTI" })[code] || "?"
    }
    function nombreIdioma(code) {
        for (const l of (st.langs || [])) if (l.code === code) return l.label
        return "Idioma desconocido"
    }
    function tamano(n) {
        if (!n || n <= 0) return "?"
        const u = ["B", "KB", "MB", "GB", "TB"]
        let v = n, i = 0
        while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
        return (v >= 10 || i === 0 ? v.toFixed(0) : v.toFixed(1).replace(".", ",")) + " " + u[i]
    }
    function tiempo(s) {
        s = Math.max(0, Math.floor(s || 0))
        const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60
        const dos = n => (n < 10 ? "0" : "") + n
        return h > 0 ? h + ":" + dos(m) + ":" + dos(x) : m + ":" + dos(x)
    }
}
