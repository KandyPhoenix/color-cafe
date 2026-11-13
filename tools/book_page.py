#!/usr/bin/env python3
"""Rebuild a colour-by-number page as a real coloring-book page.

  python3 tools/book_page.py <slug> [<slug> ...] [--src DIR] [--colors N] [--speck 40]

Uses the artist's own black-and-white drawing (DIR/<slug>-line.png) and the painting made from it
(public/pages/<slug>/color.jpg, else DIR/<slug>-color.jpg). DIR defaults to pages/src. Every drawn shape
becomes one piece you tap, as in a coloring book: small gaps in the long outlines are closed first (light
grey ticks show where), so the water does not run into the mist or a hill. Specks and pieces too small to
colour join a small neighbour. Each piece is numbered with its main painted colour (sunlight and glow count
as light on it: water with a sun path is blue), and filling it brings back every colour the painting has there.

Writes public/pages/<slug>/: labels.png, regions.json (v 3, no blob outlines), ink.png (the drawing,
2x, solid black lines), line.png (the drawing, page size). Updates public/pages.json (regions, colors).
Rebuilding changes the pieces, so anyone partway through that page starts it fresh. Needs opencv, numpy.
"""
import sys, os, json, argparse, time
import numpy as np, cv2

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('slugs', nargs='+')
ap.add_argument('--src', default=os.path.join(R, 'pages', 'src'))
ap.add_argument('--colors', type=int, default=None, help='palette size (default: keep the page\'s current size, else 28)')
ap.add_argument('--speck', type=float, default=80, help='areas smaller than this (px on a 1254px page) join a neighbour')
ap.add_argument('--ink', type=int, default=140, help='grey level below which the drawing counts as a line')
ap.add_argument('--min', type=float, default=700, help='pieces smaller than this (px on a 1254px page) join the touching piece of the closest colour')
ap.add_argument('--gap', type=float, default=4, help='outline gaps up to about twice this (px on a 1254px page) are closed, so each drawn shape is its own piece')
ap.add_argument('--cap', type=float, default=3, help='touching same-number pieces join only while the piece stays under this %% of the page')
ap.add_argument('--glow', type=float, default=0.3, help='a piece that is partly sunlight/glow colours takes the number of its deeper colour when that covers at least this share')
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
    K = a.colors or old.get('k') or (len(old['palette']) if isinstance(old.get('palette'), list) else 28)
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

    # 2. spots = enclosed white areas, one per drawn shape. In a big open area (1%+ of the page) a small gap in an
    #    outline lets the white run on into the next shape (river into mist, mist up a hill), so there gaps up to
    #    about 2*--gap px are closed first: the long lines are thickened, each shape left is a seed, and the seeds
    #    grow back to the lines. Smaller shapes are kept exactly as drawn.
    white = (1 - ink).astype(np.uint8)
    n0, lab0, st0, _ = cv2.connectedComponentsWithStats(white, connectivity=4)
    lab = lab0.astype(np.int32); n = n0
    gr = int(round(a.gap * k2 ** 0.5))
    bigc = np.nonzero(st0[:, cv2.CC_STAT_AREA] >= 0.01 * w * h)[0]; bigc = bigc[bigc > 0]
    if gr > 0 and len(bigc):
        inbig = np.isin(lab0, bigc)
        se = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gr + 1, 2 * gr + 1))
        # only the long lines (outlines, shorelines) are thickened; short strokes (ripples, feathers, hatching) are
        # left as they are, so they never chop an open area like the water into pieces
        ni, il, ist, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
        longl = np.isin(il, np.nonzero(ist[:, cv2.CC_STAT_AREA] >= 200 * k2)[0][1:]).astype(np.uint8)
        n1, l1 = cv2.connectedComponents((inbig & (cv2.dilate(longl, se) == 0)).astype(np.uint8), connectivity=4)
        l1 = l1.astype(np.int32)
        cross = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        for _ in range(gr + 2):      # grow back over the thickened margin, through white only, never across a line
            m = inbig & (l1 == 0)
            if not m.any(): break
            d = cv2.dilate(l1.astype(np.float32), cross).astype(np.int32); up = m & (d > 0)
            if not up.any(): break
            l1[up] = d[up]
        # a narrow shape the thick lines covered (a pole, a thin branch) is not flooded from its open end: it keeps its own spot
        rest = inbig & (l1 == 0)
        nr, lr = cv2.connectedComponents(rest.astype(np.uint8), connectivity=4)
        l1[rest] = lr[rest] + n1 - 1
        lab[inbig] = l1[inbig] + n; n += n1 + nr
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
            if len(v):     # a speck inside a small thing (between a bird's feathers) stays with it, not the water
                cv_ = np.bincount(v); cs_ = np.nonzero(cv_)[0]; sm_ = cs_[area[cs_] < 0.01 * w * h]
                t = sm_[cv_[sm_].argmax()] if len(sm_) else cv_.argmax(); lab[ys, xs] = t; area[t] += area[i]; area[i] = 0
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

    blur = cv2.cvtColor(cv2.GaussianBlur(C, (0, 0), 6 * k2 ** 0.5), cv2.COLOR_BGR2LAB).astype(np.float32)

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
    # light warm colours (sunlight, glow: pale gold, peach, yellow) are light falling on a thing, not its own
    # colour: water with a sun path is numbered blue and a fire deep orange, and the fill still brings the glow
    glow = (cent[:, 0] >= 175) & (cent[:, 2] - 128 > 25) & (cent[:, 2] > cent[:, 1])
    for r in range(Rn):
        cnt = np.bincount(near[order[bounds[r]:bounds[r + 1]]], minlength=K).astype(np.float64)
        sc = simk @ cnt                        # similar shades count together: many blues outvote one gold
        if glow[sc.argmax()] and cnt[~glow].sum() >= a.glow * cnt.sum(): sc = np.where(glow, -1, sc)
        cidx[r] = sc.argmax()
    used = np.unique(cidx); cm = np.full(K, -1); cm[used] = np.arange(len(used)); cidx = cm[cidx]; cent = cent[used]
    # order palette light to dark-ish by hue for a tidy picker
    rgb = cv2.cvtColor(cent.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2RGB).reshape(-1, 3)
    hsv = cv2.cvtColor(rgb.reshape(1, -1, 3), cv2.COLOR_RGB2HSV).reshape(-1, 3)
    po = np.lexsort((-hsv[:, 2].astype(int), (hsv[:, 1] < 40).astype(int) * 1000 + hsv[:, 0].astype(int)))
    rank = np.empty(len(po), int); rank[po] = np.arange(len(po)); cidx = rank[cidx]; rgb = rgb[po]

    # 5b. fewer pieces without mixing things up: touching pieces with the same number become one piece (a leaded
    #     window's glass becomes a few pieces) while both are under 1% of the page and the piece stays under --cap,
    #     so a big shape (the water) never takes in a bird or a pole. Pieces too small to see a number in join the
    #     touching piece whose painted colour is closest, a small one first.
    par = np.arange(Rn)
    def root(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    A = lab[:, 1:].ravel(), lab[:, :-1].ravel(); B = lab[1:, :].ravel(), lab[:-1, :].ravel()
    p1 = np.concatenate([A[0], B[0]]) - 1; p2 = np.concatenate([A[1], B[1]]) - 1; d = p1 != p2
    pairs, cnt = np.unique(np.minimum(p1[d], p2[d]).astype(np.int64) * Rn + np.maximum(p1[d], p2[d]), return_counts=True)
    pa, pb = pairs // Rn, pairs % Rn
    sz = np.bincount(flat - 1, minlength=Rn).astype(np.float64)
    nb = {}; edge = {}
    for i, j, c in zip(pa, pb, cnt):
        nb.setdefault(i, []).append(j); nb.setdefault(j, []).append(i); edge[(i, j)] = edge[(j, i)] = c
    gsz = sz.copy(); bigP = 0.01 * w * h; capP = a.cap / 100 * w * h
    for k in np.argsort(-cnt):        # longest shared edge first
        i, j = pa[k], pb[k]
        if cidx[i] != cidx[j] or sz[i] >= bigP or sz[j] >= bigP: continue
        ri, rj = root(i), root(j)
        if ri == rj or gsz[ri] + gsz[rj] >= capP: continue
        par[ri] = rj; gsz[rj] += gsz[ri]
    minp = a.min * k2
    for _ in range(8):
        g = np.array([root(i) for i in range(Rn)])
        gs = np.bincount(g, weights=sz, minlength=Rn); gm = np.zeros((Rn, 3)); np.add.at(gm, g, med * sz[:, None]); gm /= np.maximum(gs, 1)[:, None]
        changed = False
        for r in np.argsort(gs):
            if gs[r] == 0 or gs[r] >= minp or root(r) != r: continue
            cand = {root(j) for i in np.nonzero(g == r)[0] for j in nb.get(i, [])} - {r}
            if not cand: continue
            # bits of one small thing (a bird's chest and feathers) gather together before any of them joins a big shape
            small_ = {q for q in cand if gs[q] < bigP}
            t = min(small_ or cand, key=lambda q: ((gm[q] - gm[r]) ** 2).sum())
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
    # where a piece ends at a closed gap (no line in the drawing), a light grey line shows the edge
    soft = np.zeros((h, w), bool)
    soft[:, 1:] |= (lab[:, 1:] != lab[:, :-1]) & (ink[:, 1:] == 0) & (ink[:, :-1] == 0)
    soft[1:, :] |= (lab[1:, :] != lab[:-1, :]) & (ink[1:, :] == 0) & (ink[:-1, :] == 0)

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
    meta = {'w': w, 'h': h, 'mode': 'pair', 'palette': rgb.tolist(), 'regions': regions, 'shade': a.shade, 'reveal': 1, 'v': 3, 'ink': S, 'k': K, 'b': int(time.time())}
    json.dump(meta, open(os.path.join(out, 'regions.json'), 'w'), separators=(',', ':'))
    pj = os.path.join(R, 'public', 'pages.json'); P = json.load(open(pj, encoding='utf-8'))
    for p in P:
        if p['slug'] == slug: p['regions'] = Rn; p['colors'] = len(rgb)
    for tries in range(20):   # Windows: a running preview server can briefly hold the file
        try:
            with open(pj + '.tmp', 'w', encoding='utf-8') as f: json.dump(P, f, ensure_ascii=False, indent=1)
            os.replace(pj + '.tmp', pj); break
        except PermissionError:
            time.sleep(0.5)
    big = max(r['a'] for r in regions) / (w * h)
    print(f"{slug}: {Rn} spots, {len(rgb)} colors, biggest {big:.1%}, mixed-colour {int((spread > 25).sum())}, tiny {sum(r['r'] < 3 for r in regions)}")
    return True


skipped = [s for s in a.slugs if not build(s)]
if skipped: print('SKIPPED (still old pages):', ' '.join(skipped))
