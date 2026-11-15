#!/usr/bin/env python3
"""Repair a page whose pieces sprawl across objects: split every piece that holds clearly different colours.

  python3 tools/split_mixed.py <slug> [<slug> ...] [--far 26] [--share 0.28] [--min 500]

A piece is "mixed" when more than --share of it (away from the drawn lines) is further than --far from the
piece's own colour (hue weighted over light/shade, so ordinary shading does not count). Each mixed piece is
cut along the painting's colour boundaries into 2-4 parts; fragments under --min px (on a 1254px page) rejoin
the part they touch most. New parts take the nearest existing palette number. Then outline_page.py redraws
the outlines. Prints mixed area before and after. Changing pieces restarts saved progress on that page.
"""
import sys, os, json, argparse, subprocess
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+')
ap.add_argument('--far', type=float, default=26); ap.add_argument('--share', type=float, default=0.28); ap.add_argument('--min', type=float, default=500)
a = ap.parse_args(); W3 = np.array([.6, 1, 1], np.float32)   # sqrt(.35) on lightness
def measure(lbl, lab, paper):
    n = lbl.max() + 1; f = lbl.ravel()[paper]; lp = lab[paper]; cnt = np.bincount(f, minlength=n).astype(np.float64)
    mean = np.stack([np.bincount(f, weights=lp[:, i], minlength=n) for i in range(3)], 1) / np.maximum(cnt, 1)[:, None]
    dist = np.sqrt((((lp - mean[f]) * W3) ** 2).sum(1)); far = np.bincount(f, weights=(dist > a.far).astype(float), minlength=n) / np.maximum(cnt, 1)
    mixed = (far > a.share) & (cnt > 300); return mixed, cnt, mean
for slug in a.slugs:
    d = os.path.join(R, 'public', 'pages', slug); rp = os.path.join(d, 'regions.json'); m = json.load(open(rp))
    L = cv2.imread(os.path.join(d, 'labels.png')); lbl = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32); h, w = lbl.shape
    MIN = a.min * (w * h) / (1254 * 1254)
    col = cv2.resize(cv2.imread(os.path.join(d, 'color.jpg')), (w, h)); line = cv2.resize(cv2.imread(os.path.join(d, 'line.png'), 0), (w, h))
    paper = (cv2.erode(line, np.ones((5, 5), np.uint8)) > 150).ravel()
    sm = cv2.pyrMeanShiftFiltering(cv2.bilateralFilter(col, 9, 40, 9), 10, 22)
    lab2 = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).astype(np.float32); lab = cv2.cvtColor(cv2.GaussianBlur(col, (0, 0), 2), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)
    mixed, cnt, _ = measure(lbl, lab, paper); before = cnt[mixed].sum() / max(1, cnt[1:].sum()); n0 = int(lbl.max()); nxt = n0 + 1
    for r in np.nonzero(mixed)[0]:
        ys, xs = np.nonzero(lbl == r)
        if len(ys) < 2 * MIN: continue
        px = lab2[ys, xs] * W3; k = int(np.clip(len(ys) // int(4 * MIN) + 2, 2, 4))
        _, asg, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5), 3, cv2.KMEANS_PP_CENTERS)
        y0, x0 = ys.min(), xs.min(); sub = np.zeros((ys.max() - y0 + 1, xs.max() - x0 + 1), np.uint8); sub[ys - y0, xs - x0] = asg.ravel() + 1
        sub2 = cv2.medianBlur(sub, 7); sub = np.where(sub > 0, np.where(sub2 > 0, sub2, sub), 0).astype(np.uint8)
        parts = np.zeros(sub.shape, np.int32); base = 0
        for j in range(1, k + 1):
            c, cc = cv2.connectedComponents((sub == j).astype(np.uint8), connectivity=4); parts[cc > 0] = cc[cc > 0] + base; base += c - 1
        for _ in range(10):   # small fragments rejoin the part they touch most
            ar = np.bincount(parts.ravel()); small = [i for i in range(1, len(ar)) if 0 < ar[i] < MIN]
            if not small: break
            big = np.where(np.isin(parts, small), 0, parts)
            if not big.any(): parts[parts > 0] = 1; break
            for _i in range(200):
                hole = (big == 0) & (parts > 0)
                if not hole.any(): break
                big = np.where(hole, cv2.dilate(big.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32), big)
            parts = np.where(parts > 0, big, 0)
        ids = [i for i in np.unique(parts) if i > 0]
        for i in ids[1:]:
            py, px_ = np.nonzero(parts == i); lbl[py + y0, px_ + x0] = nxt; nxt += 1
    if nxt == n0 + 1: print(slug, 'nothing to split'); continue
    mixed2, cnt2, mean2 = measure(lbl, lab, paper); after = cnt2[mixed2].sum() / max(1, cnt2[1:].sum()); Rn = int(lbl.max())
    pal = cv2.cvtColor(np.array(m['palette'], np.uint8).reshape(1, -1, 3)[:, :, ::-1].copy(), cv2.COLOR_BGR2LAB)[0].astype(np.float64)
    old = {r['id']: r['c'] for r in m['regions']}; regions = []
    for r in range(1, Rn + 1):
        ys, xs = np.nonzero(lbl == r)
        if not len(ys): continue
        c = old[r] if r <= n0 and not mixed[r] else int(np.argmin((((pal - mean2[r]) * W3) ** 2).sum(1))) if cnt2[r] > 0 else old.get(r, 0)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1; mk = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8); mk[ys - y0 + 1, xs - x0 + 1] = 1
        dt = cv2.distanceTransform(mk, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
        regions.append({'id': r, 'c': c, 'a': int(len(ys)), 'x': int(x + x0 - 1), 'y': int(y + y0 - 1), 'r': round(float(dt.max()), 1)})
    rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = lbl % 256; rgb[:, :, 1] = lbl // 256
    cv2.imwrite(os.path.join(d, 'labels.png'), rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    m.setdefault('base', n0); m['regions'] = regions; json.dump(m, open(rp, 'w'), separators=(',', ':'))
    pj = os.path.join(R, 'public', 'pages.json'); P = json.load(open(pj, encoding='utf-8'))
    for x in P:
        if x['slug'] == slug: x['regions'] = len(regions); x.pop('level', None)
    json.dump(P, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    subprocess.run([sys.executable, os.path.join(R, 'tools', 'outline_page.py'), slug], check=True, stdout=subprocess.DEVNULL)
    print(f'{slug}: {n0} -> {len(regions)} pieces; mixed area {100*before:.0f}% -> {100*after:.0f}%')
