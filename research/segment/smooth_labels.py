"""Smooth region boundaries of a saved label map (majority vote under a Gaussian), re-merge
anything that became too small, then render a page with anti-aliased outlines and uniform numbers."""
import sys, json, time, numpy as np, cv2
base, sigma = sys.argv[1], float(sys.argv[2]); scale = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
t0 = time.time()
lab = cv2.imread(f'out/{base}_labels_rgb.png', cv2.IMREAD_UNCHANGED)
labels = lab[:, :, 2].astype(np.int32) + 256 * lab[:, :, 1].astype(np.int32)
d = json.load(open(f'out/{base}_regions.json'))
h, w = labels.shape; R = labels.max()
# majority-vote smoothing: label with the highest blurred membership wins
best = np.zeros((h, w), np.float32); out = np.zeros((h, w), np.int32)
k = int(sigma * 6) | 1
for r in range(1, R + 1):
    m = (labels == r)
    if not m.any(): continue
    ys, xs = np.where(m); y0, y1 = max(ys.min() - k, 0), min(ys.max() + k + 1, h); x0, x1 = max(xs.min() - k, 0), min(xs.max() + k + 1, w)
    b = cv2.GaussianBlur(m[y0:y1, x0:x1].astype(np.float32), (k, k), sigma)
    sub = best[y0:y1, x0:x1]; win = b > sub
    sub[win] = b[win]; out[y0:y1, x0:x1][win] = r
# any region that vanished or shrank below ~900px: give its pixels to the neighbour majority (rare)
areas = np.bincount(out.ravel(), minlength=R + 1)
lost = [r for r in range(1, R + 1) if 0 < areas[r] < 900]
for r in lost:
    m = (out == r).astype(np.uint8); ring = cv2.dilate(m, np.ones((3, 3), np.uint8)) - m
    nb = out[ring > 0]; nb = nb[nb != r]
    if nb.size: out[m > 0] = np.bincount(nb).argmax()
areas = np.bincount(out.ravel(), minlength=R + 1)
# render
page = np.full((h, w, 3), 255, np.uint8)
for r in range(1, R + 1):
    if areas[r] == 0: continue
    m = (out == r).astype(np.uint8)
    cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(page, cs, -1, (120, 120, 120), 2, cv2.LINE_AA)
font = cv2.FONT_HERSHEY_SIMPLEX; placed = 0
dist = None
for reg in d['regions']:
    r = reg['id']
    if areas[r] == 0: continue
    m = (out == r).astype(np.uint8)
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape); rad = dt.max()
    txt = str(reg['c'] + 1); (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) > rad * 2.0: continue
    cv2.putText(page, txt, (int(x - tw / 2), int(y + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA); placed += 1
cv2.imwrite(f'out/{base}_page_smooth{int(sigma)}.png', page)
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = out % 256; rgb[:, :, 1] = out // 256
cv2.imwrite(f'out/{base}_labels_smooth{int(sigma)}.png', rgb)
print(base, 'sigma', sigma, 'regions', int((areas > 0).sum() - 1), 'numbers', placed, 'lost-merged', len(lost), f'{time.time()-t0:.1f}s')
