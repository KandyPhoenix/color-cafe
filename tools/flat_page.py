#!/usr/bin/env python3
"""Build a colour-by-number page the way coloring apps do: shapes first.

  python3 tools/flat_page.py <slug> <flat.png> [<rich.jpg>] --title "..." --theme <id> [--style "..."]
                             [--colors 24] [--min 500] [--level Easy]

<flat.png> is flat-colour art: every object a solid colour with a hard edge (no shading, no outlines).
Flat colour is the blueprint: each patch of one colour is one piece, exactly as drawn, so there is nothing
to guess. Its colours give the palette numbers.
<rich.jpg> (optional) is the same picture repainted rich and shaded, with every shape kept in place. When
given, that is what a tap reveals inside a piece; otherwise a tap reveals the flat colour.

Writes public/pages/<slug>/: labels.png, regions.json (v 3, look 2, outlines as vector "lines"), color.jpg,
line.png (outline drawing, also used to place numbers), thumb.jpg, feature.jpg, and the entry in
public/pages.json. Sources are copied to pages/src. Needs opencv, numpy.
"""
import sys, os, json, argparse, time, shutil, subprocess
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('slug'); ap.add_argument('flat'); ap.add_argument('rich', nargs='?')
ap.add_argument('--title', required=True); ap.add_argument('--theme', required=True); ap.add_argument('--style', default='')
ap.add_argument('--colors', type=int, default=24); ap.add_argument('--min', type=float, default=500, help='smallest piece, px on a 1254px page')
ap.add_argument('--size', type=int, default=1254); ap.add_argument('--level', default=None); ap.add_argument('--artist', default='Original art')
a = ap.parse_args(); t0 = time.time()
flat = cv2.imread(a.flat)
if flat is None: sys.exit('cannot read ' + a.flat)
h0, w0 = flat.shape[:2]; sc = a.size / max(h0, w0); w, h = round(w0 * sc), round(h0 * sc)
flat = cv2.resize(flat, (w, h), interpolation=cv2.INTER_AREA)
MIN = a.min * (w * h) / (1254 * 1254)

# 1. the picture's own colours: smooth away compression noise, then find the K flat colours
sm = cv2.pyrMeanShiftFiltering(cv2.bilateralFilter(flat, 7, 30, 7), 8, 18)
lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
samp = lab[np.random.RandomState(1).choice(len(lab), min(len(lab), 200000), replace=False)]
_, _, cen = cv2.kmeans(samp, a.colors, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, .3), 5, cv2.KMEANS_PP_CENTERS)
cidx = np.empty(len(lab), np.int32)
for i in range(0, len(lab), 400000):
    cidx[i:i + 400000] = np.argmin(((lab[i:i + 400000, None, :] - cen[None]) ** 2).sum(2), 1)
cidx = cidx.reshape(h, w)

# 2. pieces = connected patches of one colour
lbl = np.zeros((h, w), np.int32); n = 0
for c in range(a.colors):
    k, cc = cv2.connectedComponents((cidx == c).astype(np.uint8), connectivity=4)
    lbl[cc > 0] = cc[cc > 0] + n; n += k - 1
# 3. slivers (the soft pixels along an edge) and specks join the neighbour they touch most
for _ in range(12):
    area = np.bincount(lbl.ravel(), minlength=lbl.max() + 1); small = np.nonzero((area > 0) & (area < MIN))[0]; small = small[small > 0]
    if not len(small): break
    sm_mask = np.isin(lbl, small)
    # grow the big pieces into the small ones, one pixel ring at a time
    big = np.where(sm_mask, 0, lbl).astype(np.int32)
    for _i in range(400):
        if not (big == 0).any(): break
        d = cv2.dilate(big.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.int32)
        big = np.where(big == 0, d, big)
    lbl = big
_, lbl = np.unique(lbl, return_inverse=True); lbl = lbl.reshape(h, w).astype(np.int32) + 1
Rn = int(lbl.max())

