#!/usr/bin/env python3
"""Build the Brink icon: a brass balance scale standing on top of the world.

Dev tool - needs Pillow.  Run, then ./install-desktop.sh to refresh the dash.
"""
import math
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons")
SS = 4
N = 512 * SS

OCEAN = (52, 112, 184)
OCEAN_HI = (98, 156, 220)
LAND = (72, 160, 92)
LAND_DARK = (50, 124, 70)
GRID = (210, 230, 250)
EDGE = (32, 44, 66)
BRASS = (214, 164, 58)
BRASS_HI = (246, 210, 120)
BRASS_DK = (150, 104, 30)


def s(v):
    return int(round(v * SS))


def main():
    os.makedirs(OUT, exist_ok=True)
    img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ---- the world: lower part of the icon --------------------------------
    cx, cy, R = 256, 330, 160
    globe = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    g = ImageDraw.Draw(globe)
    g.ellipse([s(cx - R), s(cy - R), s(cx + R), s(cy + R)], fill=OCEAN)
    g.ellipse([s(cx - R + 22), s(cy - R + 14), s(cx + R - 70), s(cy + R - 120)], fill=OCEAN_HI)
    # continents as soft blobs
    blobs = [(-70, -60, 55, 40), (-95, -10, 40, 55), (-55, 60, 35, 50), (40, -80, 70, 35), (70, -30, 55, 45),
             (30, 30, 40, 50), (110, 50, 30, 35), (-10, -105, 40, 18)]
    for dx, dy, rx, ry in blobs:
        g.ellipse([s(cx + dx - rx), s(cy + dy - ry), s(cx + dx + rx), s(cy + dy + ry)], fill=LAND)
    for dx, dy, rx, ry in blobs[1::3]:
        g.ellipse([s(cx + dx - rx * 0.5), s(cy + dy - ry * 0.4), s(cx + dx + rx * 0.4), s(cy + dy + ry * 0.5)],
                  fill=LAND_DARK)
    # graticule
    for lat in (-0.6, -0.3, 0.0, 0.3, 0.6):
        y = cy + lat * R
        half = R * math.sqrt(1 - lat * lat)
        g.ellipse([s(cx - half), s(y - half * 0.16), s(cx + half), s(y + half * 0.16)], outline=GRID + (120,), width=s(3))
    for k in (0.35, 0.7):
        g.ellipse([s(cx - R * k), s(cy - R), s(cx + R * k), s(cy + R)], outline=GRID + (120,), width=s(3))
    g.line([s(cx), s(cy - R), s(cx), s(cy + R)], fill=GRID + (120,), width=s(3))
    mask = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mask).ellipse([s(cx - R), s(cy - R), s(cx + R), s(cy + R)], fill=255)
    img.paste(globe, (0, 0), mask)
    d.ellipse([s(cx - R), s(cy - R), s(cx + R), s(cy + R)], outline=EDGE, width=s(9))

    # ---- the balance, standing on the top of the globe ---------------------
    top = cy - R                      # 170
    # base plate resting on the globe
    d.rounded_rectangle([s(206), s(top - 22), s(306), s(top + 8)], radius=s(12), fill=BRASS, outline=EDGE, width=s(6))
    d.line([s(216), s(top - 14), s(296), s(top - 14)], fill=BRASS_HI, width=s(5))
    # post
    d.rectangle([s(246), s(56), s(266), s(top - 20)], fill=BRASS, outline=EDGE, width=s(6))
    d.line([s(252), s(64), s(252), s(top - 26)], fill=BRASS_HI, width=s(4))
    # beam
    by = 70
    d.rounded_rectangle([s(70), s(by - 10), s(442), s(by + 10)], radius=s(10), fill=BRASS, outline=EDGE, width=s(6))
    d.line([s(82), s(by - 3), s(430), s(by - 3)], fill=BRASS_HI, width=s(4))
    # pivot finial
    d.ellipse([s(240), s(by - 30), s(272), s(by + 2)], fill=BRASS_HI, outline=EDGE, width=s(6))
    # pans hanging by chains
    for px in (98, 414):
        d.ellipse([s(px - 9), s(by - 9), s(px + 9), s(by + 9)], fill=BRASS_DK, outline=EDGE, width=s(4))
        pan_y = 176
        for off in (-44, 44):
            d.line([s(px), s(by + 6), s(px + off), s(pan_y)], fill=EDGE, width=s(5))
        # the pan: a shallow bowl
        d.chord([s(px - 58), s(pan_y - 34), s(px + 58), s(pan_y + 34)], 0, 180, fill=BRASS, outline=EDGE, width=s(6))
        d.line([s(px - 58), s(pan_y), s(px + 58), s(pan_y)], fill=EDGE, width=s(6))
        d.arc([s(px - 44), s(pan_y - 20), s(px + 44), s(pan_y + 22)], 20, 160, fill=BRASS_HI, width=s(4))

    big = img.resize((512, 512), Image.LANCZOS)
    big.save(os.path.join(OUT, "brink.png"))
    for size in (256, 128, 64, 48):
        big.resize((size, size), Image.LANCZOS).save(os.path.join(OUT, f"brink-{size}.png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
