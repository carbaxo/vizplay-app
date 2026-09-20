package com.carbaxo.torrentbox

import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * Busca en **tu propia cuenta de Real-Debrid** y lo ofrece como un motor más en la
 * ficha, junto a Peerflix y Torrentio.
 *
 * Esto es lo que cierra el círculo: cuando un título no aparece en ningún addon —
 * el caso de las series infantiles en castellano — se añade el torrent a mano una
 * vez, y a partir de ahí **sale solo en la ficha**, como cualquier otro enlace, con
 * su reproducción, su descarga y su selector de capítulos si es un pack.
 *
 * Es el motor más fiable de los tres, y por eso va primero en la lista:
 *
 *  - Usa la **API oficial** de RD, así que no se rompe cuando una web cambia.
 *  - Lo que sale ya está **en tu cuenta**: se ve al instante, sin esperar semillas
 *    ni depender de que RD lo tenga en caché.
 */
object RdEngine {

    /**
     * Copia de la lista de torrents con caducidad corta. Sin esto, cada ficha (y
     * cada episodio que se toca) pediría la lista entera a Real-Debrid otra vez.
     */
    private var cache: List<RealDebrid.Torrent> = emptyList()
    private var cacheAt = 0L
    private const val TTL_MS = 60_000L

    private val io = Executors.newCachedThreadPool()

    /**
     * Archivos de cada pack, por id de torrent. Sin caducidad a propósito: los
     * archivos de un torrent que RD ya ha terminado no cambian nunca, y cada
     * consulta es una llamada más a la API por cada pack y cada episodio que se
     * abre.
     */
    private val filesCache = ConcurrentHashMap<String, List<RealDebrid.RdFile>>()

    /** Palabras del título que valen para comparar (fuera artículos y ruido). */
    private fun tokens(s: String): List<String> =
        s.lowercase()
            .replace(Regex("[^\\p{L}\\p{N}]+"), " ")
            .split(' ')
            .filter { it.length >= 3 && it !in STOP }

    private val STOP = setOf("the", "los", "las", "una", "unos", "unas", "del", "por", "con", "para")

    /**
     * ¿Este torrent de la cuenta es de este título?
     *
     * Se exige que **todas** las palabras del título aparezcan en el nombre del
     * torrent, no que se parezcan: los nombres de los torrents traen mucha morralla
     * (grupo, códec, año) y comparar el conjunto entero no casaría nunca. Así
     * «Peppa Pig» encuentra «Peppa.Pig.1.Temporada.1x01.al.1x13.HDTV».
     */
    private fun matches(title: String, torrentName: String): Boolean {
        val t = tokens(title)
        if (t.isEmpty()) return false
        val n = torrentName.lowercase().replace(Regex("[^\\p{L}\\p{N}]+"), " ")
        return t.all { n.contains(it) }
    }

    /** ¿El nombre dice que es una temporada o serie completa? */
    private fun looksPack(name: String): Boolean = Regex(
        "temporada|completa|complete|season|\\d+x\\d+\\s*al\\s*\\d+x\\d+|pack|s\\d{2}(?!e\\d)",
        RegexOption.IGNORE_CASE
    ).containsMatchIn(name)

    private fun toResult(t: RealDebrid.Torrent): Search.Result = Search.Result(
        name = t.name,
        infoHash = t.hash,
        seeders = t.seeders,
        sizeBytes = t.bytes,
        magnet = Search.buildMagnet(t.hash, t.name),
        // Lo que se añade a mano aquí es casi siempre castellano; si el nombre lo
        // dice, se respeta lo que diga.
        lang = Lang.detectFromTitle(t.name) ?: "es",
        quality = Search.quality(t.name),
        engine = Search.ENGINE_RD,
        info = if (t.ready) "✅ en tu Real-Debrid" else "⏳ en tu Real-Debrid (${RealDebrid.statusEs(t.status)})",
        // Varios archivos = pack, aunque el nombre no lo diga: es lo que hace que
        // caiga en el selector de capítulos.
        pack = looksPack(t.name) || t.links > 1
    )