# 4. palette from the pieces' own flat colour, numbered light to dark
flab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float64); fl = lbl.ravel()
cnt = np.bincount(fl, minlength=Rn + 1).astype(np.float64)
mean = np.stack([np.bincount(fl, weights=flab[:, i], minlength=Rn + 1) for i in range(3)], 1)[1:] / cnt[1:, None]
K = min(a.colors, Rn)
_, asg, pc = cv2.kmeans(mean.astype(np.float32), K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 80, .2), 8, cv2.KMEANS_PP_CENTERS)
asg = asg.ravel(); used = np.unique(asg); pc = pc[used]; asg = np.searchsorted(used, asg); K = len(used)
order = np.argsort(-pc[:, 0]); rank = np.empty(K, int); rank[order] = np.arange(K); rc = rank[asg]
pal = cv2.cvtColor(pc[order].reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
palette = [[int(c[2]), int(c[1]), int(c[0])] for c in pal]
regions = []
for r in range(1, Rn + 1):
    ys, xs = np.nonzero(lbl == r); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8); m[ys - y0 + 1, xs - x0 + 1] = 1
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
    regions.append({'id': r, 'c': int(rc[r - 1]), 'a': int(len(ys)), 'x': int(x + x0 - 1), 'y': int(y + y0 - 1), 'r': round(float(dt.max()), 1)})

# 5. write the page
out = os.path.join(R, 'public', 'pages', a.slug); os.makedirs(out, exist_ok=True)
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = lbl % 256; rgb[:, :, 1] = lbl // 256
cv2.imwrite(os.path.join(out, 'labels.png'), rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
col = flat
if a.rich:
    rich = cv2.imread(a.rich)
    if rich is None: sys.exit('cannot read ' + a.rich)
    col = cv2.resize(rich, (w, h), interpolation=cv2.INTER_AREA)
cv2.imwrite(os.path.join(out, 'color.jpg'), col, [cv2.IMWRITE_JPEG_QUALITY, 90])
e = np.zeros((h, w), np.uint8); e[:, 1:] |= (lbl[:, 1:] != lbl[:, :-1]).astype(np.uint8); e[1:, :] |= (lbl[1:, :] != lbl[:-1, :]).astype(np.uint8)
line = np.where(e > 0, 0, 255).astype(np.uint8)
cv2.imwrite(os.path.join(out, 'line.png'), line, [cv2.IMWRITE_PNG_COMPRESSION, 9])
meta = {'w': w, 'h': h, 'mode': 'pair', 'palette': palette, 'regions': regions, 'shade': 1.0, 'reveal': 1, 'v': 3, 'ink': 0, 'k': K, 'b': int(time.time()), 'flat': 1}
json.dump(meta, open(os.path.join(out, 'regions.json'), 'w'), separators=(',', ':'))
src = os.path.join(R, 'pages', 'src'); os.makedirs(src, exist_ok=True)
shutil.copy(a.flat, os.path.join(src, a.slug + '-flat' + os.path.splitext(a.flat)[1]))
if a.rich: shutil.copy(a.rich, os.path.join(src, a.slug + '-color' + os.path.splitext(a.rich)[1]))
pj = os.path.join(R, 'public', 'pages.json'); pages = [p for p in json.load(open(pj, encoding='utf-8')) if p['slug'] != a.slug]
level = a.level or ('Easy' if Rn <= 270 else 'Medium' if Rn <= 450 else 'Hard')
pages.append({'slug': a.slug, 'title': a.title, 'theme': a.theme, 'mode': 'pair', 'artist': a.artist, 'style': a.style, 'w': w, 'h': h,
              'regions': Rn, 'colors': K, 'added': time.strftime('%Y-%m-%d'), 'level': level})
json.dump(pages, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
# outlines (vector) + thumbnail, then the feature image: finished on the left, blank page on the right
subprocess.run([sys.executable, os.path.join(R, 'tools', 'outline_page.py'), a.slug], check=True, stdout=subprocess.DEVNULL)
blank = cv2.cvtColor(cv2.erode(line, np.ones((2, 2), np.uint8)), cv2.COLOR_GRAY2BGR)
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); t = np.clip(((xx - 0.60 * w) + (yy - 0.5 * h) * 0.35) / (0.06 * w) + 0.5, 0, 1)[..., None]
feat = (np.minimum(col, blank) * (1 - t) + blank * t).astype(np.uint8)
cv2.imwrite(os.path.join(out, 'feature.jpg'), cv2.resize(feat, (900, round(900 * h / w)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 86])
if not a.rich:   # no rich repaint supplied: paint light, shadow and deeper colour into the flat pieces
    subprocess.run([sys.executable, os.path.join(R, 'tools', 'shade_page.py'), a.slug], check=True, stdout=subprocess.DEVNULL)
ar = sorted(r['a'] for r in regions)
print(f"{a.slug}: {Rn} pieces, {K} colours, smallest {ar[0]} px, median {ar[len(ar)//2]}, {level}, {time.time()-t0:.0f}s")
