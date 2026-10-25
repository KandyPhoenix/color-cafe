#!/usr/bin/env python3
"""Build Color Cafe page assets.

  python3 tools/make_page.py pair <slug> <line.png> <color.jpg> --title "..." --theme <id> [--colors 36] [--min 250]
  python3 tools/make_page.py line <slug> <line.png>             --title "..." --theme mandalas [--min 150]

Writes public/pages/<slug>/{line.png,color.jpg,labels.png,regions.json,thumb.jpg} and updates public/pages.json.
Regions = areas enclosed by the ink lines of the line art. For 'pair' pages the colour comes from the painted
version (aligned to the line art) and each region gets a palette number. 'line' pages have no palette (free colour).
Needs opencv-python, numpy, Pillow.
"""
import sys, os, json, argparse, time
import numpy as np, cv2

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('mode', choices=['pair', 'line']); ap.add_argument('slug'); ap.add_argument('line'); ap.add_argument('color', nargs='?')
ap.add_argument('--title', required=True); ap.add_argument('--theme', required=True)
ap.add_argument('--colors', type=int, default=36); ap.add_argument('--min', type=int, default=250)
ap.add_argument('--ink', type=int, default=110); ap.add_argument('--size', type=int, default=1400)
ap.add_argument('--merge', type=float, default=18.0, help='pair mode: merge touching areas whose colours differ by less than this (Lab distance, lightness half-weighted) so one tap fills a whole item')
ap.add_argument('--maxitem', type=float, default=0.12, help='pair mode: never merge into an item bigger than this fraction of the page')
ap.add_argument('--style', default=''); ap.add_argument('--artist', default='Original art')
a = ap.parse_args(); t0 = time.time()

line = cv2.imread(a.line)
if line is None: sys.exit('cannot read ' + a.line)
# normalise size: longest side = --size (keeps phones fast, 1400 is plenty for a square page)
h0, w0 = line.shape[:2]; sc = a.size / max(h0, w0)
if sc < 1: line = cv2.resize(line, (round(w0 * sc), round(h0 * sc)), interpolation=cv2.INTER_AREA)
h, w = line.shape[:2]
L = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)
ink = (L < a.ink).astype(np.uint8)
ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

n, labels = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4); labels = labels.astype(np.int32)
areas = np.bincount(labels.ravel(), minlength=n)
for r in [r for r in range(1, n) if 0 < areas[r] < a.min]:
    m = (labels == r).astype(np.uint8); ring = cv2.dilate(m, np.ones((7, 7), np.uint8)) - m
    nb = labels[ring > 0]; nb = nb[(nb != r) & (nb > 0)]
    if nb.size: labels[m > 0] = np.bincount(nb).argmax()
# anything still smaller than --min has no neighbour (a speck sealed inside ink): treat it as ink
areas = np.bincount(labels.ravel(), minlength=labels.max() + 1)
labels[np.isin(labels, np.where(areas < a.min)[0]) & (labels > 0)] = 0
ink = (labels == 0).astype(np.uint8)
_, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
# the outer border region (touches all four edges and is big) is background; keep it, it is colourable too
Rn = labels.max()
if Rn > 65000: sys.exit(f'too many regions ({Rn}); raise --min')

