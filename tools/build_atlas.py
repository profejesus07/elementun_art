#!/usr/bin/env python3
"""Extrae los fotogramas de la hoja de sprites original y genera un atlas
optimizado (una tira horizontal por animación, celdas de tamaño uniforme
dentro de cada tira) + los metadatos que usa el componente web.

Uso:  python3 tools/build_atlas.py
Requiere: pillow (con soporte AVIF), numpy, scipy, scikit-image
"""
import gzip
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage.segmentation import watershed

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source" / "dragon-sheet.webp"
OUT = ROOT / "dist"
GAP = 2  # separación transparente entre celdas para evitar sangrado al escalar

# Semillas (x, y) de cada fotograma en la hoja original, fila por fila.
# Los fotogramas se solapan entre sí, así que se separan con watershed.
ROWS = [
    [(62, 55), (178, 55), (290, 55), (415, 55), (530, 55), (655, 55), (773, 55)],
    [(62, 150), (185, 150), (315, 150), (445, 150), (570, 150), (685, 150), (785, 150)],
    [(80, 250), (215, 250), (325, 250), (450, 250), (605, 250), (760, 250)],
    [(65, 355), (195, 355), (340, 355), (450, 355), (590, 355), (750, 355)],
    [(55, 445), (165, 445), (285, 445), (400, 445), (520, 445), (635, 445), (760, 445)],
    [(65, 530), (190, 530), (315, 530), (435, 530), (555, 530), (665, 530), (770, 530)],
]
# Semillas extra (el aliento de fuego/hielo pertenece al dragón de su izquierda)
EXTRA = {
    (3, 0): [(130, 355)], (3, 1): [(255, 350)], (3, 2): [(395, 368)],
    (3, 3): [(525, 355)], (3, 4): [(655, 355)], (3, 5): [(815, 350)],
}

# Animaciones: nombre -> (fila, [índices de fotograma], fps, bucle, anclaje)
ANIMS = {
    "idle":  (0, [0, 1, 2, 3, 4, 5, 6], 8,  True,  "bottom"),
    "walk":  (1, [0, 1, 2, 3, 4, 5, 6], 10, True,  "bottom"),
    "fly":   (2, [0, 1, 2, 3, 4, 5],    10, True,  "center"),
    "fire":  (3, [0, 1, 2],             9,  False, "bottom"),
    "ice":   (3, [3, 4, 5],             9,  False, "bottom"),
    "cast":  (4, [0, 1, 2, 3, 4],       9,  False, "bottom"),
    "roar":  (4, [5, 6],                5,  False, "bottom"),
    "rest":  (5, [0, 1, 2, 3],          6,  False, "bottom"),
    "death": (5, [4, 5, 6],             6,  False, "bottom"),
}


def extract_frames(img):
    rgba = np.asarray(img)
    mask = rgba[:, :, 3] > 8
    ys, xs = np.nonzero(mask)
    markers = np.zeros(mask.shape, np.int32)
    labels = {}
    lid = 0
    for r, row in enumerate(ROWS):
        for c, seed in enumerate(row):
            lid += 1
            labels[(r, c)] = lid
            for sx, sy in [seed] + EXTRA.get((r, c), []):
                # engancha la semilla al píxel opaco más cercano
                i = np.argmin((xs - sx) ** 2 + (ys - sy) ** 2)
                y0, x0 = ys[i], xs[i]
                yy, xx = np.ogrid[: mask.shape[0], : mask.shape[1]]
                disk = ((yy - y0) ** 2 + (xx - x0) ** 2 <= 16) & mask
                markers[disk] = lid
    dist = ndimage.distance_transform_edt(mask)
    seg = watershed(-dist, markers, mask=mask)

    frames = {}
    for key, l in labels.items():
        m = seg == l
        # descarta motas sueltas
        cc, n = ndimage.label(m)
        if n > 1:
            sizes = ndimage.sum(m, cc, range(1, n + 1))
            for i, s in enumerate(sizes, 1):
                if s < 12:
                    m[cc == i] = False
        yy, xx = np.nonzero(m)
        y0, y1, x0, x1 = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
        crop = rgba[y0:y1, x0:x1].copy()
        crop[~m[y0:y1, x0:x1]] = 0
        # punto de anclaje: centro horizontal del cuerpo (mitad inferior)
        low = m[y0:y1, x0:x1][int((y1 - y0) * 0.55):]
        lx = np.nonzero(low)[1]
        ax = float(np.median(lx)) if len(lx) else (x1 - x0) / 2
        cy = float(np.nonzero(m[y0:y1, x0:x1])[0].mean())
        frames[key] = dict(img=crop, ax=ax, cy=cy)
    return frames


