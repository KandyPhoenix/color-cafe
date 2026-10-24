"""Two-step page: regions come from the LINE ART; colour comes from the painted version of the same drawing.
The painting may be a slightly different size / slightly misaligned, so it is resized and aligned first."""
import sys, json, time, numpy as np, cv2
line_p, col_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
INK = int(sys.argv[4]) if len(sys.argv) > 4 else 110; MIN = int(sys.argv[5]) if len(sys.argv) > 5 else 250; N = int(sys.argv[6]) if len(sys.argv) > 6 else 36
t0 = time.time()
line = cv2.imread(line_p); col = cv2.imread(col_p)
h, w = line.shape[:2]; col = cv2.resize(col, (w, h), interpolation=cv2.INTER_LANCZOS4)
# align: ECC on edge maps (translation + scale), handles ChatGPT's slight reframing
g1 = cv2.GaussianBlur(cv2.cvtColor(line, cv2.COLOR_BGR2GRAY), (0, 0), 2)
g2 = cv2.GaussianBlur(cv2.cvtColor(col, cv2.COLOR_BGR2GRAY), (0, 0), 2)
e1 = cv2.Canny(g1, 50, 150).astype(np.float32); e2 = cv2.Canny(g2, 50, 150).astype(np.float32)
e1 = cv2.GaussianBlur(e1, (0, 0), 4); e2 = cv2.GaussianBlur(e2, (0, 0), 4)
warp = np.eye(2, 3, dtype=np.float32)
try:
    cc, warp = cv2.findTransformECC(e1, e2, warp, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-5), None, 5)
    col = cv2.warpAffine(col, warp, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    print('aligned, ecc', round(float(cc), 3), 'warp', np.round(warp, 3).tolist())
except cv2.error as e:
    print('alignment failed, using unaligned', str(e)[:80])
# ink from the line art
L = cv2.cvtColor(line, cv2.COLOR_BGR2GRAY)
ink = (L < INK).astype(np.uint8)
ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
n, labels = cv2.connectedComponents((1 - ink).astype(np.uint8), connectivity=4); labels = labels.astype(np.int32)
areas = np.bincount(labels.ravel(), minlength=n)
for r in [r for r in range(1, n) if 0 < areas[r] < MIN]:
    m = (labels == r).astype(np.uint8); ring = cv2.dilate(m, np.ones((7, 7), np.uint8)) - m; nb = labels[ring > 0]; nb = nb[(nb != r) & (nb > 0)]
    if nb.size: labels[m > 0] = np.bincount(nb).argmax()
_, labels = np.unique(labels, return_inverse=True); labels = labels.reshape(h, w).astype(np.int32)
R = labels.max()
# dominant colour per region from the painting (median in Lab, ignoring ink pixels)
lab = cv2.cvtColor(col, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32); flat = labels.ravel()
cnt = np.bincount(flat, minlength=R + 1).astype(np.float64)
means = np.stack([np.bincount(flat, weights=lab[:, c], minlength=R + 1) for c in range(3)], 1) / np.maximum(cnt, 1)[:, None]
crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
_, assign, centers = cv2.kmeans(means[1:].astype(np.float32), N, None, crit, 5, cv2.KMEANS_PP_CENTERS)
rc = np.concatenate([[0], assign.ravel()]); pal_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_LAB2BGR)[0]
# page = the real line art, with numbers
page = line.copy(); font = cv2.FONT_HERSHEY_SIMPLEX; scale = 0.45; regions = []; placed = 0
for r in range(1, R + 1):
    m = (labels == r).astype(np.uint8); dt = cv2.distanceTransform(m, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape); rad = float(dt.max())
    regions.append({'id': r, 'c': int(rc[r]), 'area': int(m.sum()), 'x': int(x), 'y': int(y), 'r': round(rad, 1)})
    txt = str(int(rc[r]) + 1); (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) <= rad * 1.9: cv2.putText(page, txt, (int(x - tw / 2), int(y + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA); placed += 1
cv2.imwrite(f'{out}_page.png', page)
# reveal: painted pixels inside revealed regions, line art ink kept on top (multiply)
show = np.random.default_rng(1).random(R + 1) < 0.5; show[0] = False
half = np.where(show[labels][..., None], col, page); half[ink > 0] = np.minimum(half[ink > 0], line[ink > 0])
cv2.imwrite(f'{out}_half.jpg', half, [cv2.IMWRITE_JPEG_QUALITY, 90])
full = col.copy(); full[ink > 0] = np.minimum(full[ink > 0], line[ink > 0]); cv2.imwrite(f'{out}_full.jpg', full, [cv2.IMWRITE_JPEG_QUALITY, 90])
json.dump({'n': N, 'w': w, 'h': h, 'palette': [[int(v) for v in c[::-1]] for c in pal_bgr], 'regions': regions}, open(f'{out}_regions.json', 'w'))
rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = labels % 256; rgb[:, :, 1] = labels // 256; cv2.imwrite(f'{out}_labels_rgb.png', rgb)
ar = [r['area'] for r in regions]
print(f'{out}: regions {R}, numbered {placed}, min {min(ar)}, median {int(np.median(ar))}, largest {max(ar)/(h*w)*100:.1f}%, {time.time()-t0:.0f}s')
