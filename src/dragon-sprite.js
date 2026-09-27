/**
 * <dragon-sprite> — componente web para animar el dragón elemental.
 *
 * Rendimiento:
 *  - Un único atlas (AVIF con respaldo WebP) y cero dependencias.
 *  - Animación 100 % CSS con `transform` (se ejecuta en el compositor, sin
 *    repintados ni trabajo por fotograma en JavaScript).
 *  - Se pausa sola fuera de pantalla (IntersectionObserver) y respeta
 *    `prefers-reduced-motion`.
 *
 * Atributos:
 *   anim     idle | walk | fly | fire | ice | cast | roar | rest | death
 *   scale    factor de escala (por defecto 1)
 *   fps      sobrescribe los fotogramas por segundo de la animación
 *   speed    multiplicador de velocidad (por defecto 1)
 *   then     animación tras terminar una que no se repite (por defecto "idle";
 *            "none" congela el último fotograma)
 *   flip     refleja horizontalmente (mira a la izquierda)
 *   paused   detiene la animación
 *   pixelated  escalado nítido (ideal con escalas enteras: 2, 3, 4…)
 *   src      ruta base del atlas sin extensión (por defecto, junto a este script)
 *
 * API:
 *   el.play("fire").then(() => …)   // promesa que se resuelve al terminar
 *   evento "animationdone" con detail.anim
 */
const ATLAS = /*__ATLAS__*/ null;

const BASE = new URL(".", import.meta.url).href;
const A = ATLAS.anims;

// Caja común centrada en el ancla (centro del cuerpo / línea de suelo): todas
// las animaciones comparten posición, así que cambiar de una a otra no salta.
// El borde inferior del elemento es la línea de suelo; lo que quede por debajo
// (p. ej. la cola durante el vuelo) desborda sin afectar al layout.
const HALF_W = Math.max(...Object.values(A).map((a) => Math.max(a.ax, a.w - a.ax)));
const UP = Math.max(...Object.values(A).map((a) => a.ay));
const BOX_W = HALF_W * 2;
const BOX_H = UP;

const keyframes = Object.entries(A)
  .map(([name, a]) => {
    const x1 = a.x + (a.frames - 1) * a.stride;
    return `@keyframes ${name}{from{transform:translate3d(${-a.x}px,${-a.y}px,0)}to{transform:translate3d(${-x1}px,${-a.y}px,0)}}`;
  })
  .join("");

const css = (src) => `
:host{display:inline-block;position:relative;vertical-align:bottom;contain:layout style;
  --s:1;width:calc(${BOX_W}px*var(--s));height:calc(${BOX_H}px*var(--s))}
:host([hidden]){display:none}
.stage{position:absolute;inset:0 auto auto 0;width:${BOX_W}px;height:${BOX_H}px;
  transform-origin:0 0;transform:scale(var(--s))}
:host([flip]) .stage{transform:translateX(calc(${BOX_W}px*var(--s))) scale(calc(var(--s)*-1),var(--s))}
.view{position:absolute;overflow:hidden}
.sheet{width:${ATLAS.width}px;height:${ATLAS.height}px;will-change:transform;
  background:url("${src}.webp") 0 0/100% 100% no-repeat;
  background-image:image-set(url("${src}.avif") type("image/avif"),url("${src}.webp") type("image/webp"));
  animation-fill-mode:both}
:host([pixelated]) .sheet{image-rendering:pixelated}
:host([paused]) .sheet,.sheet.off{animation-play-state:paused}
@media (prefers-reduced-motion:reduce){.sheet{animation-play-state:paused!important}}
${keyframes}`;