    /**
     * Un PACK de la cuenta, repartido en un resultado POR CAPÍTULO.
     *
     * Es lo que hace que un pack deje de ser un cajón. Antes, una temporada
     * entera era UN enlace: salía igual en todos los episodios, había que abrirlo
     * y elegir capítulo a mano, y como se reproducía siempre "desde el pack", el
     * progreso se apuntaba en el episodio que estuviera abierto en la ficha. O
     * sea: ni se veía por dónde ibas, ni salía la marca de visto donde tocaba.
     *
     * Aquí se le pregunta a RD por los archivos (el pack YA está en la cuenta, así
     * que es solo una consulta: no hay que bajar nada) y se saca un enlace por
     * fichero, con el nombre del propio fichero. A partir de ahí el resto de la
     * app hace sola lo que hay que hacer: el filtro por episodio coloca cada uno
     * bajo su capítulo, y al reproducirlo el progreso se guarda con su temporada y
     * su episodio.
     *
     * Los ficheros de los que NO se puede sacar el episodio del nombre no se
     * tiran: se quedan como el pack de siempre, con su "elegir capítulo".
     */
    private fun expand(t: RealDebrid.Torrent): List<Search.Result> {
        // Solo se guarda lo que ha venido con algo: cachear una respuesta vacía
        // dejaría el pack sin repartir durante toda la sesión por un fallo de red
        // de un momento.
        val files = filesCache[t.id] ?: RealDebrid.filesOfBlocking(t.id)
            .also { if (it.isNotEmpty()) filesCache[t.id] = it }
        val conEpisodio = files.mapNotNull { f ->
            val ep = Search.episodeOf(f.name.substringAfterLast('/')) ?: return@mapNotNull null
            f to ep
        }
        // Si no se ha podido situar NINGUNO, el pack sigue siendo un pack
        if (conEpisodio.isEmpty()) return listOf(toResult(t))
        return conEpisodio.map { (f, ep) ->
            val nombre = f.name.substringAfterLast('/')
            // El idioma y la calidad se leen del fichero Y del nombre del pack: los
            // ficheros sueltos suelen ir pelados ("3x05.mkv") y es el pack el que
            // dice que es castellano y 1080p.
            val combinado = "$nombre\n${t.name}"
            Search.Result(
                name = nombre,
                infoHash = t.hash,
                seeders = t.seeders,
                sizeBytes = f.bytes,
                magnet = Search.buildMagnet(t.hash, nombre),
                lang = Lang.detectFromTitle(combinado) ?: "es",
                quality = Search.quality(combinado),
                engine = Search.ENGINE_RD,
                // El "%02d" se resuelve APARTE. Aplicando .format() sobre la
                // cadena ya interpolada, un nombre de torrent con un '%' dentro
                // (los hay, vienen URL-codificados) la haría reventar.
                info = "✅ en tu Real-Debrid · " + "%dx%02d".format(ep.first, ep.second) +
                    " del pack «${t.name.take(40)}»",
                pack = false,
                fileLink = f.link
            )
        }
    }

    /**
     * Enlaces de la cuenta que casan con el título. Nunca falla hacia fuera: si RD
     * no contesta, devuelve la lista vacía y los demás motores siguen su camino.
     *
     * Va SIEMPRE a un hilo aparte, incluso cuando la lista de torrents está en
     * memoria: repartir un pack pregunta a RD por sus archivos, y eso no puede
     * pasar en el hilo principal.
     */
    fun streams(title: String, onResult: (List<Search.Result>?, String?) -> Unit) {
        if (!RealDebrid.configured) return onResult(emptyList(), null)
        val fresh = System.currentTimeMillis() - cacheAt < TTL_MS
        if (fresh && cache.isNotEmpty()) {
            val suyos = cache.filter { matches(title, it.name) }
            io.submit { onResult(suyos.flatMap { resultsFor(it) }, null) }
            return
        }
        RealDebrid.torrents { list, _ ->
            if (list == null) return@torrents onResult(emptyList(), null)
            cache = list; cacheAt = System.currentTimeMillis()
            onResult(list.filter { matches(title, it.name) }.flatMap { resultsFor(it) }, null)
        }
    }

    /**
     * Un torrent de la cuenta, como enlaces. Un pack TERMINADO se reparte por
     * capítulos; lo demás va tal cual.
     *
     * Se exige `ready` porque los archivos definitivos (y sus enlaces) no existen
     * hasta que RD acaba: mientras baja, se enseña el pack con su estado, que es
     * información útil, en vez de nada.
     */
    private fun resultsFor(t: RealDebrid.Torrent): List<Search.Result> =
        if (t.ready && t.links > 1) expand(t) else listOf(toResult(t))

    /** Olvida la copia: se llama al añadir algo, para que salga ya en la ficha. */
    fun invalidate() { cacheAt = 0L }
}
