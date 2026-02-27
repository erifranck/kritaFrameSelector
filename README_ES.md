# Frame Selector - Plugin para Krita

> **[Read in English](README.md)**

Un plugin para Krita que permite a los animadores **reutilizar frames** a lo largo del timeline con un solo click. Analiza tu archivo `.kra` para detectar frames \u00fanicos, los muestra como tarjetas con miniatura, y te permite clonar cualquier frame a la posici\u00f3n actual del timeline.

**\u00bfLa caracter\u00edstica clave?** Los frames clonados en Krita comparten memoria \u2014 edit\u00e1s uno y todos los clones se actualizan autom\u00e1ticamente.

![Krita 5.x](https://img.shields.io/badge/Krita-5.x-blue)
![Python 3](https://img.shields.io/badge/Python-3-green)
![License: GPL-3.0](https://img.shields.io/badge/License-GPL--3.0-orange)

---

## \u00bfPor qu\u00e9 Frame Selector?

Si alguna vez animaste en Krita, conoc\u00e9s el dolor:

- **Lip sync**: Los personajes repiten formas de boca (A, E, O, cerrada) decenas de veces. Sin clonaci\u00f3n, estar\u00edas duplicando datos de p\u00edxeles por cada frame individual.
- **Ciclos de caminata/corrida**: Reutiliz\u00e1 las mismas posiciones de piernas en un loop sin copiar frames manualmente.
- **Parpadeos y expresiones**: Un personaje parpadea cada pocos segundos \u2014 son los mismos 2-3 frames una y otra vez.
- **Fondos est\u00e1ticos**: Manten\u00e9 un fondo fijo a lo largo de cientos de frames sin desperdiciar memoria.

Frame Selector hace que este flujo de trabajo sea **r\u00e1pido y visual**. Escane\u00e1 tu documento, ve\u00e9 todos los frames \u00fanicos como tarjetas, hace\u00e9 click para clonar.

---

## C\u00f3mo Funciona

1. **Escaneo**: El plugin guarda tu documento y lee el archivo `.kra` (que internamente es un archivo ZIP). Parsea `maindoc.xml` y los `keyframes.xml` de cada capa para detectar cu\u00e1les frames son \u00fanicos y cu\u00e1les son clones.

2. **Visualizaci\u00f3n**: Los frames \u00fanicos aparecen como tarjetas con miniatura en el panel Docker. Los frames vac\u00edos/transparentes se filtran autom\u00e1ticamente.

3. **Clonaci\u00f3n**: Hac\u00e9 click en cualquier tarjeta y el plugin clona ese frame a la **posici\u00f3n actual del timeline** en la **capa activa**. El clon comparte datos de p\u00edxeles con el original \u2014 cero costo extra de memoria.

4. **Auto-refresh**: Si un frame se movi\u00f3 o fue modificado, el plugin detecta el estado desactualizado y re-escanea autom\u00e1ticamente.

---

## Instalaci\u00f3n

### M\u00e9todo 1: Importar ZIP (Recomendado)

Esta es la forma est\u00e1ndar de instalar plugins de Python en Krita.

1. And\u00e1 a la p\u00e1gina de [Releases](../../releases) y descarg\u00e1 `frame_selector.zip`
2. Abr\u00ed Krita
3. And\u00e1 a **Herramientas > Scripts > Importar Plugin de Python desde Archivo...**
4. Seleccion\u00e1 el `frame_selector.zip` descargado
5. Reinici\u00e1 Krita
6. And\u00e1 a **Configuraci\u00f3n > Configurar Krita > Administrador de Plugins de Python**
7. Activ\u00e1 **Frame Selector**
8. Reinici\u00e1 Krita una vez m\u00e1s

El panel Docker va a aparecer en **Configuraci\u00f3n > Paneles > Frame Selector**.

### M\u00e9todo 2: install.sh (Para Desarrolladores)

Si clonaste el repo y quer\u00e9s instalar directamente:

```bash
git clone https://github.com/your-username/KritaFrameSelector.git
cd KritaFrameSelector
chmod +x install.sh
./install.sh
```

El script auto-detecta tu sistema operativo (macOS, Linux, Windows/MSYS) y copia los archivos del plugin al directorio correcto de Krita:

| SO      | Ruta por defecto                                |
| ------- | ----------------------------------------------- |
| macOS   | `~/Library/Application Support/krita/pykrita`   |
| Linux   | `~/.local/share/krita/pykrita`                  |
| Windows | `%APPDATA%/krita/pykrita`                       |

Tambi\u00e9n pod\u00e9s pasar una ruta personalizada:

```bash
./install.sh /ruta/a/tu/krita/pykrita
```

Despu\u00e9s de ejecutar el script, reinici\u00e1 Krita y activ\u00e1 el plugin en **Configuraci\u00f3n > Configurar Krita > Administrador de Plugins de Python**.

---

## Uso

1. Abr\u00ed un documento de animaci\u00f3n en Krita (tiene que tener al menos una capa de pintura con keyframes)
2. Abr\u00ed el panel **Frame Selector** (**Configuraci\u00f3n > Paneles > Frame Selector**)
3. Hac\u00e9 click en el bot\u00f3n **\u21bb Refresh** para escanear el documento activo
4. Los frames \u00fanicos aparecen como tarjetas en el panel
5. Naveg\u00e1 a la posici\u00f3n deseada en el timeline
6. Hac\u00e9 click en una tarjeta para **clonar el frame** a la posici\u00f3n actual en la capa activa

### Tips

- **Edit\u00e1 una vez, actualiz\u00e1 en todos lados**: Como los clones comparten datos de p\u00edxeles, pintar sobre cualquier clon actualiza todas las instancias. Esta es una caracter\u00edstica nativa de Krita que Frame Selector aprovecha.
- **Refresh despu\u00e9s de cambios**: Si agreg\u00e1s/elimin\u00e1s frames manualmente, toc\u00e1 Refresh para re-escanear.
- **La capa activa importa**: El clon siempre se coloca en la capa seleccionada actualmente.

---

## Estructura del Proyecto

```
KritaFrameSelector/
\u251c\u2500\u2500 frame_selector/                  # Paquete del plugin
\u2502   \u251c\u2500\u2500 __init__.py                  # Entry point del plugin para Krita
\u2502   \u251c\u2500\u2500 frame_manager.py             # L\u00f3gica de escaneo de frames y clonaci\u00f3n inteligente
\u2502   \u251c\u2500\u2500 frame_selector_docker.py     # UI del panel Docker (Qt)
\u2502   \u251c\u2500\u2500 frame_store.py               # Almacenamiento persistente en JSON para frames registrados
\u2502   \u251c\u2500\u2500 frame_thumbnail_delegate.py  # Renderizado personalizado de tarjetas con miniaturas
\u2502   \u251c\u2500\u2500 krita_parser.py              # Analizador forense de archivos .kra (parseo ZIP/XML)
\u2502   \u2514\u2500\u2500 manual.html                  # Manual del plugin
\u251c\u2500\u2500 frame_selector.desktop           # Descriptor del plugin para Krita
\u251c\u2500\u2500 install.sh                       # Script de instalaci\u00f3n para desarrolladores
\u251c\u2500\u2500 README.md                        # Versi\u00f3n en ingl\u00e9s
\u2514\u2500\u2500 README_ES.md                     # Este archivo
```

---

## Detalles T\u00e9cnicos

### C\u00f3mo Funciona la Detecci\u00f3n de Clones en .kra

Un archivo `.kra` es un archivo ZIP. Adentro tiene:

- **`maindoc.xml`** que describe la estructura del \u00e1rbol de capas
- **Archivos `<layerN>.keyframes.xml`** que describen el timing de keyframes por capa

En un archivo `keyframes.xml`, cada elemento `<keyframe>` tiene un `time` (posici\u00f3n en el timeline) y un atributo `frame` (referencia a datos de p\u00edxeles). Cuando dos keyframes apuntan al **mismo valor de `frame`**, son clones \u2014 comparten datos de p\u00edxeles id\u00e9nticos en memoria.

```xml
<!-- Estos dos keyframes son clones (ambos referencian "layer5") -->
<keyframe time="0" frame="layer5" />
<keyframe time="24" frame="layer5" />

<!-- Este es \u00fanico (referencia datos diferentes) -->
<keyframe time="12" frame="layer5.f12" />
```

El plugin lee estos archivos para construir un mapa de frames \u00fanicos vs. clonados, filtra los frames vac\u00edos (tama\u00f1o de archivo < 100 bytes en el ZIP), y presenta solo los frames significativos al usuario.

---

## Requisitos

- **Krita 5.x** o posterior
- **Python 3** (incluido con Krita)

No se requieren dependencias externas.

---

## Licencia

Este proyecto est\u00e1 licenciado bajo la Licencia GPL-3.0 - la misma licencia que Krita.

---

## Contribuir

\u00a1Las contribuciones son bienvenidas! Sent\u00edte libre de abrir issues o pull requests.

1. Hace\u00e9 un fork del repositorio
2. Cre\u00e1 una rama para tu feature (`git checkout -b feature/feature-genial`)
3. Commite\u00e1 tus cambios
4. Push\u00e1 a la rama
5. Abr\u00ed un Pull Request