col = None; rc = np.zeros(Rn + 1, np.int32); palette = []
if a.mode == 'pair':
    col = cv2.imread(a.color)
    if col is None: sys.exit('cannot read ' + a.color)
    col = cv2.resize(col, (w, h), interpolation=cv2.INTER_LANCZOS4)
    g1 = cv2.GaussianBlur(cv2.Canny(cv2.GaussianBlur(L, (0, 0), 2), 50, 150).astype(np.float32), (0, 0), 4)
    g2 = cv2.GaussianBlur(cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(col, cv2.COLOR_BGR2GRAY), (0, 0), 2), 50, 150).astype(np.float32), (0, 0), 4)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(g1, g2, warp, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5), None, 5)
        col = cv2.warpAffine(col, warp, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        print(f'aligned painting to line art (ecc {cc:.2f})')
    except cv2.error:
        print('WARNING: could not align painting; using as-is')
    lab = cv2.cvtColor(col, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32); flat = labels.ravel()
    cnt = np.bincount(flat, minlength=Rn + 1).astype(np.float64)
    means = np.stack([np.bincount(flat, weights=lab[:, c], minlength=Rn + 1) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
    if a.merge > 0:
        # neighbours across the ink: grow labels into the ink lines, then read 4-neighbour pairs
        grown = labels.astype(np.uint16)
        for _ in range(6):
            dil = cv2.dilate(grown, np.ones((3, 3), np.uint8))
            grown = np.where(grown == 0, dil, grown)
        pr = np.stack([grown[:, :-1].ravel(), grown[:, 1:].ravel()], 1); pd = np.stack([grown[:-1, :].ravel(), grown[1:, :].ravel()], 1)
        pairs = np.concatenate([pr, pd]).astype(np.int64); pairs = pairs[(pairs[:, 0] != pairs[:, 1]) & (pairs[:, 0] > 0) & (pairs[:, 1] > 0)]
        pairs = np.unique(np.sort(pairs, 1), axis=0)
        wgt = np.array([0.5, 1.0, 1.0]); dE = np.sqrt((((means[pairs[:, 0]] - means[pairs[:, 1]]) * wgt) ** 2).sum(1))
        order = np.argsort(dE); parent = np.arange(Rn + 1); size = cnt.copy(); limit = a.maxitem * h * w
        def find(x):
            while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
            return x
        merged = 0
        for k in order:
            if dE[k] > a.merge: break
            ra, rb = find(pairs[k, 0]), find(pairs[k, 1])
            if ra == rb or size[ra] + size[rb] > limit: continue
            parent[rb] = ra; size[ra] += size[rb]; merged += 1
        root = np.array([find(i) for i in range(Rn + 1)]); root[0] = 0
        _, labels = np.unique(root[labels], return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
        Rn = labels.max(); flat = labels.ravel()
        cnt = np.bincount(flat, minlength=Rn + 1).astype(np.float64)
        means = np.stack([np.bincount(flat, weights=lab[:, c], minlength=Rn + 1) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
        rc = np.zeros(Rn + 1, np.int32)
        print(f'merged {merged} touching areas into whole items -> {Rn} items')
    N = min(a.colors, Rn)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, 0.5)
    _, assign, centers = cv2.kmeans(means[1:].astype(np.float32), N, None, crit, 6, cv2.KMEANS_PP_CENTERS)
    # order palette light->dark so numbers feel natural
    order = np.argsort(-centers[:, 0]); rank = np.empty(N, int); rank[order] = np.arange(N)
    rc[1:] = rank[assign.ravel()]
    pal = cv2.cvtColor(centers[order].reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
    palette = [[int(c[2]), int(c[1]), int(c[0])] for c in pal]

regions = []
for r in range(1, Rn + 1):
    m = (labels == r).astype(np.uint8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
    regions.append({'id': r, 'c': int(rc[r]) if a.mode == 'pair' else -1, 'a': int(m.sum()), 'x': int(x), 'y': int(y), 'r': round(float(dt.max()), 1)})

out = os.path.join(R, 'public', 'pages', a.slug); os.makedirs(out, exist_ok=True)
cv2.imwrite(os.path.join(out, 'line.png'), cv2.cvtColor(line, cv2.COLOR_BGR2GRAY), [cv2.IMWRITE_PNG_COMPRESSION, 9])
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = labels % 256; rgb[:, :, 1] = labels // 256
cv2.imwrite(os.path.join(out, 'labels.png'), rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
if col is not None:
    cv2.imwrite(os.path.join(out, 'color.jpg'), col, [cv2.IMWRITE_JPEG_QUALITY, 88])
    thumb = col.copy(); thumb[ink > 0] = np.minimum(thumb[ink > 0], line[ink > 0])
else:
    thumb = line.copy()
ts = 420 / max(h, w); thumb = cv2.resize(thumb, (round(w * ts), round(h * ts)), interpolation=cv2.INTER_AREA)
cv2.imwrite(os.path.join(out, 'thumb.jpg'), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
json.dump({'w': w, 'h': h, 'mode': a.mode, 'palette': palette, 'regions': regions}, open(os.path.join(out, 'regions.json'), 'w'), separators=(',', ':'))

mf = os.path.join(R, 'public', 'pages.json')
pages = json.load(open(mf)) if os.path.exists(mf) else []
pages = [p for p in pages if p['slug'] != a.slug]
pages.append({'slug': a.slug, 'title': a.title, 'theme': a.theme, 'mode': a.mode, 'artist': a.artist, 'style': a.style,
              'w': w, 'h': h, 'regions': int(Rn), 'colors': len(palette), 'added': time.strftime('%Y-%m-%d')})
json.dump(pages, open(mf, 'w'), indent=1)
ar = [r['a'] for r in regions]
print(f"{a.slug}: {Rn} regions, {len(palette)} colours, min {min(ar)} px, median {int(np.median(ar))}, {w}x{h}, {time.time()-t0:.0f}s")
