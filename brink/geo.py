"""Map geometry: each Region is a site; land is the set of pixels within a
(wobbly) radius of their nearest site, so Regions become Voronoi cells
clipped into coastlines.  Pure Python - shared by the map view and by the
random-world generator (which reads land borders off the raster)."""
from __future__ import annotations

import math
import random


def _noise_fn(seed):
    rnd = random.Random(seed)
    waves = [(rnd.uniform(9, 16), rnd.uniform(9, 16), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)) for _ in range(3)]
    waves += [(rnd.uniform(24, 40), rnd.uniform(24, 40), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3)) for _ in range(2)]

    def n(x, y):
        v = 0.0
        for i, (fx, fy, px, py) in enumerate(waves):
            amp = 1.0 if i < 3 else 0.45
            v += amp * math.sin(fx * x + px) * math.sin(fy * y + py)
        return v / 2.2
    return n


def raster(sites, aspect, radius, width, seed=7, wobble=0.28):
    """sites: [(x, y)] with x, y in 0..1.  Returns (W, H, idx) where idx[py*W+px]
    is the index of the nearest site, or -1 for sea."""
    W = int(width)
    H = max(1, int(round(width / aspect)))
    n = len(sites)
    search = radius * (1 + wobble) * 1.05
    s2 = search * search
    best = [s2] * (W * H)
    idx = [-1] * (W * H)
    for i, (x, y) in enumerate(sites):
        cx, cy = x * aspect, y
        x0 = max(0, int((cx - search) / aspect * W))
        x1 = min(W, int((cx + search) / aspect * W) + 2)
        y0 = max(0, int((cy - search) * H))
        y1 = min(H, int((cy + search) * H) + 2)
        for py in range(y0, y1):
            dy = (py + 0.5) / H - cy
            dy2 = dy * dy
            if dy2 >= s2:
                continue
            row = py * W
            for px in range(x0, x1):
                dx = (px + 0.5) / W * aspect - cx
                d = dx * dx + dy2
                k = row + px
                if d < best[k]:
                    best[k] = d
                    idx[k] = i
    noise = _noise_fn(seed)
    for py in range(H):
        row = py * W
        yy = (py + 0.5) / H
        for px in range(W):
            k = row + px
            i = idx[k]
            if i < 0:
                continue
            rr = radius * (1 + wobble * noise((px + 0.5) / W * aspect, yy))
            if best[k] > rr * rr:
                idx[k] = -1
    return W, H, idx


def touching(W, H, idx):
    """Pairs of site indices whose cells share an edge on the raster."""
    pairs = set()
    for py in range(H):
        row = py * W
        for px in range(W):
            a = idx[row + px]
            if a < 0:
                continue
            if px + 1 < W:
                b = idx[row + px + 1]
                if b >= 0 and b != a:
                    pairs.add((min(a, b), max(a, b)))
            if py + 1 < H:
                b = idx[row + W + px]
                if b >= 0 and b != a:
                    pairs.add((min(a, b), max(a, b)))
    return pairs


def borders(W, H, idx):
    """[(pixel, a, b)] for land pixels next to a different cell or sea (b = -1)."""
    out = []
    for py in range(H):
        row = py * W
        for px in range(W):
            k = row + px
            a = idx[k]
            if a < 0:
                continue
            for nx, ny in ((px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)):
                if 0 <= nx < W and 0 <= ny < H:
                    b = idx[ny * W + nx]
                else:
                    b = -1
                if b != a:
                    out.append((k, a, b))
                    break
    return out
