# Elementun Art · Dragón Elemental

Animación web optimizada generada a partir de la hoja de sprites `source/dragon-sheet.webp`.
Abre `index.html` (con un servidor local, p. ej. `npx http-server .`) para ver la demo.

## Uso

Copia la carpeta `dist/` a tu web y:

```html
<link rel="preload" as="image" href="dist/dragon-atlas.avif" type="image/avif">
<script type="module" src="dist/dragon-sprite.min.js"></script>

<dragon-sprite anim="idle" scale="2"></dragon-sprite>
```

```js
const dragon = document.querySelector("dragon-sprite");
await dragon.play("fire");               // fuego y vuelve a "idle"
await dragon.play("death", { then: "none" }); // se queda en el último fotograma
dragon.addEventListener("animationdone", (e) => console.log(e.detail.anim));
```

### Animaciones

| Nombre  | Fotogramas | Bucle |
|---------|-----------:|:-----:|
| `idle`  | 7 | ✔ |
| `walk`  | 7 | ✔ |
| `fly`   | 6 | ✔ |
| `fire`  | 3 | — |
| `ice`   | 3 | — |
| `cast`  | 5 | — |
| `roar`  | 2 | — |
| `rest`  | 4 | — |
| `death` | 3 | — |

### Atributos

| Atributo    | Descripción |
|-------------|-------------|
| `anim`      | Animación actual (por defecto `idle`). |
| `scale`     | Factor de escala (por defecto `1`). |
| `speed`     | Multiplicador de velocidad. |
| `fps`       | Fotogramas por segundo exactos. |
| `then`      | Animación al terminar una sin bucle (`idle` por defecto, `none` para congelar). |
| `flip`      | Refleja al dragón para que mire a la izquierda. |
| `paused`    | Pausa la animación. |
| `pixelated` | Escalado nítido (mejor con escalas enteras). |
| `src`       | Ruta base del atlas sin extensión, si lo alojas en otra carpeta/CDN. |

El borde inferior del elemento coincide con la línea de suelo del dragón, así que basta con
colocarlo sobre tu "suelo" con `position:absolute; bottom:…`. Todas las animaciones comparten
el mismo punto de anclaje: cambiar de una a otra no produce saltos.

## Optimización

- **Un solo atlas** (1128×565) empaquetado por estantes: AVIF **150 KB**, respaldo WebP **237 KB**
  (la hoja original pesa 394 KB). El navegador elige el formato con `image-set()`.
- **JS: 4,5 KB minificado / 2 KB gzip**, sin dependencias; los metadatos van incrustados.
- **Animación 100 % CSS** con `transform` + `steps()`: se ejecuta en el compositor, sin
  `requestAnimationFrame` ni repintados.
- **Pausa automática fuera de pantalla** (IntersectionObserver) y respeto a
  `prefers-reduced-motion`.
- Celdas separadas 2 px para evitar sangrado entre fotogramas al escalar.

## Regenerar el atlas

```bash
pip install pillow numpy scipy scikit-image
python3 tools/build_atlas.py
```

`tools/build_atlas.py` separa los fotogramas (se solapan en la hoja original, por eso usa
*watershed* a partir de semillas), los alinea por animación, empaqueta el atlas, lo exporta en
AVIF/WebP e inyecta los metadatos en `dist/dragon-sprite.js` (y lo minifica con esbuild si hay Node).
Para cambiar velocidades o agrupar fotogramas de otra forma, edita el diccionario `ANIMS`.
