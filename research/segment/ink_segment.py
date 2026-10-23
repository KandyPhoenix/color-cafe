"""Ink-outline color-by-number: regions are the areas enclosed by the drawing's own ink lines.
The blank page shows the real ink; tapping a region reveals the original shaded pixels inside it."""
import sys, json, time, numpy as np, cv2
src, out = sys.argv[1], sys.argv[2]
INK = int(sys.argv[3]) if len(sys.argv) > 3 else 70      # luminance below this = ink
MIN = int(sys.argv[4]) if len(sys.argv) > 4 else 600      # regions smaller than this merge into a neighbour
N = int(sys.argv[5]) if len(sys.argv) > 5 else 24
t0 = time.time()
img = cv2.imread(src); h, w = img.shape[:2]
lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
L = lab[:, :, 0]
# ink mask: pixels that are dark relative to their surroundings (black-hat) AND thin (line-like)
bh = cv2.morphologyEx(L, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)))
cand = ((bh > 28) | (L < INK)).astype(np.uint8)
dt = cv2.distanceTransform(cand, cv2.DIST_L2, 5)
thin = (dt <= 5.5).astype(np.uint8)            # strokes up to ~11 px wide count as ink
# keep whole thin strokes: reconstruct candidate components that are mostly thin
nc, cl = cv2.connectedComponents(cand, connectivity=8)
frac = np.bincount(cl.ravel(), weights=thin.ravel(), minlength=nc) / np.maximum(np.bincount(cl.ravel(), minlength=nc), 1)
keep = frac > 0.6; keep[0] = False
ink = keep[cl].astype(np.uint8)
ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
# regions = connected components of non-ink
n, labels = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4)
labels = labels.astype(np.int32)
areas = np.bincount(labels.ravel(), minlength=n)
# merge small regions into the neighbour they share the longest border with (through the ink)
small = [r for r in range(1, n) if 0 < areas[r] < MIN]
for r in small:
    m = (labels == r).astype(np.uint8)
    ring = cv2.dilate(m, np.ones((7, 7), np.uint8)) - m
    nb = labels[ring > 0]; nb = nb[(nb != r) & (nb > 0)]
    if nb.size: labels[m > 0] = np.bincount(nb).argmax()
# split big un-inked regions by colour (sky/hills/clouds with no ink between them)
MAXF = 0.04
sm = cv2.pyrMeanShiftFiltering(cv2.bilateralFilter(img, 9, 50, 9), 10, 20)
for _ in range(2):
    R0 = labels.max(); areas = np.bincount(labels.ravel(), minlength=R0 + 1)
    big = [r for r in range(1, R0 + 1) if areas[r] > MAXF * h * w]
    if not big: break
    for r in big:
        m = labels == r; ys, xs = np.where(m); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        gs = cv2.ximgproc.segmentation.createGraphSegmentation(sigma=0.8, k=1200, min_size=int(MIN * 4))
        sub = gs.processImage(sm[y0:y1, x0:x1]).astype(np.int32) + 1
        subm = m[y0:y1, x0:x1]
        # smooth sub-boundaries (majority vote) so they are not squiggly
        best = np.zeros(sub.shape, np.float32); out_s = sub.copy()
        for v in np.unique(sub[subm]):
            b = cv2.GaussianBlur((sub == v).astype(np.float32), (0, 0), 6); win = b > best; best[win] = b[win]; out_s[win] = v
        labels[y0:y1, x0:x1][subm] = R0 + out_s[subm]
    _, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
    # keep ink at 0
    labels[ink > 0] = 0
    # tiny leftovers merge
    R0 = labels.max(); areas = np.bincount(labels.ravel(), minlength=R0 + 1)
    for r in [r for r in range(1, R0 + 1) if 0 < areas[r] < MIN]:
        m = (labels == r).astype(np.uint8); ring = cv2.dilate(m, np.ones((7, 7), np.uint8)) - m; nb = labels[ring > 0]; nb = nb[(nb != r) & (nb > 0)]
        if nb.size: labels[m > 0] = np.bincount(nb).argmax()
# relabel densely
_, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
# ink pixels get label 0; assign them to nearest region for hit-testing/reveal
R = labels.max()
# palette: dominant colour per region (median Lab of non-ink pixels), k-means to N
flat = labels.ravel(); labf = lab.reshape(-1, 3).astype(np.float32)
cnt = np.bincount(flat, minlength=R + 1).astype(np.float64)
means = np.stack([np.bincount(flat, weights=labf[:, c], minlength=R + 1) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
_, assign, centers = cv2.kmeans(means[1:].astype(np.float32), N, None, crit, 5, cv2.KMEANS_PP_CENTERS)
rc = np.concatenate([[0], assign.ravel()])
pal_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
# page: white with the real ink lines, numbers in each region
page = np.full((h, w, 3), 255, np.uint8)
bnd = np.zeros((h, w), np.uint8); bnd[:, :-1] |= ((labels[:, :-1] != labels[:, 1:]) & (labels[:, :-1] > 0) & (labels[:, 1:] > 0)); bnd[:-1, :] |= ((labels[:-1, :] != labels[1:, :]) & (labels[:-1, :] > 0) & (labels[1:, :] > 0))
page[cv2.dilate(bnd, np.ones((2, 2), np.uint8)) > 0] = (150, 150, 150)
page[ink > 0] = (40, 40, 40)
font = cv2.FONT_HERSHEY_SIMPLEX; scale = 0.5; regions = []; placed = 0
for r in range(1, R + 1):
    m = (labels == r).astype(np.uint8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape); rad = float(dt.max())
    regions.append({'id': r, 'c': int(rc[r]), 'area': int(m.sum()), 'x': int(x), 'y': int(y), 'r': round(rad, 1)})
    txt = str(int(rc[r]) + 1); (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) <= rad * 2.0:
        cv2.putText(page, txt, (int(x - tw / 2), int(y + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA); placed += 1
cv2.imwrite(f'{out}_page.png', page)
show = np.random.default_rng(1).random(R + 1) < 0.5; show[0] = True
half = np.where(show[labels][..., None], img, page); half[ink > 0] = img[ink > 0]; cv2.imwrite(f'{out}_half.jpg', half, [cv2.IMWRITE_JPEG_QUALITY, 88])
json.dump({'n': N, 'w': w, 'h': h, 'palette': [[int(v) for v in c[::-1]] for c in pal_bgr], 'regions': regions}, open(f'{out}_regions.json', 'w'))
ar = [r['area'] for r in regions]
print(f'{out}: regions {R}, numbered {placed}, min {min(ar)}, median {int(np.median(ar))}, largest {max(ar)/(h*w)*100:.1f}%, ink {ink.mean()*100:.1f}% of pixels, {time.time()-t0:.0f}s')
