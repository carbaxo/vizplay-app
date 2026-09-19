package com.carbaxo.torrentbox

import okhttp3.Dns
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import org.json.JSONObject
import java.net.ConnectException
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.URI
import java.net.UnknownHostException
import java.security.cert.CertificateException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLException

/**
 * Lo común de las peticiones de los motores de búsqueda: el reintento cuando la
 * RED se mete por medio, y el traducir el fallo a algo que se entienda.
 *
 * El caso real que hay detrás, y que conviene no olvidar:
 *
 *     java.security.cert.CertPathValidatorException: Trust anchor for
 *     certification path not found.
 *
 * Eso salía tal cual en la ficha, debajo de la sinopsis, y sin ningún enlace.
 * No es un fallo de la app ni del addon: significa que lo que contesta al otro
 * lado presenta un certificado que Android no reconoce, es decir, que **no es
 * el sitio al que se ha llamado**. Pasa cuando el operador bloquea el dominio
 * por DNS y devuelve su propia página de aviso (lo habitual con los dominios de
 * torrents en España), y también con un DNS privado que filtra, una VPN o un
 * antivirus que inspecciona el tráfico.
 *
 * Que TMDB cargara bien -la carátula y la sinopsis estaban ahí- y solo fallaran
 * los addons es justo la huella de esto: no es la red entera, son esos dominios.
 *
 * Aquí se hacen las dos cosas que se pueden hacer desde la app:
 *
 *  1. **Reintentar resolviendo el nombre por DNS cifrado** (DoH de Cloudflare).
 *     Si el bloqueo es por DNS -lo más frecuente-, el segundo intento va a la IP
 *     de verdad y los enlaces salen. Solo se hace cuando el primer intento ha
 *     fallado por certificado, así que en una red normal no cuesta nada.
 *  2. Si aun así falla, **decirlo en castellano** y con el dominio delante, en
 *     vez de escupir el nombre de la excepción de Java.
 */
object Net {

    /**
     * Pide una URL y, si la red devuelve un certificado que no es del sitio,
     * lo reintenta resolviendo por DNS cifrado.
     *
     * Se le pasa el cliente de cada motor (cada uno tiene sus tiempos de espera)
     * y se reutiliza su gemelo con DoH, que se crea una sola vez: `newBuilder`
     * comparte el pool de conexiones y los hilos del original.
     */
    fun call(client: OkHttpClient, req: Request): Response {
        try {
            return client.newCall(req).execute()
        } catch (e: Exception) {
            if (!intercepted(e)) throw e
            return try {
                withDoh(client).newCall(req).execute()
            } catch (retry: Exception) {
                // Se lanza el fallo ORIGINAL: el del reintento sería "no se pudo
                // resolver por DoH", que despista sobre lo que pasa de verdad.
                e.addSuppressed(retry)
                throw e
            }
        }
    }

    /**
     * ¿El fallo es "la red me ha dado un certificado que no me cuadra"?
     *
     * Se mira la cadena de causas porque OkHttp envuelve: lo que llega es un
     * SSLHandshakeException cuya causa, tres niveles más abajo, es el
     * CertPathValidatorException del mensaje de arriba.
     */
    fun intercepted(t: Throwable?): Boolean {
        var e = t
        var depth = 0
        while (e != null && depth++ < 10) {
            if (e is SSLException || e is CertificateException) return true
            e = e.cause
        }
        return false
    }

    /** Explica un fallo de red nombrando al motor y al dominio. */
    fun explain(who: String, url: String, t: Throwable): String {
        val host = runCatching { URI(url).host }.getOrNull() ?: url
        return when {
            intercepted(t) ->
                "$who: la red está interceptando la conexión con $host (el certificado " +
                    "no es suyo). Suele ser el bloqueo del operador, un DNS privado o una " +
                    "VPN/antivirus con filtro. Prueba con otra red (datos en vez de WiFi, o " +
                    "al revés) o pon el DNS privado en 1.1.1.1."
            t is UnknownHostException ->
                "$who: no se pudo resolver $host. O no hay conexión, o el dominio está bloqueado."
            t is SocketTimeoutException -> "$who: $host no ha contestado a tiempo."
            t is ConnectException -> "$who: no se pudo conectar con $host."
            else -> "$who: ${t.message ?: "error de red"}"
        }
    }

    // --- Reintento por DNS cifrado -------------------------------------------

    private val twins = ConcurrentHashMap<OkHttpClient, OkHttpClient>()

    private fun withDoh(client: OkHttpClient): OkHttpClient =
        twins.getOrPut(client) { client.newBuilder().dns(Doh).build() }

    /**
     * Resolutor por DNS-over-HTTPS (Cloudflare, formato JSON). No se usa el
     * artefacto `okhttp-dnsoverhttps` para no añadir una dependencia por esto:
     * la consulta es una GET y la respuesta, cuatro campos.
     */
    private object Doh : Dns {
        private const val ENDPOINT = "https://cloudflare-dns.com/dns-query"
        private const val TTL_MS = 5 * 60_000L

        /** Cliente propio y SIN DoH: resolver cloudflare-dns.com va por el sistema. */
        private val resolver = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS).readTimeout(5, TimeUnit.SECONDS).build()

        private val cache = ConcurrentHashMap<String, Pair<Long, List<InetAddress>>>()

        override fun lookup(hostname: String): List<InetAddress> {
            cache[hostname]?.let { (until, addrs) ->
                if (System.currentTimeMillis() < until) return addrs
            }
            val out = query(hostname, "A") + query(hostname, "AAAA")
            // Si el DNS cifrado no contesta, al menos que se comporte como antes
            if (out.isEmpty()) return Dns.SYSTEM.lookup(hostname)
            cache[hostname] = (System.currentTimeMillis() + TTL_MS) to out
            return out
        }

        private fun query(host: String, type: String): List<InetAddress> = runCatching {
            val req = Request.Builder()
                .url("$ENDPOINT?name=$host&type=$type")
                .header("Accept", "application/dns-json")
                .build()
            resolver.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@use emptyList<InetAddress>()
                val ans = JSONObject(resp.body?.string() ?: "{}").optJSONArray("Answer")
                    ?: return@use emptyList<InetAddress>()
                val out = ArrayList<InetAddress>()
                for (i in 0 until ans.length()) {
                    val a = ans.getJSONObject(i)
                    // 1 = A, 28 = AAAA. Lo demás (un CNAME por el camino) no es
                    // una dirección y getByName lo mandaría a resolver otra vez.
                    if (a.optInt("type") != 1 && a.optInt("type") != 28) continue
                    // Es un literal: getByName no hace consulta ninguna.
                    runCatching { out.add(InetAddress.getByName(a.optString("data"))) }
                }
                out
            }
        }.getOrDefault(emptyList())
    }
}
