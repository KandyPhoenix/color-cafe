#!/usr/bin/env python3
"""Rebuild a colour-by-number page so it is easy to colour.

  python3 tools/simplify_page.py <slug> [--src DIR] [--colors 28] [--min 1800] [--width 9] [--same 8]

Reads the ink drawing and DIR/color.jpg (the painting, already aligned to the drawing; make_page.py does
that alignment). DIR defaults to public/pages/<slug>/. The ink drawing is pages/ink/<slug>.png when that
exists, else DIR/line.png; the first run saves it to pages/ink/<slug>.png, because line.png is then
replaced by the simplified outlines. So a page can always be rebuilt in place with new settings:

  python3 tools/simplify_page.py <slug> --min 800      # more, smaller pieces
  python3 tools/simplify_page.py <slug> --min 1500     # fewer, bigger pieces

What it fixes, compared with using the ink drawing as-is:
  * Too much detail: tiny pieces and thin slivers are merged into the touching piece whose painted
    colour is closest, and touching pieces of (nearly) the same colour become one piece.
  * Leaks: a piece whose painting spans two clearly different colours (an outline with a gap) is split
    along the painting's own colour edge.
  * Heavy black lines and blur on zoom: the black ink is no longer shown. Every outline is traced from the
    final piece map (so every line is closed and is exactly the edge of what gets filled) and stored as
    vector polylines in regions.json ("lines"). The app strokes them thin and grey at any zoom.

Writes labels.png, regions.json, line.png (outline raster, for older app builds), keeps the page's
thumb.jpg / feature.jpg (the artist's drawing), and updates the page's entry in public/pages.json
(regions/colors). Needs opencv-python, numpy.

Rebuilding changes the pieces, so anyone partway through that page starts it fresh.
"""
import sys, os, json, argparse, heapq, time
import numpy as np, cv2

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('slug'); ap.add_argument('--src', default=None)
ap.add_argument('--colors', type=int, default=28, help='palette size')
ap.add_argument('--min', type=float, default=1800, help='smallest piece, in pixels of a 1254px page (scaled for other sizes)')
ap.add_argument('--width', type=float, default=9.0, help='thinnest piece (approx. width in px); thinner slivers are merged')
ap.add_argument('--same', type=float, default=8.0, help='merge touching pieces whose painted colours differ by less than this (Lab dE)')
ap.add_argument('--hard', type=float, default=0.6, help='pieces under this fraction of --min always merge, whatever their colour')
ap.add_argument('--distinct', type=float, default=28.0, help='a piece between --hard and --min stays if every neighbour differs from it by more than this (Lab dE)')
ap.add_argument('--split', type=float, default=20.0, help='split a piece whose painted colours spread wider than this')
ap.add_argument('--maxitem', type=float, default=0.06, help='never merge into a piece bigger than this fraction of the page')
ap.add_argument('--ink', type=int, default=110, help='grey level below which the drawing counts as ink')
ap.add_argument('--line', default=None, help='the ink drawing (default pages/ink/<slug>.png, else <src>/line.png)')
ap.add_argument('--shade', type=float, default=None, help='keep/set regions.json "shade" (0-1); default keeps the old value or 0.5')
a = ap.parse_args(); t0 = time.time()
src = a.src or os.path.join(R, 'public', 'pages', a.slug)
out = os.path.join(R, 'public', 'pages', a.slug)
saved = os.path.join(R, 'pages', 'ink', a.slug + '.png')
linep = a.line or (saved if os.path.exists(saved) else os.path.join(src, 'line.png'))
old = {}
try: old = json.load(open(os.path.join(src, 'regions.json')))
except Exception: pass
if linep == os.path.join(src, 'line.png') and old.get('v') == 2:
    sys.exit(f'{linep} is already the simplified outline, not the ink drawing. Put the original drawing at {saved} or pass --line')

L = cv2.imread(linep, cv2.IMREAD_GRAYSCALE)
col = cv2.imread(os.path.join(src, 'color.jpg'))
if L is None or col is None: sys.exit(f'need the ink drawing ({linep}) and {os.path.join(src, "color.jpg")}')
if not os.path.exists(saved):
    os.makedirs(os.path.dirname(saved), exist_ok=True); cv2.imwrite(saved, L, [cv2.IMWRITE_PNG_COMPRESSION, 9])
