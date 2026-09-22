package com.carbaxo.torrentbox

import android.content.Context
import androidx.compose.runtime.mutableStateListOf
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Progreso de reproducción + "visto", por dispositivo y sincronizado con la
 * nube (states[perfil].progress, mismo esquema que la web).
 *
 * key    = "movie:<tmdb>"  |  "series:<tmdb>:<season>:<episode>"
 * titleId= "movie:<tmdb>"  |  "series:<tmdb>"   (la web marca el título visto)
 * "visto" si position/duration > 0.9.
 */
object WatchStore {
    data class Prog(
        val key: String, val titleId: String, val tmdbId: Int, val type: String,
        val season: Int?, val episode: Int?, val name: String, val poster: String?,
        val position: Double, val duration: Double, val watched: Boolean, val updatedAt: String
    )

    private lateinit var appCtx: Context
    val list = mutableStateListOf<Prog>()

    fun init(ctx: Context) {
        appCtx = ctx.applicationContext
        val raw = sp().getString("progress", null) ?: return
        runCatching { list.addAll(parse(JSONArray(raw))) }
    }

    private fun sp() = appCtx.getSharedPreferences("tcv_prefs", Context.MODE_PRIVATE)
    private fun iso() = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())

    private fun persistLocal() {
        sp().edit().putString("progress", toJson().toString()).apply()
    }

    fun toJson(): JSONArray {
        val arr = JSONArray()
        list.forEach { p ->
            arr.put(JSONObject().apply {
                put("key", p.key); put("titleId", p.titleId); put("tmdbId", p.tmdbId)
                put("type", p.type); if (p.season != null) put("season", p.season)
                if (p.episode != null) put("episode", p.episode)
                put("name", p.name); if (p.poster != null) put("poster", p.poster)
                put("position", p.position); put("duration", p.duration)
                put("watched", p.watched); put("updatedAt", p.updatedAt)
            })
        }
        return arr
    }

    fun parse(arr: JSONArray): List<Prog> {
        val out = ArrayList<Prog>()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val key = o.optString("key")
            if (key.isBlank()) continue
            out.add(Prog(
                key = key,
                titleId = o.optString("titleId", key),
                tmdbId = o.optInt("tmdbId", Regex("(\\d+)").find(o.optString("titleId"))?.value?.toIntOrNull() ?: 0),
                type = if (o.optString("type") == "series" || key.startsWith("series")) "series" else "movie",
                season = if (o.has("season")) o.optInt("season") else null,
                episode = if (o.has("episode")) o.optInt("episode") else null,
                name = o.optString("name", ""),
                poster = o.optString("poster", "").takeIf { it.isNotBlank() && it != "null" },
                position = o.optDouble("position", 0.0),
                duration = o.optDouble("duration", 0.0),
                watched = o.optBoolean("watched", false),
                updatedAt = o.optString("updatedAt", "")
            ))
        }
        return out
    }

    /** Para escribir en Firestore (states[perfil].progress). */
    fun toMaps(): List<Map<String, Any?>> = list.map { p ->
        val m = HashMap<String, Any?>()
        m["key"] = p.key; m["titleId"] = p.titleId; m["tmdbId"] = p.tmdbId; m["type"] = p.type
        if (p.season != null) m["season"] = p.season
        if (p.episode != null) m["episode"] = p.episode
        m["name"] = p.name; if (p.poster != null) m["poster"] = p.poster
        m["position"] = p.position; m["duration"] = p.duration
        m["watched"] = p.watched; m["updatedAt"] = p.updatedAt
        m
    }

    /** Sustituye el estado local por el de la nube (al elegir perfil). */
    fun loadFromMaps(maps: List<Map<String, Any?>>) {
        val arr = JSONArray()
        maps.forEach { arr.put(JSONObject(it)) }
        list.clear(); list.addAll(parse(arr)); persistLocal()
    }

    /**
     * Cada subida a la nube manda la lista ENTERA. En disco se guarda siempre
     * (es barato y local), pero a Firestore no se va más de una vez cada 30 s:
     * con el autoguardado del reproductor, si no, serían seis escrituras por
     * minuto durante toda la película, cada una con todo el historial dentro.
     *
     * Lo que SÍ sube en el momento es el "visto": es el cambio que importa que
     * llegue al resto de aparatos, y pasa una vez por episodio, no cada 10 s.
     */
    private var ultimaNube = 0L
    private const val NUBE_MIN_MS = 30_000L

    private fun subirNube(forzar: Boolean) {
        val ahora = System.currentTimeMillis()
        if (!forzar && ahora - ultimaNube < NUBE_MIN_MS) return
        ultimaNube = ahora
        // no-op si no hay sesión o perfil activo
        runCatching { Sync.saveProgressCloud(toMaps()) }
    }

    /**
     * Sube ya lo que haya pendiente. Se llama al salir del reproductor: si no, la
     * última posición podía quedarse esperando a que pasaran los 30 s que ya no
     * iban a pasar.
     */
    fun flush() = subirNube(true)

    private fun upsert(p: Prog) {
        val i = list.indexOfFirst { it.key == p.key }
        if (i >= 0) list.removeAt(i)
        list.add(0, p)
        persistLocal()
        subirNube(forzar = p.watched)
    }

    /** Registra progreso de reproducción. */
    fun record(tmdbId: Int, type: String, season: Int?, episode: Int?, name: String, poster: String?, position: Double, duration: Double) {
        if (tmdbId <= 0 || position < 5) return
        val isSeries = type == "series" && season != null
        val titleId = "${if (isSeries) "series" else "movie"}:$tmdbId"
        val key = if (isSeries) "series:$tmdbId:$season:${episode ?: 1}" else "movie:$tmdbId"
        val watched = duration > 0 && position / duration > 0.9
        upsert(Prog(key, titleId, tmdbId, if (isSeries) "series" else "movie", season, episode, name, poster, position, duration, watched, iso()))
    }

    /**
     * Marca algo como VISTO sin depender de la duración.
     *
     * [record] decide el "visto" con position/duration > 0.9, y eso falla justo
     * cuando más importa: al terminar un vídeo, muchos reproductores dejan la
     * posición en 0 o no llegan a saber la duración de un stream, así que el
     * episodio que acabas de terminar entero se quedaba sin marcar. Cuando el
     * reproductor dice que ha llegado al final no hay nada que deducir: está
     * visto, y se apunta así.
     *
     * Se conserva la duración que ya hubiera guardada, que es la buena para la
     * barra de progreso.
     */
    fun markWatched(tmdbId: Int, type: String, season: Int?, episode: Int?, name: String, poster: String?) {
        if (tmdbId <= 0) return
        val isSeries = type == "series" && season != null
        val titleId = "${if (isSeries) "series" else "movie"}:$tmdbId"
        val key = if (isSeries) "series:$tmdbId:$season:${episode ?: 1}" else "movie:$tmdbId"
        val prev = progressFor(key)
        val dur = prev?.duration ?: 0.0
        upsert(
            Prog(
                key, titleId, tmdbId, if (isSeries) "series" else "movie", season, episode,
                name.ifBlank { prev?.name ?: "" }, poster ?: prev?.poster,
                position = if (dur > 0) dur else (prev?.position ?: 0.0),
                duration = dur, watched = true, updatedAt = iso()
            )
        )
    }

    fun isWatchedTitle(type: String, tmdbId: Int): Boolean {
        val tid = "${if (type == "series") "series" else "movie"}:$tmdbId"
        return list.any { it.titleId == tid && it.watched }
    }

    fun isWatchedEpisode(tmdbId: Int, season: Int, episode: Int): Boolean =
        list.any { it.key == "series:$tmdbId:$season:$episode" && it.watched }

    /** Progreso de un episodio/título (para reanudar / barra). */
    fun progressFor(key: String): Prog? = list.firstOrNull { it.key == key }

    /** En curso (para "Continuar viendo"). */
    /**
     * Lo empezado y sin acabar. [type] ("movie"/"series") lo limita a ese tipo:
     * en Descubrir, con el filtro en Series no tiene sentido ofrecer películas.
     */
    fun continueWatching(type: String? = null): List<Prog> = list
        .filter { type == null || it.type == type }
        .filter { !it.watched && it.position > 20 && (it.duration <= 0 || it.position / it.duration < 0.95) }
        .sortedByDescending { it.updatedAt }

    /**
     * Semillas para recomendaciones: títulos vistos/en curso, recientes. El
     * recorte a 6 va DESPUÉS de filtrar por tipo; si no, con el filtro en Series
     * las seis últimas podían ser todas películas y no quedaría ninguna semilla.
     */
    fun seeds(type: String? = null): List<Pair<Int, String>> = list
        .sortedByDescending { it.updatedAt }
        .filter { type == null || it.type == type }
        .map { it.tmdbId to it.type }
        .distinct()
        .filter { it.first > 0 }
        .take(6)
}
