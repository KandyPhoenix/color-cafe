#!/usr/bin/env python3
"""Make the line art a colour-by-number page shows: the original drawing, cleaned up.

  python3 tools/make_ink.py <slug> [<slug> ...]      # or --all

Reads the original ink drawing pages/ink/<slug>.png (saved by simplify_page.py) and writes
public/pages/<slug>/ink.png:
  * specks and stray dots are removed (ink blobs smaller than --speck pixels)
  * every stroke is thinned by about one pixel, so lines read as fine pen, not heavy marker
  * drawn at --scale times the page size with smooth edges, so it stays crisp when zoomed in
The app draws it over the colours (multiply) in grey, so it always looks like a coloring page,
and the pieces you tap (labels.png, from simplify_page.py) are unions of the drawing's own areas,
so their edges sit on the drawn lines.
Sets "ink": <scale> in regions.json so the app knows to use it. Needs opencv-python, numpy.
"""
import sys, os, json, argparse, glob
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='*'); ap.add_argument('--all', action='store_true')
ap.add_argument('--scale', type=int, default=2); ap.add_argument('--speck', type=int, default=60)
ap.add_argument('--thin', type=int, default=2, help='pixels to thin each stroke by (0 = keep)')
ap.add_argument('--detail', type=float, default=0.3, help='strength of lines inside a piece (0-1); piece edges are full strength')
a = ap.parse_args()
slugs = a.slugs or ([os.path.basename(p)[:-4] for p in sorted(glob.glob(os.path.join(R, 'pages', 'ink', '*.png')))] if a.all else [])
for slug in slugs:
    g = cv2.imread(os.path.join(R, 'pages', 'ink', slug + '.png'), cv2.IMREAD_GRAYSCALE)
    if g is None: print('skip', slug, '(no ink drawing)'); continue
    ink = (g < 140).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    small = np.where(st[:, cv2.CC_STAT_AREA] < a.speck)[0]; small = small[small > 0]
    g = g.copy(); g[np.isin(lab, small)] = 255
    if a.thin: g = cv2.dilate(g, np.ones((a.thin + 1, a.thin + 1), np.uint8))   # paper grows into the ink
    # lines on the edge of a piece you tap stay clear; lines inside a piece are faint detail
    d = os.path.join(R, 'public', 'pages', slug); L = cv2.imread(os.path.join(d, 'labels.png'))
    if L is not None and L.shape[:2] == g.shape:
        L = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32)
        e = np.zeros(g.shape, np.uint8); e[:, 1:] |= L[:, 1:] != L[:, :-1]; e[1:, :] |= L[1:, :] != L[:-1, :]
        e = cv2.dilate(e, np.ones((5, 5), np.uint8)).astype(bool)
        gf = g.astype(np.float32); g = np.where(e, gf, 255 - (255 - gf) * a.detail).astype(np.uint8)
    h, w = g.shape; S = a.scale
    up = cv2.resize(g, (w * S, h * S), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    up = cv2.GaussianBlur(up, (0, 0), 0.6 * S)
    t = 1 / (1 + np.exp((up - 150) / 14))            # 1 = ink, 0 = paper, smooth anti-aliased edge
    t = np.maximum(t, (255 - up) / 255 * (up >= 150))  # keep faint detail lines as light grey
    out = (255 - 255 * t).clip(0, 255).astype(np.uint8)
    cv2.imwrite(os.path.join(d, 'ink.png'), out, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    rp = os.path.join(d, 'regions.json'); m = json.load(open(rp)); m['ink'] = S
    json.dump(m, open(rp, 'w'), separators=(',', ':'))
    print(slug, 'ink.png', os.path.getsize(os.path.join(d, 'ink.png')) // 1024, 'KB')
