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
ap.add_argument('--min', type=float, default=700, help='pieces smaller than this (px on a 1254px page) join the touching piece of the closest colour')
ap.add_argument('--split', type=float, default=1.2, help='open areas bigger than this %% of the page whose painting has clearly different colours are split into a few sections')
ap.add_argument('--shade', type=float, default=1.0)
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

    # 0. remove the colour-band cuts an older tool (carve.py) drew into some drawings: solid 3px strokes of
    #    pure black with hard edges, unlike the artist's soft-edged lines. Real lines they crossed are rejoined.
    def strokes(L, zone=None, minlen=150, edge=False):
        # solid 3px pure-black strokes whose edges go straight to white (the artist's lines fade through grey)
        z = (L == 0).astype(np.uint8)
        dtz = cv2.distanceTransform(z, cv2.DIST_L2, 3)
        solid = cv2.dilate((dtz > 2.6).astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        c = ((z > 0) & ~solid) if zone is None else ((z > 0) & zone)
        c = cv2.morphologyEx(c.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, zl, st, _ = cv2.connectedComponentsWithStats(c, connectivity=8)
        ring = (cv2.dilate(c, np.ones((3, 3), np.uint8)) > 0) & (c == 0)
        zr = cv2.dilate(zl.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32)
        frac = np.bincount(zr[ring & (L > 25) & (L < 215)], minlength=n) / np.maximum(np.bincount(zr[ring], minlength=n), 1)
        keep = np.where((st[:, cv2.CC_STAT_AREA] >= minlen * k2) & ((frac < 0.3) | (not edge)))[0]; keep = keep[keep > 0]
        return (cv2.dilate(np.isin(zl, keep).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0) & (L < 90)
    cut = strokes(L)
    if cut.sum() > 2000 * k2:      # this drawing was cut up: also take the cut pieces that run into solid black
        L = L.copy(); L[cut] = 255
        zone = cv2.dilate(cut.astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
        more = strokes(L, zone, minlen=15, edge=True); L[more] = 255
        print(f'  removed {int(cut.sum() + more.sum())} px of old cut lines')
    else: cut[:] = False

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

    # 4b. a big open area of the drawing (a lake, a sky) whose painting has clearly different colours is split into
    #     a few large, smooth sections, divided by light grey lines (not black ink): e.g. blue / sun-yellow / blue water
    blur = cv2.cvtColor(cv2.GaussianBlur(C, (0, 0), 6 * k2 ** 0.5), cv2.COLOR_BGR2LAB).astype(np.float32)
    soft = np.zeros((h, w), bool); sig = 14 * k2 ** 0.5
    areas = np.bincount(lab.ravel(), minlength=Rn + 1)
    for r in (np.nonzero(areas >= a.split / 100 * w * h)[0] if a.split > 0 else []):
        if r == 0: continue
        ys, xs = np.nonzero(lab == r); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        M = lab[y0:y1, x0:x1] == r; px = blur[y0:y1, x0:x1][M]
        sub = px[np.random.default_rng(2).choice(len(px), min(40000, len(px)), replace=False)]
        _, _, cen = cv2.kmeans(sub, 6, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5), 2, cv2.KMEANS_PP_CENTERS)
        wts = [float((np.argmin(((sub[:, None] - cen[None]) ** 2).sum(2), 1) == k).sum()) for k in range(len(cen))]
        cen = list(cen); wts = list(wts)
        while len(cen) > 1:   # colours closer than this are one section
            dd = [(((cen[i] - cen[j]) ** 2).sum() ** .5, i, j) for i in range(len(cen)) for j in range(i + 1, len(cen))]
            dm, i, j = min(dd)
            if dm > 22: break
            cen[i] = (cen[i] * wts[i] + cen[j] * wts[j]) / (wts[i] + wts[j]); wts[i] += wts[j]; del cen[j]; del wts[j]
        if len(cen) < 2: continue
        cen = np.array(cen, np.float32)
        hard = np.argmin(((blur[y0:y1, x0:x1][:, :, None, :] - cen[None, None]) ** 2).sum(3), 2)
        Mf = cv2.GaussianBlur(M.astype(np.float32), (0, 0), sig) + 1e-6
        prob = np.stack([cv2.GaussianBlur(((hard == k) & M).astype(np.float32), (0, 0), sig) / Mf for k in range(len(cen))], 2)
        sec = np.argmax(prob, 2); sec[~M] = -1
        # sections smaller than a piece worth colouring go to the section around them
        minsec = max(0.004 * w * h, 0.03 * M.sum())
        secl = np.full(M.shape, -1, np.int32); nid = 0
        for k in range(len(cen)):
            nk, cl, cs, _ = cv2.connectedComponentsWithStats((sec == k).astype(np.uint8), connectivity=4)
            for q in range(1, nk):
                if cs[q, cv2.CC_STAT_AREA] >= minsec: secl[cl == q] = nid; nid += 1
        if nid < 2: continue
        un = (secl < 0) & M
        for _ in range(400):
            if not un.any(): break
            g2 = cv2.dilate((secl + 1).astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32) - 1
            fill = un & (g2 >= 0); secl[fill] = g2[fill]; un = (secl < 0) & M
        secl[un] = 0
        blk = lab[y0:y1, x0:x1]
        for q in range(1, nid):
            Rn += 1; blk[M & (secl == q)] = Rn
        e = np.zeros(M.shape, bool)
        e[:, 1:] |= (secl[:, 1:] != secl[:, :-1]) & M[:, 1:] & M[:, :-1]; e[1:, :] |= (secl[1:, :] != secl[:-1, :]) & M[1:, :] & M[:-1, :]
        soft[y0:y1, x0:x1] |= e
        print(f'  split an open area ({100 * M.sum() / (w * h):.1f}% of the page) into {nid} colour sections')

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
    # each spot's number is the palette colour covering most of it (a blue lake with a gold sun path is "blue");
    # filling it shows the painting's own colours there (regions.json "reveal"), so one tap brings back every shade
    near = np.empty(len(lab3), np.int32); bl = blur.reshape(-1, 3)
    for i0 in range(0, len(bl), 250000):
        near[i0:i0 + 250000] = np.argmin(((bl[i0:i0 + 250000, None, :] - cent[None]) ** 2).sum(2), 1)
    cidx = np.zeros(Rn, np.int64)
    simk = np.exp(-((cent[:, None] - cent[None]) ** 2).sum(2) / (2 * 18.0 ** 2))
    for r in range(Rn):
        cnt = np.bincount(near[order[bounds[r]:bounds[r + 1]]], minlength=K).astype(np.float64)
        cidx[r] = (simk @ cnt).argmax()        # similar shades count together: many blues outvote one gold
    used = np.unique(cidx); cm = np.full(K, -1); cm[used] = np.arange(len(used)); cidx = cm[cidx]; cent = cent[used]
    # order palette light to dark-ish by hue for a tidy picker
    rgb = cv2.cvtColor(cent.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    hsv = cv2.cvtColor(rgb.reshape(1, -1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    po = np.lexsort((-hsv[:, 2].astype(int), (hsv[:, 1] < 40).astype(int) * 1000 + hsv[:, 0].astype(int)))
    rank = np.empty(len(po), int); rank[po] = np.arange(len(po)); cidx = rank[cidx]; rgb = rgb[po]

    # 5b. fewer, bigger pieces: touching spots with the same number become one piece, and pieces too small to
    #     see a number in join the touching piece whose painted colour is closest. The drawing still shows every
    #     line, and the painting's light and dark shades each piece, so detail is kept without extra taps.
    par = np.arange(Rn)
    def root(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    A = lab[:, 1:].ravel(), lab[:, :-1].ravel(); B = lab[1:, :].ravel(), lab[:-1, :].ravel()
    p1 = np.concatenate([A[0], B[0]]) - 1; p2 = np.concatenate([A[1], B[1]]) - 1; d = p1 != p2
    pairs, cnt = np.unique(np.minimum(p1[d], p2[d]).astype(np.int64) * Rn + np.maximum(p1[d], p2[d]), return_counts=True)
    pa, pb = pairs // Rn, pairs % Rn
    for i, j in zip(pa, pb):
        if cidx[i] == cidx[j]: ri, rj = root(i), root(j); par[ri] = rj
    sz = np.bincount(flat - 1, minlength=Rn).astype(np.float64)
    nb = {}
    for i, j, c in zip(pa, pb, cnt): nb.setdefault(i, []).append(j); nb.setdefault(j, []).append(i)
    minp = a.min * k2
    for _ in range(8):
        g = np.array([root(i) for i in range(Rn)])
        gs = np.bincount(g, weights=sz, minlength=Rn); gm = np.zeros((Rn, 3)); np.add.at(gm, g, med * sz[:, None]); gm /= np.maximum(gs, 1)[:, None]
        changed = False
        for r in np.argsort(gs):
            if gs[r] == 0 or gs[r] >= minp or root(r) != r: continue
            cand = {root(j) for i in np.nonzero(g == r)[0] for j in nb.get(i, [])} - {r}
            if not cand: continue
            t = min(cand, key=lambda q: ((gm[q] - gm[r]) ** 2).sum())
            par[r] = t; gs[t] += gs[r]; gs[r] = 0; changed = True
        if not changed: break
    g = np.array([root(i) for i in range(Rn)])
    big = np.zeros(Rn, np.float64); best = np.zeros(Rn, int)        # a piece keeps the number of its biggest part
    for i in np.argsort(sz):
        best[g[i]] = cidx[i] if sz[i] >= big[g[i]] else best[g[i]]; big[g[i]] = max(big[g[i]], sz[i])
    roots = np.unique(g); newid = np.zeros(Rn, np.int32); newid[roots] = np.arange(1, len(roots) + 1)
    lab = np.concatenate([[0], newid[g]])[lab]; cidx = best[roots]; Rn = len(roots)
    used = np.unique(cidx); cm = np.full(len(rgb), -1); cm[used] = np.arange(len(used)); cidx = cm[cidx]; rgb = rgb[used]
    flat = lab.ravel(); order = np.argsort(flat, kind='stable'); bounds = np.searchsorted(flat[order], np.arange(1, Rn + 2))
    spread = np.zeros(Rn)

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
    if soft.any():
        sl = cv2.dilate(soft.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
        Lc = Lc.copy(); Lc[sl & (Lc > 170)] = 170          # light grey: a gentle guide, not a black line
    cv2.imwrite(os.path.join(out, 'line.png'), Lc, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    S = 2
    up = cv2.resize(Lc, (w * S, h * S), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    up = cv2.GaussianBlur(up, (0, 0), 0.5 * S)
    t = 1 / (1 + np.exp((up - 150) / 16))
    cv2.imwrite(os.path.join(out, 'ink.png'), (255 - 255 * t).clip(0, 255).astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    meta = {'w': w, 'h': h, 'mode': 'pair', 'palette': rgb.tolist(), 'regions': regions, 'shade': a.shade, 'reveal': 1, 'v': 3, 'ink': S}
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
