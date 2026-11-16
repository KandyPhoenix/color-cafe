#!/usr/bin/env python3
"""Make every number match what its pieces really colour.

  python3 tools/renumber_page.py <slug> [<slug> ...] | --all

Rebuilds the palette from the pieces' own colours in the painting (same number of colours as before) and
gives each piece the number of the colour it actually is. Pieces are not changed, so saved progress stays.
--all does every colour-by-number page that was not built from flat art.
"""
import sys, os, json
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); pj = os.path.join(R, 'public', 'pages.json')
W3 = np.array([.5, 1, 1], np.float32)   # hue counts twice as much as light and dark: green leaves and brown wood never share a number
slugs = sys.argv[1:]
if slugs == ['--all']:
    slugs = [p['slug'] for p in json.load(open(pj, encoding='utf-8')) if p['mode'] == 'pair' and not any(json.load(open(os.path.join(R, 'public', 'pages', p['slug'], 'regions.json'))).get(k) for k in ('flat', 'blend'))]
for slug in slugs:
    d = os.path.join(R, 'public', 'pages', slug); rp = os.path.join(d, 'regions.json'); m = json.load(open(rp))
    L = cv2.imread(os.path.join(d, 'labels.png')); lbl = (L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32)).ravel(); h, w = L.shape[:2]
    lab = cv2.cvtColor(cv2.resize(cv2.imread(os.path.join(d, 'color.jpg')), (w, h)), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64)
    paper = (cv2.erode(cv2.resize(cv2.imread(os.path.join(d, 'line.png'), 0), (w, h)), np.ones((5, 5), np.uint8)) > 150).ravel()
    n = lbl.max() + 1; cnt = np.bincount(lbl[paper], minlength=n).astype(np.float64); call = np.bincount(lbl, minlength=n)
    mean = np.stack([np.bincount(lbl[paper], weights=lab[paper][:, i], minlength=n) for i in range(3)], 1)
    thin = cnt < 20                                             # a piece that is nearly all line: use all its pixels
    if thin.any():
        ma = np.stack([np.bincount(lbl, weights=lab[:, i], minlength=n) for i in range(3)], 1); mean[thin] = ma[thin]; cnt[thin] = call[thin]
    mean /= np.maximum(cnt, 1)[:, None]
    ids = np.array([r['id'] for r in m['regions']]); K = max(len(m['palette']), 22); pts = (mean[ids] * W3).astype(np.float32)   # at least 22 numbers, so every distinct colour has its own
    rep = np.repeat(pts, np.clip(np.sqrt(call[ids]) // 6, 1, 40).astype(int), 0)   # bigger pieces weigh more
    _, _, cen = cv2.kmeans(rep, K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, .2), 6, cv2.KMEANS_PP_CENTERS)
    c = np.argmin(((pts[:, None, :] - cen[None]) ** 2).sum(2), 1); used = np.unique(c); remap = {int(o): i for i, o in enumerate(used)}
    old = [r['c'] for r in m['regions']]; oldpal = np.array(m['palette'], np.float64)
    labc = (cen[used] / W3).clip(0, 255).astype(np.uint8).reshape(1, -1, 3); rgb = cv2.cvtColor(labc, cv2.COLOR_LAB2BGR)[0][:, ::-1]
    m['palette'] = [[int(v) for v in x] for x in rgb]
    for r, ci in zip(m['regions'], c): r['c'] = remap[int(ci)]
    newpal = np.array(m['palette'], np.float64); moved = np.mean([np.abs(oldpal[o] - newpal[r['c']]).sum() > 90 for o, r in zip(old, m['regions'])])
    json.dump(m, open(rp, 'w'), separators=(',', ':'))
    P = json.load(open(pj, encoding='utf-8'))
    for x in P:
        if x['slug'] == slug: x['colors'] = len(m['palette'])
    json.dump(P, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{slug}: {len(m["palette"])} colours, {100*moved:.0f}% of pieces got a clearly different colour')
