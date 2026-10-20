"""Object-shaped color-by-number v2: graph segmentation on a lifted/CLAHE image, recursive refinement of
oversized regions, same-colour merge, boundary smoothing, uniform numbers, zoomed quadrant previews."""
import sys, json, time, numpy as np, cv2
src, out = sys.argv[1], sys.argv[2]
K = float(sys.argv[3]) if len(sys.argv) > 3 else 500; MIN = int(sys.argv[4]) if len(sys.argv) > 4 else 3000
N = int(sys.argv[5]) if len(sys.argv) > 5 else 24; MAXF = 0.025; SIG = 5.0
t0 = time.time()
img = cv2.imread(src); h, w = img.shape[:2]
sm = img
for _ in range(3): sm = cv2.bilateralFilter(sm, 9, 60, 9)
sm = cv2.pyrMeanShiftFiltering(sm, 12, 24)
lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB)
clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(16, 16))
lab2 = lab.copy(); lab2[:, :, 0] = clahe.apply(lab[:, :, 0])
seg_in = cv2.cvtColor(lab2, cv2.COLOR_LAB2BGR)
lut = np.array([255 * (i / 255) ** 0.6 for i in range(256)], np.uint8); seg_in = cv2.LUT(seg_in, lut)

def graphseg(im, k, mn):
    gs = cv2.ximgproc.segmentation.createGraphSegmentation(sigma=0.8, k=k, min_size=mn)
    return gs.processImage(im).astype(np.int32) + 1