h, w = L.shape
if col.shape[:2] != (h, w): col = cv2.resize(col, (w, h), interpolation=cv2.INTER_AREA)
k2 = (w * h) / (1254 * 1254)
MIN = a.min * k2; MINW = a.width * (k2 ** .5)
lab = cv2.cvtColor(cv2.GaussianBlur(col, (0, 0), 1.2), cv2.COLOR_BGR2LAB).astype(np.float32)

# ---- 1. pieces = paper areas enclosed by the ink
ink = (L < a.ink).astype(np.uint8)
ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, lbl = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4)
area = np.bincount(lbl.ravel(), minlength=n)
lbl[(area[lbl] < 30) & (lbl > 0)] = 0          # specks inside ink are ink
paper = lbl > 0

# ---- 2. split pieces whose painting holds two clearly different colours (gaps in the outline)
def stats(lb, m):
    f = lb[m]; N = lb.max() + 1
    c = np.bincount(f, minlength=N).astype(np.float64)
    s = np.stack([np.bincount(f, weights=lab[:, :, i][m], minlength=N) for i in range(3)], 1)
    q = np.stack([np.bincount(f, weights=lab[:, :, i][m] ** 2, minlength=N) for i in range(3)], 1)
    return c, s, q
cnt, s1, s2 = stats(lbl, paper)
mu = s1 / np.maximum(cnt, 1)[:, None]
sd = np.sqrt(np.maximum(s2 / np.maximum(cnt, 1)[:, None] - mu ** 2, 0)); sd[:, 0] *= .6
spread = sd.sum(1)
nxt = lbl.max() + 1; nsplit = 0
for r in np.nonzero((spread > a.split) & (cnt >= 2 * MIN))[0]:
    if r == 0: continue
    ys, xs = np.nonzero(lbl == r); px = lab[ys, xs]
    k = int(min(4, max(2, round(spread[r] / a.split) + 1)))
    _, asg, cen = cv2.kmeans(px, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, .5), 3, cv2.KMEANS_PP_CENTERS)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = np.zeros((y1 - y0, x1 - x0), np.uint8); sub[ys - y0, xs - x0] = asg.ravel() + 1
    sub = cv2.medianBlur(sub, 5); sub[lbl[y0:y1, x0:x1] != r] = 0   # smooth the cut so it is a clean line
    part = np.zeros(sub.shape, np.int32); base = 0
    for j in range(1, k + 1):
        m2, cc = cv2.connectedComponents((sub == j).astype(np.uint8), connectivity=4)
        part[cc > 0] = cc[cc > 0] + base; base += m2 - 1
    pa = np.bincount(part.ravel())
    big = [i for i in range(1, len(pa)) if pa[i] >= MIN]
    if len(big) < 2: continue
    # keep the big parts; everything else in the piece goes to the nearest big part
    keep = np.isin(part, big)
    inside = lbl[y0:y1, x0:x1] == r
    dt, near = cv2.distanceTransformWithLabels((~keep).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    lut = np.zeros(near.max() + 1, np.int32); lut[near[keep]] = part[keep]
    part = np.where(inside, lut[near], 0)
    for i in big[1:]:
        sl = lbl[y0:y1, x0:x1]; sl[part == i] = nxt; nxt += 1
    nsplit += 1

# ---- 3. give every ink pixel to the nearest piece, so pieces tile the page with no gaps
paper = lbl > 0
dt, near = cv2.distanceTransformWithLabels((~paper).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
lut = np.zeros(near.max() + 1, np.int32); lut[near[paper]] = lbl[paper]
lbl = np.where(paper, lbl, lut[near]).astype(np.int32)
_, lbl = np.unique(lbl, return_inverse=True); lbl = (lbl.reshape(h, w) + 1).astype(np.int32)
n0 = lbl.max()

# ---- 4. region graph: colour (from paper pixels only), area, shared border lengths
N = n0 + 1
cnt, s1, _ = stats(lbl, paper)
allcnt = np.bincount(lbl.ravel(), minlength=N).astype(np.float64)
nb = [dict() for _ in range(N)]
for A, B in ((lbl[:, :-1], lbl[:, 1:]), (lbl[:-1, :], lbl[1:, :])):
    d = A != B; p = np.stack([A[d], B[d]], 1); p.sort(1)
    u, c = np.unique(p, axis=0, return_counts=True)
    for (x, y), k in zip(u.tolist(), c.tolist()):
        nb[x][y] = nb[x].get(y, 0) + k; nb[y][x] = nb[y].get(x, 0) + k
edge = np.zeros(N);
for row in (lbl[0], lbl[-1], lbl[:, 0], lbl[:, -1]): edge += np.bincount(row, minlength=N)
parent = list(range(N))
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
def colour(r): return s1[r] / cnt[r] if cnt[r] > 0 else None
def dE(r, q):
    c1, c2 = colour(r), colour(q)
    if c1 is None or c2 is None: return 0.0
    d = c1 - c2; return float(np.sqrt(0.5 * d[0] ** 2 + d[1] ** 2 + d[2] ** 2))
def perim(r): return sum(nb[r].values()) + edge[r]
LIMIT = a.maxitem * w * h
def merge(keep, gone):
    parent[gone] = keep
    cnt[keep] += cnt[gone]; s1[keep] += s1[gone]; allcnt[keep] += allcnt[gone]; edge[keep] += edge[gone]
    for q, k in nb[gone].items():
        if q == keep: continue
        nb[keep][q] = nb[keep].get(q, 0) + k
        del nb[q][gone]; nb[q][keep] = nb[q].get(keep, 0) + k
    nb[keep].pop(gone, None); nb[gone] = {}

# 4a. touching pieces that are the same colour in the painting become one piece
pairs = []
for r in range(1, N):
    for q in nb[r]:
        if q > r: pairs.append((dE(r, q), r, q))
heapq.heapify(pairs)
while pairs:
    d0, r, q = heapq.heappop(pairs)
    if d0 > a.same: break
    r, q = find(r), find(q)
    if r == q or q not in nb[r] or allcnt[r] + allcnt[q] > LIMIT: continue
    d1 = dE(r, q)
    if d1 > d0 + 1e-6: heapq.heappush(pairs, (d1, r, q)); continue   # colours changed since queued
    if allcnt[q] > allcnt[r]: r, q = q, r
    merge(r, q)
    for x in nb[r]: heapq.heappush(pairs, (dE(r, x), r, x))

# 4b. small or thin pieces join the touching piece with the closest colour
#     A piece that is only "smallish" but clearly a different colour from everything around it (an eye,
#     a face next to hair, a flower centre) is kept; only true specks and slivers must merge.
HARD = MIN * a.hard
def small(r): return allcnt[r] < MIN or 2 * allcnt[r] / max(perim(r), 1) < MINW / 2
def must(r): return allcnt[r] < HARD or 2 * allcnt[r] / max(perim(r), 1) < MINW / 4
def pick(r): return min(nb[r], key=lambda q: dE(r, q) - 4.0 * nb[r][q] / max(perim(r), 1))
heap = [(allcnt[r], r) for r in range(1, N) if find(r) == r and small(r)]
heapq.heapify(heap)
while heap:
    _, r = heapq.heappop(heap)
    if find(r) != r or not small(r) or not nb[r]: continue
    # closest colour, with a nudge toward pieces sharing more border (keeps shapes natural)
    best = pick(r)
    if not must(r) and dE(r, best) > a.distinct: continue
    keep, gone = (best, r) if allcnt[best] >= allcnt[r] else (r, best)
    merge(keep, gone)
    if small(keep): heapq.heappush(heap, (allcnt[keep], keep))

root = np.array([find(i) for i in range(N)]); root[0] = 0
_, lbl = np.unique(root[lbl], return_inverse=True); lbl = lbl.reshape(h, w).astype(np.int32) + 1
Rn = int(lbl.max())
if Rn > 65000: sys.exit('too many pieces')

# ---- 5. palette: k-means over the pieces' painted colours, numbered light -> dark
cnt, s1, _ = stats(lbl, paper)
cntall = np.bincount(lbl.ravel(), minlength=Rn + 1)
nopaper = cnt == 0
if nopaper.any():   # a piece made only of ink pixels: read its colour from all its pixels
    full = np.ones_like(paper); c2, t2, _ = stats(lbl, full); cnt[nopaper] = c2[nopaper]; s1[nopaper] = t2[nopaper]
means = (s1 / np.maximum(cnt, 1)[:, None])[1:].astype(np.float32)
K = min(a.colors, Rn)
# weight big pieces a little more so the main colours of the picture are exact
reps = np.clip(np.round(np.sqrt(cntall[1:] / MIN)), 1, 6).astype(int)
_, _, centers = cv2.kmeans(np.repeat(means, reps, 0), K, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 80, .2), 8, cv2.KMEANS_PP_CENTERS)
wl = np.array([.5, 1, 1], np.float32)
assign = np.argmin((((means[:, None, :] - centers[None]) * wl) ** 2).sum(2), 1)
used = np.unique(assign); centers = centers[used]; assign = np.searchsorted(used, assign); K = len(used)
order = np.argsort(-centers[:, 0]); rank = np.empty(K, int); rank[order] = np.arange(K)
rc = rank[assign]
pal = cv2.cvtColor(centers[order].reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
palette = [[int(c[2]), int(c[1]), int(c[0])] for c in pal]

# ---- 6. number positions (deepest point of each piece)
regions = []
for r in range(1, Rn + 1):
    ys, xs = np.nonzero(lbl == r); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    m = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8); m[ys - y0 + 1, xs - x0 + 1] = 1
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
    regions.append({'id': r, 'c': int(rc[r - 1]), 'a': int(len(ys)), 'x': int(x + x0 - 1), 'y': int(y + y0 - 1), 'r': round(float(dt.max()), 1)})

# ---- 7. outlines: trace the cracks between pixels of different pieces, chain them, smooth, simplify
hz = lbl[:-1, :] != lbl[1:, :]   # crack on grid row y+1 from (x,y+1) to (x+1,y+1)
vt = lbl[:, :-1] != lbl[:, 1:]   # crack on grid column x+1 from (x+1,y) to (x+1,y+1)
W1 = w + 1
yy, xx = np.nonzero(hz); e1 = np.stack([(yy + 1) * W1 + xx, (yy + 1) * W1 + xx + 1], 1)
yy, xx = np.nonzero(vt); e2 = np.stack([yy * W1 + xx + 1, (yy + 1) * W1 + xx + 1], 1)
E = np.concatenate([e1, e2]).astype(np.int64)
deg = np.bincount(E.ravel(), minlength=W1 * (h + 1))
adj = {}
for i, (p, q) in enumerate(E.tolist()):
    adj.setdefault(p, []).append(i); adj.setdefault(q, []).append(i)
usedE = np.zeros(len(E), bool)
def walk(start, ei):
    pts = [start]; cur = start
    while True:
        usedE[ei] = True
        p, q = E[ei]; cur = q if p == cur else p; pts.append(cur)
        if deg[cur] != 2 or cur == start: return pts
        nxt_ = [j for j in adj[cur] if not usedE[j]]
        if not nxt_: return pts
        ei = nxt_[0]
chains = []
for v in np.nonzero((deg > 0) & (deg != 2))[0].tolist():
    for ei in adj[v]:
        if not usedE[ei]: chains.append(walk(v, ei))
for ei in range(len(E)):
    if not usedE[ei]: chains.append(walk(int(E[ei][0]), ei))
def smooth(pts):
    P = np.array([(p % W1, p // W1) for p in pts], np.float64)
    closed = len(pts) > 3 and pts[0] == pts[-1]
    if len(P) > 4:
        sig = 1.6; rad = 4; kx = np.exp(-np.arange(-rad, rad + 1) ** 2 / (2 * sig * sig)); kx /= kx.sum()
        if closed:
            Q = P[:-1]; Qp = np.concatenate([Q[-rad:], Q, Q[:rad]])
            S = np.stack([np.convolve(Qp[:, i], kx, 'valid') for i in range(2)], 1); P = np.concatenate([S, S[:1]])
        else:
            Pp = np.concatenate([np.repeat(P[:1], rad, 0), P, np.repeat(P[-1:], rad, 0)])
            S = np.stack([np.convolve(Pp[:, i], kx, 'valid') for i in range(2)], 1)
            # pin the ends (junctions) and ease in, so chains still meet exactly
            t = np.minimum(np.arange(len(P)), np.arange(len(P))[::-1]); wgt = np.clip(t / rad, 0, 1)[:, None]
            P = P * (1 - wgt) + S * wgt
    ap_ = cv2.approxPolyDP(np.round(P * 4).astype(np.int32).reshape(-1, 1, 2), 1.2, False).reshape(-1, 2)
    return ap_
lines = []; npts = 0
for c in chains:
    if len(c) < 2: continue
    q = smooth(c); npts += len(q)
    d = np.concatenate([q[:1], np.diff(q, axis=0)]).ravel().tolist()   # delta-encoded, quarter pixels
    lines.append(d)

# ---- 8. write assets
os.makedirs(out, exist_ok=True)
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = lbl % 256; rgb[:, :, 1] = lbl // 256
cv2.imwrite(os.path.join(out, 'labels.png'), rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
if os.path.abspath(src) != os.path.abspath(out):   # copy the painting as-is (re-saving a JPEG loses quality)
    import shutil; shutil.copyfile(os.path.join(src, 'color.jpg'), os.path.join(out, 'color.jpg'))
def raster(scale, width, gray):
    S = 4  # draw big then shrink = smooth lines
    cw, ch = round(w * scale * S), round(h * scale * S)
    img = np.full((ch, cw), 255, np.uint8)
    pl = [ (np.cumsum(np.array(d).reshape(-1, 2), 0) * scale * S / 4).round().astype(np.int32) for d in lines ]
    cv2.polylines(img, pl, False, gray, max(1, round(width * S)), cv2.LINE_AA)
    return cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
cv2.imwrite(os.path.join(out, 'line.png'), raster(1, 1.4, 90), [cv2.IMWRITE_PNG_COMPRESSION, 9])
# gallery thumbnail and featured image: keep the artist's drawing (it shows what the picture is far better
# than the simplified outlines); only make one from the outlines when the page has none
import shutil
for f in ('thumb.jpg', 'feature.jpg'):
    s_, o_ = os.path.join(src, f), os.path.join(out, f)
    if os.path.exists(s_) and os.path.abspath(s_) != os.path.abspath(o_): shutil.copyfile(s_, o_)
if not os.path.exists(os.path.join(out, 'thumb.jpg')):
    ts = 420 / max(h, w)
    cv2.imwrite(os.path.join(out, 'thumb.jpg'), raster(ts, max(.9, 1.6 * ts), 70), [cv2.IMWRITE_JPEG_QUALITY, 85])
shade = a.shade if a.shade is not None else old.get('shade', 0.5)
meta = {'w': w, 'h': h, 'mode': 'pair', 'palette': palette, 'regions': regions, 'shade': shade, 'v': 2, 'lines': lines}
json.dump(meta, open(os.path.join(out, 'regions.json'), 'w'), separators=(',', ':'))
mf = os.path.join(R, 'public', 'pages.json')
if os.path.exists(mf):
    pages = json.load(open(mf))
    for p in pages:
        if p['slug'] == a.slug: p['regions'] = Rn; p['colors'] = len(palette)
    json.dump(pages, open(mf, 'w'), indent=1)
ar = [r['a'] for r in regions]
print(f"{a.slug}: {n0} ink pieces (+{nsplit} split) -> {Rn} pieces, {len(palette)} colours, min {min(ar)} px, "
      f"median {int(np.median(ar))}, {len(lines)} outline chains / {npts} pts, "
      f"json {os.path.getsize(os.path.join(out, 'regions.json')) // 1024} KB, {time.time() - t0:.0f}s")
