"""Generate a clean Quant OS app icon (1024x1024 PNG source for `tauri icon`).

Design: near-black canvas, a rounded dark tile with a thin emerald edge, and a bold
emerald upward "growth line" with an end node — a finance-grade mark that stays legible
down to 16px. Rendered at 4x and downsampled for smooth (anti-aliased) edges.
"""

from PIL import Image, ImageDraw

S = 1024
SS = 4               # supersample factor
W = S * SS
img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

BG = (10, 10, 11, 255)        # #0a0a0b
TILE = (17, 17, 21, 255)      # #111115
EDGE = (16, 185, 129, 110)    # emerald, translucent edge
LINE = (52, 211, 153, 255)    # #34d399
NODE = (16, 185, 129, 255)    # #10b981
NODE_CORE = (209, 250, 229, 255)

# full-bleed dark background, slightly rounded so it also looks right un-masked
d.rounded_rectangle([0, 0, W, W], radius=180 * SS, fill=BG)

# centered tile
m = 96 * SS
d.rounded_rectangle([m, m, W - m, W - m], radius=200 * SS, fill=TILE,
                    outline=EDGE, width=4 * SS)

# growth line (upward zig-zag), normalized to the tile's inner box
pts_norm = [(0.22, 0.70), (0.40, 0.56), (0.55, 0.64), (0.78, 0.30)]
pts = [(x * W, y * W) for (x, y) in pts_norm]
d.line(pts, fill=LINE, width=11 * SS, joint="curve")

# round caps at each vertex so the polyline reads as a smooth stroke
r_cap = 5 * SS
for (x, y) in pts:
    d.ellipse([x - r_cap, y - r_cap, x + r_cap, y + r_cap], fill=LINE)

# end node (emphasis dot at the top-right of the line)
ex, ey = pts[-1]
r = 30 * SS
d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=NODE)
rc = 12 * SS
d.ellipse([ex - rc, ey - rc, ex + rc, ey + rc], fill=NODE_CORE)

out = img.resize((S, S), Image.LANCZOS)
dest = "apps/web/src-tauri/icons/source.png"
out.save(dest)
print("wrote", dest)