labels = graphseg(seg_in, K, MIN)
# recursive refinement of oversized regions with a finer, more contrasty pass
for level in range(3):
    R = labels.max(); areas = np.bincount(labels.ravel(), minlength=R + 1)
    big = [r for r in range(1, R + 1) if areas[r] > MAXF * h * w]
    if not big: break
    for r in big:
        m = labels == r; ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = seg_in[y0:y1, x0:x1].copy()
        cl = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB); cl[:, :, 0] = cv2.createCLAHE(4.0, (8, 8)).apply(cl[:, :, 0])
        crop = cv2.cvtColor(cl, cv2.COLOR_LAB2BGR)
        sub = graphseg(crop, K / (3 ** (level + 1)), max(MIN // 2, 800))
        subm = m[y0:y1, x0:x1]
        labels[y0:y1, x0:x1][subm] = R + sub[subm]; R = labels.max()
    _, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32) + 1
R = labels.max()
# palette by region mean colour (dominant colour), k-means in Lab
flat = labels.ravel(); L = lab.reshape(-1, 3).astype(np.float32)
cnt = np.bincount(flat, minlength=R + 1).astype(np.float64)
means = np.stack([np.bincount(flat, weights=L[:, c], minlength=R + 1) for c in range(3)], 1)[1:] / np.maximum(cnt[1:], 1)[:, None]
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
_, assign, centers = cv2.kmeans(means.astype(np.float32), N, None, crit, 5, cv2.KMEANS_PP_CENTERS)
reg_col = np.concatenate([[0], assign.ravel()])
pal_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
# merge touching regions of the same palette colour, but never into something oversized
def merge_same_colour(labels, reg_col):
    R = labels.max(); areas = np.bincount(labels.ravel(), minlength=R + 1)
    right = np.stack([labels[:, :-1].ravel(), labels[:, 1:].ravel()], 1); down = np.stack([labels[:-1, :].ravel(), labels[1:, :].ravel()], 1)
    pairs = np.concatenate([right, down]); pairs = pairs[pairs[:, 0] != pairs[:, 1]]
    pairs = pairs[reg_col[pairs[:, 0]] == reg_col[pairs[:, 1]]]
    parent = np.arange(R + 1); size = areas.copy()
    def find(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for a, b in np.unique(pairs, axis=0):
        ra, rb = find(a), find(b)
        if ra != rb and size[ra] + size[rb] <= MAXF * h * w * 1.5:
            parent[max(ra, rb)] = min(ra, rb); size[min(ra, rb)] += size[max(ra, rb)]
    root = np.array([find(i) for i in range(R + 1)])
    _, l2 = np.unique(root[labels], return_inverse=True); l2 = l2.reshape(h, w).astype(np.int32) + 1
    rc = np.zeros(l2.max() + 1, np.int32)
    for r in range(1, l2.max() + 1): rc[r] = reg_col[labels[l2 == r][0]]
    return l2, rc
labels, reg_col = merge_same_colour(labels, reg_col)
# boundary smoothing: majority vote under a Gaussian
R = labels.max(); best = np.zeros((h, w), np.float32); out_l = np.zeros((h, w), np.int32); k = int(SIG * 6) | 1
for r in range(1, R + 1):
    m = labels == r
    if not m.any(): continue
    ys, xs = np.where(m); y0, y1 = max(ys.min() - k, 0), min(ys.max() + k + 1, h); x0, x1 = max(xs.min() - k, 0), min(xs.max() + k + 1, w)
    b = cv2.GaussianBlur(m[y0:y1, x0:x1].astype(np.float32), (k, k), SIG); sub = best[y0:y1, x0:x1]; win = b > sub
    sub[win] = b[win]; out_l[y0:y1, x0:x1][win] = r
labels = out_l
# absorb slivers (< 900 px) into their biggest neighbour
areas = np.bincount(labels.ravel(), minlength=R + 1)
for r in [r for r in range(1, R + 1) if 0 < areas[r] < 900]:
    m = (labels == r).astype(np.uint8); ring = cv2.dilate(m, np.ones((3, 3), np.uint8)) - m; nb = labels[ring > 0]; nb = nb[(nb != r) & (nb > 0)]
    if nb.size: labels[m > 0] = np.bincount(nb).argmax()
_, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
if labels.min() == 0: labels += 1
R = labels.max(); rc = np.zeros(R + 1, np.int32)
# recompute colour per region from its mean (after merges)
flat = labels.ravel(); cnt = np.bincount(flat, minlength=R + 1).astype(np.float64)
means = np.stack([np.bincount(flat, weights=L[:, c], minlength=R + 1) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
for r in range(1, R + 1): rc[r] = int(np.argmin(((centers - means[r]) ** 2).sum(1)))
# render
page = np.full((h, w, 3), 255, np.uint8); regions = []; font = cv2.FONT_HERSHEY_SIMPLEX; scale = 0.55
for r in range(1, R + 1):
    m = (labels == r).astype(np.uint8); cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(page, cs, -1, (120, 120, 120), 2, cv2.LINE_AA)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
    regions.append({'id': r, 'c': int(rc[r]), 'area': int(m.sum()), 'x': int(x), 'y': int(y), 'r': round(float(dt.max()), 1)})
placed = 0
for reg in regions:
    txt = str(reg['c'] + 1); (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) > reg['r'] * 2.0: continue
    cv2.putText(page, txt, (int(reg['x'] - tw / 2), int(reg['y'] + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA); placed += 1
cv2.imwrite(f'{out}_page.png', page)
show = np.random.default_rng(1).random(R + 1) < 0.5
half = np.where(show[labels][..., None], img, page); cv2.imwrite(f'{out}_half.jpg', half, [cv2.IMWRITE_JPEG_QUALITY, 88])
json.dump({'n': N, 'w': w, 'h': h, 'palette': [[int(v) for v in c[::-1]] for c in pal_bgr], 'regions': regions}, open(f'{out}_regions.json', 'w'))
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = labels % 256; rgb[:, :, 1] = labels // 256; cv2.imwrite(f'{out}_labels_rgb.png', rgb)
# zoomed quadrants of the page for review
for i, (qy, qx) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
    cv2.imwrite(f'{out}_q{i+1}.jpg', page[qy * h // 2:(qy + 1) * h // 2, qx * w // 2:(qx + 1) * w // 2], [cv2.IMWRITE_JPEG_QUALITY, 85])
areas = [r['area'] for r in regions]
print(f'{out}: regions {R}, numbered {placed}, min {min(areas)}, median {int(np.median(areas))}, largest {max(areas)/(h*w)*100:.1f}%, {time.time()-t0:.0f}s')
