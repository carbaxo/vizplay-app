import QtQuick

// Iconos de Windows (Segoe MDL2 Assets, que viene con Windows 10 y 11). Así no
// hay que empaquetar imágenes y se tiñen como cualquier texto.
Text {
    id: raiz
    property string nombre: ""
    property int tam: Tema.px(18)
    readonly property var mapa: ({
        "inicio": "", "buscar": "", "descargar": "", "ajustes": "",
        "atras": "", "play": "", "pausa": "", "volumen": "",
        "mudo": "", "completa": "", "ventana": "", "recargar": "",
        "borrar": "", "editar": "", "cerrar": "", "abajo": "",
        "arriba": "", "derecha": "", "izquierda": "", "corazon": "",
        "corazonLleno": "", "subtitulos": "", "audio": "", "siguiente": "",
        "carpeta": "", "ok": "", "persona": "", "pegar": "",
        "tv": "", "enlace": "", "info": "", "mas": "", "velocidad": "",
        "atrasar": "", "adelantar": "", "abrir": "", "salir": "", "ver": "", "ocultar": ""
    })
    text: mapa[nombre] || ""
    font.family: Tema.iconos
    font.pixelSize: tam
    color: "white"
    verticalAlignment: Text.AlignVCenter
    horizontalAlignment: Text.AlignHCenter
}