def build():
    img = Image.open(SRC).convert("RGBA")
    frames = extract_frames(img)

    strips = []
    for name, (row, idx, fps, loop, anchor) in ANIMS.items():
        fr = [frames[(row, i)] for i in idx]
        # caja común alineada al ancla
        left = max(f["ax"] for f in fr)
        right = max(f["img"].shape[1] - f["ax"] for f in fr)
        if anchor == "bottom":
            top = max(f["img"].shape[0] for f in fr)
            offs_y = [top - f["img"].shape[0] for f in fr]
            h = top
        else:
            up = max(f["cy"] for f in fr)
            down = max(f["img"].shape[0] - f["cy"] for f in fr)
            offs_y = [round(up - f["cy"]) for f in fr]
            h = int(np.ceil(up + down))
        w = int(np.ceil(left + right))
        cells = []
        for f, oy in zip(fr, offs_y):
            ox = int(round(left - f["ax"]))
            cells.append((Image.fromarray(f["img"]), ox, oy))
        ay = h if anchor == "bottom" else int(round(up + max(
            f["img"].shape[0] - f["cy"] for f in fr) * 0.8))
        strips.append(dict(name=name, w=w, h=h, cells=cells, fps=fps, loop=loop,
                           ax=int(round(left)), ay=ay))

    # Cada tira guarda su ancla (ax = centro del cuerpo, ay = línea de suelo)
    # para que el componente alinee las animaciones entre sí y no haya saltos.
    # Empaquetado por estantes: varias tiras cortas comparten fila del atlas.
    atlas_w = max(len(s["cells"]) * (s["w"] + GAP) for s in strips)
    shelves = []  # [y, altura, x_libre]
    placed = []
    y_next = 0
    for s in sorted(strips, key=lambda s: -s["h"]):
        sw = len(s["cells"]) * (s["w"] + GAP)
        shelf = next((sh for sh in shelves
                      if sh[2] + sw <= atlas_w and s["h"] <= sh[1]), None)
        if shelf is None:
            shelf = [y_next, s["h"], 0]
            shelves.append(shelf)
            y_next += s["h"] + GAP
        placed.append((s, shelf[2], shelf[0]))
        shelf[2] += sw
    atlas_h = y_next
    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    meta = {"image": "dragon-atlas", "anims": {}}
    for s, x, y in sorted(placed, key=lambda p: list(ANIMS).index(p[0]["name"])):
        for i, (im, ox, oy) in enumerate(s["cells"]):
            atlas.alpha_composite(im, (x + i * (s["w"] + GAP) + ox, y + oy))
        meta["anims"][s["name"]] = {
            "x": x, "y": y, "w": s["w"], "h": s["h"], "frames": len(s["cells"]),
            "stride": s["w"] + GAP, "fps": s["fps"], "loop": s["loop"],
            "ax": s["ax"], "ay": s["ay"],
        }
    meta["width"], meta["height"] = atlas_w, atlas_h

    OUT.mkdir(exist_ok=True)
    atlas.save(OUT / "dragon-atlas.webp", quality=80, alpha_quality=90, method=6)
    atlas.save(OUT / "dragon-atlas.avif", quality=65, speed=2)
    (OUT / "dragon-atlas.json").write_text(json.dumps(meta, indent=1))
    for ext in ("webp", "avif"):
        p = OUT / f"dragon-atlas.{ext}"
        print(f"{p.name}: {p.stat().st_size / 1024:.1f} KB")
    # Inyecta los metadatos en el componente (una petición HTTP menos).
    js = (ROOT / "src" / "dragon-sprite.js").read_text()
    js = js.replace("/*__ATLAS__*/ null", json.dumps(meta, separators=(",", ":")))
    (OUT / "dragon-sprite.js").write_text(js)
    print(f"dragon-sprite.js: {len(js.encode()) / 1024:.1f} KB")

    # Versión minificada (opcional, requiere Node/npx).
    try:
        subprocess.run(
            ["npx", "-y", "esbuild@0.25", str(OUT / "dragon-sprite.js"), "--minify",
             "--format=esm", "--target=es2022", f"--outfile={OUT / 'dragon-sprite.min.js'}"],
            check=True, capture_output=True)
        m = (OUT / "dragon-sprite.min.js").read_bytes()
        print(f"dragon-sprite.min.js: {len(m) / 1024:.1f} KB "
              f"({len(gzip.compress(m, 9)) / 1024:.1f} KB gzip)")
    except (OSError, subprocess.CalledProcessError) as e:
        print("esbuild no disponible, se omite la minificación:", e)


if __name__ == "__main__":
    build()
