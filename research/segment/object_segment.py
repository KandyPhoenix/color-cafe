"""Object-style color-by-number: regions follow object boundaries (graph segmentation on a smoothed
image), each region is numbered by its dominant palette colour, and a tap reveals all pixels inside."""
import sys, json, time, numpy as np, cv2
src, out = sys.argv[1], sys.argv[2]
K = float(sys.argv[3]) if len(sys.argv) > 3 else 900      # graph-seg merge strength (bigger = bigger regions)
MIN = int(sys.argv[4]) if len(sys.argv) > 4 else 4000      # min region px
N = int(sys.argv[5]) if len(sys.argv) > 5 else 24
t0 = time.time()
img = cv2.imread(src); h, w = img.shape[:2]
sm = img
for _ in range(3): sm = cv2.bilateralFilter(sm, 9, 60, 9)
sm = cv2.pyrMeanShiftFiltering(sm, 12, 24)
# lift the darks so low-contrast shadow areas separate like the bright ones (segmentation only)
lut = np.array([255 * (i / 255) ** 0.55 for i in range(256)], np.uint8)
seg_in = cv2.LUT(sm, lut)
gs = cv2.ximgproc.segmentation.createGraphSegmentation(sigma=0.8, k=K, min_size=MIN)
labels = gs.processImage(seg_in).astype(np.int32) + 1
# split any region larger than MAXF of the image along its own texture edges (watershed on the lifted image)
MAXF = 0.03
for _ in range(2):
    R = labels.max(); areas = np.bincount(labels.ravel(), minlength=R + 1)
    big = [r for r in range(1, R + 1) if areas[r] > MAXF * h * w]
    if not big: break
    for r in big:
        m = (labels == r).astype(np.uint8)
        g = cv2.cvtColor(seg_in, cv2.COLOR_BGR2GRAY); g = cv2.GaussianBlur(g, (0, 0), 3)
        n = max(2, int(areas[r] / (MAXF * h * w) * 2))
        ys, xs = np.where(m > 0); pts = np.random.default_rng(r).choice(len(ys), n, replace=False)
        markers = np.zeros((h, w), np.int32)
        for i, p in enumerate(pts): cv2.circle(markers, (int(xs[p]), int(ys[p])), 4, i + 1, -1)
        ws = cv2.watershed(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR), markers.copy())
        ws[m == 0] = 0; ws[ws < 1] = 0
        # watershed lines (-1) inside the region: give to nearest marker label via dilation
        for _k in range(3):
            d = cv2.dilate(ws.astype(np.float32), np.ones((3, 3), np.uint8)); ws = np.where((ws == 0) & (m > 0), d.astype(np.int32), ws)
        labels[m > 0] = R + ws[m > 0]; R = labels.max()
_, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
if labels.min() == 0: labels += 1
R = labels.max()
# palette from region means (dominant colour per region), k-means in Lab
lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
flat = labels.ravel()
sums = np.zeros((R + 1, 3), np.float64); cnt = np.bincount(flat, minlength=R + 1).astype(np.float64)
for c in range(3): sums[:, c] = np.bincount(flat, weights=lab[:, c], minlength=R + 1)
means = (sums[1:] / np.maximum(cnt[1:], 1)[:, None]).astype(np.float32)
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
_, assign, centers = cv2.kmeans(means, N, None, crit, 5, cv2.KMEANS_PP_CENTERS)
reg_col = np.concatenate([[0], assign.ravel()])
pal_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
# merge touching regions with the same palette colour (keeps object parts whole)
# union-find over adjacent label pairs
right = np.stack([labels[:, :-1].ravel(), labels[:, 1:].ravel()], 1); down = np.stack([labels[:-1, :].ravel(), labels[1:, :].ravel()], 1)
pairs = np.concatenate([right, down]); pairs = pairs[pairs[:, 0] != pairs[:, 1]]
pairs = pairs[reg_col[pairs[:, 0]] == reg_col[pairs[:, 1]]]
parent = np.arange(R + 1)
def find(a):
    while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
    return a
for a, b in np.unique(pairs, axis=0):
    ra, rb = find(a), find(b)
    if ra != rb: parent[max(ra, rb)] = min(ra, rb)
root = np.array([find(i) for i in range(R + 1)])
_, labels2 = np.unique(root[labels], return_inverse=True); labels2 = labels2.reshape(h, w).astype(np.int32)
R2 = labels2.max()
reg_col2 = np.zeros(R2 + 1, np.int32)
for r in range(1, R2 + 1):
    old = labels[labels2 == r][0]; reg_col2[r] = reg_col[old]
# render outline page with uniform numbers, and a half-revealed preview
page = np.full((h, w, 3), 255, np.uint8); regions = []
font = cv2.FONT_HERSHEY_SIMPLEX; scale = 0.55
for r in range(1, R2 + 1):
    m = (labels2 == r).astype(np.uint8)
    cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(page, cs, -1, (120, 120, 120), 2, cv2.LINE_AA)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape); rad = float(dt.max())
    regions.append({'id': r, 'c': int(reg_col2[r]), 'area': int(m.sum()), 'x': int(x), 'y': int(y), 'r': round(rad, 1)})
for reg in regions:
    txt = str(reg['c'] + 1); (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) > reg['r'] * 2.0: continue
    cv2.putText(page, txt, (int(reg['x'] - tw / 2), int(reg['y'] + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA)
cv2.imwrite(f'{out}_page.png', page)
rng = np.random.default_rng(1); show = rng.random(R2 + 1) < 0.5
half = np.where(show[labels2][..., None], img, page); cv2.imwrite(f'{out}_half.jpg', half, [cv2.IMWRITE_JPEG_QUALITY, 88])
# "tap one colour" preview: reveal every region of the most common purple-ish palette slot? -> reveal all regions of colour index c_demo (largest-area colour)
areas_by_col = np.bincount(reg_col2[1:], weights=[r['area'] for r in regions], minlength=N)
json.dump({'n': N, 'w': w, 'h': h, 'palette': [[int(v) for v in c[::-1]] for c in pal_bgr], 'regions': regions}, open(f'{out}_regions.json', 'w'))
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = labels2 % 256; rgb[:, :, 1] = labels2 // 256; cv2.imwrite(f'{out}_labels_rgb.png', rgb)
areas = [r['area'] for r in regions]
print(f'{out}: graph regions {R}, after same-colour merge {R2}, min area {min(areas)}, median {int(np.median(areas))}, largest {max(areas)/(h*w)*100:.1f}%, {time.time()-t0:.1f}s')
