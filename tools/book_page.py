#!/usr/bin/env python3
"""Rebuild a colour-by-number page as a real coloring-book page.

  python3 tools/book_page.py <slug> [<slug> ...] [--src DIR] [--colors N] [--speck 40]

Uses the artist's own black-and-white drawing (DIR/<slug>-line.png) and the painting made from it
(public/pages/<slug>/color.jpg, else DIR/<slug>-color.jpg). DIR defaults to pages/src. Every enclosed white area of the drawing becomes one
spot you tap, exactly as in a coloring book; only specks too small to tap (under --speck pixels on a
1254px page) join the neighbouring spot they share the most edge with. Each spot is numbered with the
palette colour closest to the painting inside it, so the finished page looks like the painting.

Writes public/pages/<slug>/: labels.png, regions.json (v 3, no blob outlines), ink.png (the drawing,
2x, solid black lines), line.png (the drawing, page size). Updates public/pages.json (regions, colors).
Rebuilding changes the pieces, so anyone partway through that page starts it fresh. Needs opencv, numpy.
"""
import sys, os, json, argparse
import numpy as np, cv2

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('slugs', nargs='+')
ap.add_argument('--src', default=os.path.join(R, 'pages', 'src'))
ap.add_argument('--colors', type=int, default=None, help='palette size (default: keep the page\'s current size, else 28)')
ap.add_argument('--speck', type=float, default=80, help='areas smaller than this (px on a 1254px page) join a neighbour')
ap.add_argument('--ink', type=int, default=140, help='grey level below which the drawing counts as a line')
ap.add_argument('--shade', type=float, default=0.5)
a = ap.parse_args()


