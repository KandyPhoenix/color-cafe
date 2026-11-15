#!/usr/bin/env python3
"""Give a colour-by-number page the coloring-app look: a thin black outline around every piece you tap.

  python3 tools/outline_page.py <slug> [<slug> ...]      # or --all

A coloring app's page is built from shapes: each piece is a closed shape, the blank page is those shapes'
outlines, and filling a shape colours exactly what its outline encloses. This tool makes a page work that
way from the pieces it already has (public/pages/<slug>/labels.png, from book_page.py):

  * traces the edge between every two pieces into smooth vector lines, stored in regions.json as "lines"
    (delta-encoded, quarter pixels). The app strokes them thin and black, so outlines and fills can never
    disagree and stay sharp at any zoom.
  * sets "look": 2 in regions.json. With it the app draws the artist's own drawing (ink.json / ink.png)
    only as faint grey detail inside the pieces, so the picture stays recognisable without heavy ink.
  * redraws thumb.jpg in the same look.

Run after book_page.py and vector_ink.py. Needs opencv, numpy.
"""
import sys, os, json, argparse, glob
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='*'); ap.add_argument('--all', action='store_true')
ap.add_argument('--smooth', type=float, default=2.0, help='how much to round the outlines (pixels)')
a = ap.parse_args()
slugs = a.slugs or ([os.path.basename(os.path.dirname(p)) for p in sorted(glob.glob(os.path.join(R, 'public', 'pages', '*', 'ink.png')))] if a.all else [])

def trace(lbl):
    h, w = lbl.shape
    hz = lbl[:-1, :] != lbl[1:, :]; vt = lbl[:, :-1] != lbl[:, 1:]; W1 = w + 1
    yy, xx = np.nonzero(hz); e1 = np.stack([(yy + 1) * W1 + xx, (yy + 1) * W1 + xx + 1], 1)
    yy, xx = np.nonzero(vt); e2 = np.stack([yy * W1 + xx + 1, (yy + 1) * W1 + xx + 1], 1)
    E = np.concatenate([e1, e2]).astype(np.int64)
    deg = np.bincount(E.ravel(), minlength=W1 * (h + 1)); adj = {}
    for i, (p, q) in enumerate(E.tolist()):
        adj.setdefault(p, []).append(i); adj.setdefault(q, []).append(i)
    used = np.zeros(len(E), bool)
    def walk(start, ei):
        pts = [start]; cur = start
        while True:
            used[ei] = True; p, q = E[ei]; cur = int(q if p == cur else p); pts.append(cur)
            if deg[cur] != 2 or cur == start: return pts
            nx = [j for j in adj[cur] if not used[j]]
            if not nx: return pts
            ei = nx[0]
    chains = []
    for v in np.nonzero((deg > 0) & (deg != 2))[0].tolist():
        for ei in adj[v]:
            if not used[ei]: chains.append(walk(v, ei))
    for ei in range(len(E)):
        if not used[ei]: chains.append(walk(int(E[ei][0]), ei))
    sig = a.smooth; rad = int(round(sig * 2.5)); kx = np.exp(-np.arange(-rad, rad + 1) ** 2 / (2 * sig * sig)); kx /= kx.sum()
    out = []
    for c in chains:
        if len(c) < 2: continue
        P = np.array([(p % W1, p // W1) for p in c], np.float64); closed = len(c) > 3 and c[0] == c[-1]
        if len(P) > 4:
            if closed:
                Q = P[:-1]; Qp = np.concatenate([Q[-rad:], Q, Q[:rad]])
                S = np.stack([np.convolve(Qp[:, i], kx, 'valid') for i in range(2)], 1); P = np.concatenate([S, S[:1]])
            else:   # ends are junctions shared with other lines: pin them, ease the smoothing in
                Pp = np.concatenate([np.repeat(P[:1], rad, 0), P, np.repeat(P[-1:], rad, 0)])
                S = np.stack([np.convolve(Pp[:, i], kx, 'valid') for i in range(2)], 1)
                t = np.minimum(np.arange(len(P)), np.arange(len(P))[::-1]); wgt = np.clip(t / rad, 0, 1)[:, None]
                P = P * (1 - wgt) + S * wgt
        q = cv2.approxPolyDP(np.round(P * 4).astype(np.int32).reshape(-1, 1, 2), 1.0, False).reshape(-1, 2)
        if len(q) >= 2: out.append(q)
    return out

for slug in slugs:
    d = os.path.join(R, 'public', 'pages', slug); rp = os.path.join(d, 'regions.json')
    L = cv2.imread(os.path.join(d, 'labels.png'))
    if L is None or not os.path.exists(rp): print('skip', slug); continue
    lbl = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32); h, w = lbl.shape
    chains = trace(lbl)
    m = json.load(open(rp))
    m['lines'] = [np.concatenate([q[:1], np.diff(q, axis=0)]).ravel().tolist() for q in chains]; m['look'] = 2
    json.dump(m, open(rp, 'w'), separators=(',', ':'))
    # thumbnail in the same look: crisp black outlines only
    U = 2; img = np.full((h * U, w * U), 255, np.uint8)
    g = cv2.imread(os.path.join(d, 'line.png'), cv2.IMREAD_GRAYSCALE)
    if g is not None and not m.get('solo'):   # meta.solo pages show outlines only; the rest show their drawing in black too
        g = cv2.resize(g, (w * U, h * U), interpolation=cv2.INTER_CUBIC).astype(np.float32); img = g.astype(np.uint8)
    cv2.polylines(img, [np.round(q * (U / 4) * 16).astype(np.int32).reshape(-1, 1, 2) for q in chains], False, 0, U * 2, cv2.LINE_AA, 4)
    ts = 420 / max(h, w)
    cv2.imwrite(os.path.join(d, 'thumb.jpg'), cv2.resize(img, (round(w * ts), round(h * ts)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 84])
    print(f"{slug}: {len(chains)} outline lines, {sum(len(q) for q in chains)} points, regions.json {os.path.getsize(rp) // 1024} KB")
