#!/usr/bin/env python3
"""Thin a page's drawing to fine pen lines, the way coloring apps show them.

  python3 tools/thin_ink.py <slug> [<slug> ...] [--width 2.2]

Reads public/pages/<slug>/ink.png (2x page size, black lines). Every stroke is reduced to its centre line,
about --width px wide at 2x (so roughly one page pixel); areas drawn solid black become an outline, never a black blob.
The original is kept once as pages/ink-full/<slug>.png (not in git) so the page can be re-thinned; if that copy is gone, run book_page.py again first. Then vector_ink.py redraws ink.json.
"""
import sys, os, argparse, subprocess, shutil
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+'); ap.add_argument('--width', type=float, default=2.2)
a = ap.parse_args()
for slug in a.slugs:
    d = os.path.join(R, 'public', 'pages', slug); full = os.path.join(R, 'pages', 'ink-full', slug + '.png'); os.makedirs(os.path.dirname(full), exist_ok=True); ip = os.path.join(d, 'ink.png')
    if not os.path.exists(full): shutil.copy(ip, full)
    g = cv2.imread(full, cv2.IMREAD_UNCHANGED)
    ink = ((g[:, :, 3] > 128) if g.ndim == 3 and g.shape[2] == 4 else ((g if g.ndim == 2 else cv2.cvtColor(g, cv2.COLOR_BGR2GRAY)) < 128)).astype(np.uint8)
    dt = cv2.distanceTransform(ink, cv2.DIST_L2, 5)
    ridge = (dt >= cv2.dilate(dt, np.ones((5, 5), np.uint8)) - 1.05) & (ink > 0)          # centre line of every stroke
    solid = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (29, 29))) > 0   # filled black areas
    r = max(1, int(round(a.width))); k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))
    core = cv2.erode(solid.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    edge = solid & ~(cv2.erode(solid.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)      # a filled black area keeps only its outline: no black blobs
    out = (cv2.dilate((ridge & ~core).astype(np.uint8), k) | cv2.dilate(edge.astype(np.uint8), k)) & ink
    soft = cv2.GaussianBlur(out.astype(np.float32) * 255, (0, 0), 0.6)
    if g.ndim == 3 and g.shape[2] == 4:
        o = np.zeros_like(g); o[:, :, 3] = np.clip(soft, 0, 255).astype(np.uint8)
    else: o = (255 - np.clip(soft, 0, 255)).astype(np.uint8)
    cv2.imwrite(ip, o, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    print(f'{slug}: ink {100*ink.mean():.0f}% -> {100*out.mean():.0f}% of the page')
subprocess.run([sys.executable, os.path.join(R, 'tools', 'vector_ink.py')] + a.slugs, check=True, stdout=subprocess.DEVNULL)
