#!/usr/bin/env python3
"""Turn a page's drawing into smooth vector lines, so they stay sharp and glossy at any zoom.

  python3 tools/vector_ink.py <slug> [<slug> ...]      # or --all

Reads public/pages/<slug>/ink.png (the drawing the app shows, from book_page.py / make_ink.py) and writes
public/pages/<slug>/ink.json: every ink shape as a closed outline (holes included), smoothed and simplified.
  {"s": 8, "p": [[x0, y0, dx, dy, dx, dy, ...], ...]}     coordinates in 1/8 page pixels, delta-encoded
The app fills these outlines (even-odd) with curves through the points, so a line is a clean solid shape
however far you zoom in. ink.png stays as the fallback and for the zoomed-out view.
Sets "inkv": 1 in regions.json. Run after book_page.py whenever a page's drawing changes. Needs opencv, numpy.
"""
import sys, os, json, argparse, glob
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='*'); ap.add_argument('--all', action='store_true')
ap.add_argument('--eps', type=float, default=0.22, help='simplify tolerance in page pixels')
ap.add_argument('--speck', type=float, default=6, help='drop ink shapes and holes smaller than this (page px area)')
a = ap.parse_args()
slugs = a.slugs or ([os.path.basename(os.path.dirname(p)) for p in sorted(glob.glob(os.path.join(R, 'public', 'pages', '*', 'ink.png')))] if a.all else [])
Q = 8
for slug in slugs:
    d = os.path.join(R, 'public', 'pages', slug); rp = os.path.join(d, 'regions.json')
    g = cv2.imread(os.path.join(d, 'ink.png'), cv2.IMREAD_GRAYSCALE)
    if g is None or not os.path.exists(rp): print('skip', slug); continue
    m = json.load(open(rp)); w, h = m['w'], m['h']
    U = 4                                              # work at 4x page size
    f = U * w / g.shape[1]
    big = cv2.resize(g, (w * U, h * U), interpolation=cv2.INTER_CUBIC) if abs(f - 1) > 1e-6 else g
    big = cv2.GaussianBlur(big, (0, 0), 0.55 * U)      # round off the pixel steps
    mask = (big < 128).astype(np.uint8)
    cs, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []; npts = 0
    for c in cs:
        if abs(cv2.contourArea(c)) < a.speck * U * U or len(c) < 8: continue
        p = c[:, 0, :].astype(np.float32)
        k = 2 * U + 1; pad = np.concatenate([p[-k:], p, p[:k]])     # closed moving average along the outline
        ker = np.ones(k, np.float32) / k
        sm = np.stack([np.convolve(pad[:, 0], ker, 'same'), np.convolve(pad[:, 1], ker, 'same')], 1)[k:-k]
        ap_ = cv2.approxPolyDP(sm.reshape(-1, 1, 2), a.eps * U, True)[:, 0, :]
        if len(ap_) < 3: continue
        q = np.round((ap_ + 0.5) / U * Q).astype(np.int32)
        dl = np.diff(q, axis=0); keep = np.any(dl != 0, 1)
        row = [int(q[0, 0]), int(q[0, 1])] + dl[keep].ravel().tolist()
        if len(row) >= 6: out.append(row); npts += len(row) // 2
    json.dump({'s': Q, 'p': out}, open(os.path.join(d, 'ink.json'), 'w'), separators=(',', ':'))
    m['inkv'] = 1; json.dump(m, open(rp, 'w'), separators=(',', ':'))
    print(f"{slug}: {len(out)} shapes, {npts} points, {os.path.getsize(os.path.join(d, 'ink.json')) // 1024} KB")
