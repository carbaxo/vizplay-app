"""
Núcleo de VizPlay para escritorio: la misma lógica que la app de Android
(`android-standalone/.../*.kt`), portada a Python y sin nada de interfaz.

Cada módulo es el equivalente de un fichero Kotlin y conserva sus decisiones
(y los porqués, en los comentarios): si algo se arregla en Android, aquí se
arregla en el mismo sitio.

Todas las funciones de red son BLOQUEANTES a propósito. Quien las llama (el
puente con QML) las lanza en un hilo aparte; así el núcleo se puede probar
llamándolo sin más, sin bucles de eventos de por medio.
"""