class DragonSprite extends HTMLElement {
  static observedAttributes = ["anim", "scale", "fps", "speed", "src"];
  static anims = Object.keys(A);
  /** Metadatos de una animación: { frames, fps, loop } */
  static info = (name) => A[name] && { frames: A[name].frames, fps: A[name].fps, loop: A[name].loop };
  static #io =
    "IntersectionObserver" in window
      ? new IntersectionObserver(
          (entries) => entries.forEach((e) => e.target.#sheet.classList.toggle("off", !e.isIntersecting)),
          { rootMargin: "64px" }
        )
      : null;

  #view;
  #sheet;
  #style;
  #resolve = null;

  constructor() {
    super();
    const root = this.attachShadow({ mode: "open" });
    this.#style = document.createElement("style");
    const stage = document.createElement("div");
    stage.className = "stage";
    stage.setAttribute("part", "stage");
    this.#view = document.createElement("div");
    this.#view.className = "view";
    this.#sheet = document.createElement("div");
    this.#sheet.className = "sheet";
    this.#view.append(this.#sheet);
    stage.append(this.#view);
    root.append(this.#style, stage);
    this.#sheet.addEventListener("animationend", () => this.#ended());
  }

  connectedCallback() {
    if (!this.hasAttribute("role")) this.setAttribute("role", "img");
    if (!this.hasAttribute("aria-label")) this.setAttribute("aria-label", "Dragón elemental animado");
    if (!this.#style.textContent) this.#applySrc();
    this.#render();
    DragonSprite.#io?.observe(this);
  }

  disconnectedCallback() {
    DragonSprite.#io?.unobserve(this);
  }

  attributeChangedCallback(name) {
    if (!this.isConnected) return;
    if (name === "src") this.#applySrc();
    else if (name === "scale") this.style.setProperty("--s", this.scale);
    else this.#render();
  }

  get anim() {
    const a = this.getAttribute("anim");
    return a in A ? a : "idle";
  }
  set anim(v) {
    this.setAttribute("anim", v);
  }
  get scale() {
    return Math.max(0.1, parseFloat(this.getAttribute("scale")) || 1);
  }
  set scale(v) {
    this.setAttribute("scale", v);
  }

  /** Reproduce una animación; la promesa se resuelve al terminar (o al interrumpirse). */
  play(anim, { then } = {}) {
    if (then !== undefined) this.setAttribute("then", then);
    this.#settle();
    // reinicia aunque sea la misma animación
    if (this.getAttribute("anim") === anim) this.#render(true);
    else this.anim = anim;
    return A[anim]?.loop ? Promise.resolve() : new Promise((r) => (this.#resolve = r));
  }

  #applySrc() {
    const src = this.getAttribute("src") || BASE + ATLAS.image;
    this.#style.textContent = css(src);
    this.style.setProperty("--s", this.scale);
  }

  #render(restart = false) {
    const name = this.anim;
    const a = A[name];
    const fps = (parseFloat(this.getAttribute("fps")) || a.fps) * (parseFloat(this.getAttribute("speed")) || 1);
    const v = this.#view.style;
    v.left = HALF_W - a.ax + "px";
    v.top = UP - a.ay + "px";
    v.width = a.w + "px";
    v.height = a.h + "px";
    const s = this.#sheet.style;
    // Solo longhands: así `paused` y la pausa fuera de pantalla (hoja de estilos)
    // siguen controlando animation-play-state.
    if (restart) {
      s.animationName = "none";
      void this.#sheet.offsetWidth; // fuerza reflow para reiniciar
    }
    s.animationDuration = a.frames / fps + "s";
    s.animationTimingFunction = `steps(${a.frames},jump-none)`;
    s.animationIterationCount = a.loop ? "infinite" : "1";
    s.animationName = name;
    if (a.loop) this.#settle();
  }

  #ended() {
    const done = this.anim;
    this.dispatchEvent(new CustomEvent("animationdone", { detail: { anim: done } }));
    this.#settle();
    const next = this.getAttribute("then") ?? "idle";
    if (next !== "none" && next in A && next !== done) this.anim = next;
  }

  #settle() {
    this.#resolve?.();
    this.#resolve = null;
  }
}

if (!customElements.get("dragon-sprite")) customElements.define("dragon-sprite", DragonSprite);
export default DragonSprite;