def build(slug):
    L = cv2.imread(os.path.join(a.src, slug + '-line.png'), cv2.IMREAD_GRAYSCALE)
    # the painting: the page's own color.jpg (colour-polished, aligned to the drawing), else the source copy
    C = cv2.imread(os.path.join(R, 'public', 'pages', slug, 'color.jpg'))
    if C is None: C = cv2.imread(os.path.join(a.src, slug + '-color.jpg'))
    if L is None or C is None:
        print('SKIP', slug, '(no drawing/painting in', a.src + ')'); return False
    h, w = L.shape
    if C.shape[:2] != (h, w): C = cv2.resize(C, (w, h), interpolation=cv2.INTER_AREA)
    out = os.path.join(R, 'public', 'pages', slug); os.makedirs(out, exist_ok=True)
    old = {}
    try: old = json.load(open(os.path.join(out, 'regions.json')))
    except Exception: pass
    K = a.colors or (len(old['palette']) if isinstance(old.get('palette'), list) else 28)
    k2 = (w * h) / (1254 * 1254)

    # 1. lines: drop stray ink dots that would make useless pieces
    ink = (L < a.ink).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    dots = np.where(st[:, cv2.CC_STAT_AREA] < 12 * k2)[0]; dots = dots[dots > 0]
    ink[np.isin(lab, dots)] = 0
    Lc = L.copy(); Lc[np.isin(lab, dots)] = 255

    # 2. spots = enclosed white areas
    n, lab = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4)
    lab = lab.astype(np.int32)
    area = np.bincount(lab.ravel(), minlength=n)
    # 3. specks join the neighbour they touch most (repeat until none left)
    speck = a.speck * k2
    for _ in range(6):
        small = [i for i in range(1, n) if 0 < area[i] < speck]
        if not small: break
        # grow every big spot one pixel at a time into lines and specks; specks take the label that reaches them most
        big = lab.copy(); sm = np.zeros(n, bool); sm[small] = True; big[sm[lab]] = 0
        grown = big.copy()
        for _ in range(4):
            m = grown == 0
            if not m.any(): break
            d = cv2.dilate(grown.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32)
            grown[m] = d[m]
        for i in small:
            ys, xs = np.nonzero(lab == i) if area[i] < 400 else (None, None)
            if ys is None: continue
            v = grown[ys, xs]; v = v[v > 0]
            if len(v):
                t = np.bincount(v).argmax(); lab[ys, xs] = t; area[t] += area[i]; area[i] = 0
        if not any(0 < area[i] < speck for i in small): break
    # 4. line pixels belong to the nearest spot, so a fill covers right up under the line
    m = lab == 0
    if m.any():
        dist, near = cv2.distanceTransformWithLabels(m.astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        # map each seed (non-line pixel) index to its label
        seeds = np.zeros(near.max() + 1, np.int32)
        nz = ~m; seeds[near[nz]] = lab[nz]
        lab[m] = seeds[near[m]]
    # renumber 1..R
    ids = np.unique(lab); ids = ids[ids > 0]
    remap = np.zeros(lab.max() + 1, np.int32); remap[ids] = np.arange(1, len(ids) + 1)
    lab = remap[lab]; Rn = len(ids)

    # 5. palette: k-means in Lab over the painting, then each spot takes the colour nearest its median
    lab3 = cv2.cvtColor(C, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(1); samp = lab3[rng.choice(len(lab3), min(200000, len(lab3)), replace=False)]
    _, _, cent = cv2.kmeans(samp, K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    flat = lab.ravel()
    order = np.argsort(flat, kind='stable'); bounds = np.searchsorted(flat[order], np.arange(1, Rn + 2))
    med = np.zeros((Rn, 3), np.float32); spread = np.zeros(Rn, np.float32)
    for r in range(Rn):
        px = lab3[order[bounds[r]:bounds[r + 1]]]
        med[r] = np.median(px, axis=0)
        if len(px) > 1500: spread[r] = np.sqrt(((px - med[r]) ** 2).sum(1)).mean()
    cidx = np.argmin(((med[:, None, :] - cent[None]) ** 2).sum(2), axis=1)
    used = np.unique(cidx); cm = np.full(K, -1); cm[used] = np.arange(len(used)); cidx = cm[cidx]; cent = cent[used]
    # order palette light to dark-ish by hue for a tidy picker
    rgb = cv2.cvtColor(cent.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    hsv = cv2.cvtColor(rgb.reshape(1, -1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    po = np.lexsort((-hsv[:, 2].astype(int), (hsv[:, 1] < 40).astype(int) * 1000 + hsv[:, 0].astype(int)))
    rank = np.empty(len(po), int); rank[po] = np.arange(len(po)); cidx = rank[cidx]; rgb = rgb[po]

    # 6. number spot: the point deepest inside each spot
    regions = []
    for r in range(Rn):
        sel = order[bounds[r]:bounds[r + 1]]; ys, xs = np.divmod(sel, w)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        msk = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8); msk[ys - y0 + 1, xs - x0 + 1] = 1
        msk[1:-1, 1:-1] &= 1 - ink[y0:y1, x0:x1]   # numbers sit in the white, not on a line
        dt = cv2.distanceTransform(msk, cv2.DIST_L2, 5)
        yy, xx = np.unravel_index(np.argmax(dt), dt.shape)
        regions.append({'id': r + 1, 'c': int(cidx[r]), 'a': int(len(sel)), 'x': int(xx + x0 - 1), 'y': int(yy + y0 - 1), 'r': round(float(dt[yy, xx]), 1)})

    # 7. write
    lb = np.zeros((h, w, 3), np.uint8); lb[:, :, 2] = lab & 255; lb[:, :, 1] = lab >> 8   # BGR: R = low byte, G = high byte
    cv2.imwrite(os.path.join(out, 'labels.png'), lb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    cv2.imwrite(os.path.join(out, 'line.png'), Lc, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    S = 2
    up = cv2.resize(Lc, (w * S, h * S), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    up = cv2.GaussianBlur(up, (0, 0), 0.5 * S)
    t = 1 / (1 + np.exp((up - 150) / 16))
    cv2.imwrite(os.path.join(out, 'ink.png'), (255 - 255 * t).clip(0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    meta = {'w': w, 'h': h, 'mode': 'pair', 'palette': rgb.tolist(), 'regions': regions, 'shade': a.shade, 'v': 3, 'ink': S}
    json.dump(meta, open(os.path.join(out, 'regions.json'), 'w'), separators=(',', ':'))
    pj = os.path.join(R, 'public', 'pages.json'); P = json.load(open(pj, encoding='utf-8'))
    for p in P:
        if p['slug'] == slug: p['regions'] = Rn; p['colors'] = len(rgb)
    for tries in range(20):   # Windows: a running preview server can briefly hold the file
        try:
            with open(pj + '.tmp', 'w', encoding='utf-8') as f: json.dump(P, f, ensure_ascii=False, indent=1)
            os.replace(pj + '.tmp', pj); break
        except PermissionError:
            import time; time.sleep(0.5)
    big = max(r['a'] for r in regions) / (w * h)
    print(f"{slug}: {Rn} spots, {len(rgb)} colors, biggest {big:.1%}, mixed-colour {int((spread > 25).sum())}, tiny {sum(r['r'] < 3 for r in regions)}")
    return True


skipped = [s for s in a.slugs if not build(s)]
if skipped: print('SKIPPED (still old pages):', ' '.join(skipped))
