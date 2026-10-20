"""Re-render a numbered page from a saved label map + regions.json with uniform small numbers."""
import sys, json, numpy as np, cv2
base = sys.argv[1]; scale = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
lab = cv2.imread(f'out/{base}_labels_rgb.png', cv2.IMREAD_UNCHANGED)
labels = lab[:, :, 2].astype(np.int32) + 256 * lab[:, :, 1].astype(np.int32)   # id = R + 256*G (cv2 is BGR)
d = json.load(open(f'out/{base}_regions.json'))
h, w = labels.shape
page = np.full((h, w, 3), 255, np.uint8)
b = np.zeros(labels.shape, np.uint8)
b[:, :-1] |= (labels[:, :-1] != labels[:, 1:]); b[:-1, :] |= (labels[:-1, :] != labels[1:, :])
page[b > 0] = (120, 120, 120)
font = cv2.FONT_HERSHEY_SIMPLEX
placed = skipped = 0
for r in d['regions']:
    txt = str(r['c'] + 1)
    (tw, th), _ = cv2.getTextSize(txt, font, scale, 1)
    if max(tw, th) > r['r'] * 2.0:
        skipped += 1; continue           # region too small for a number at this size; app shows it on zoom/tap
    cv2.putText(page, txt, (int(r['x'] - tw / 2), int(r['y'] + th / 2)), font, scale, (30, 30, 30), 1, cv2.LINE_AA)
    placed += 1
cv2.imwrite(f'out/{base}_page_uniform.png', page)
print(base, 'scale', scale, 'placed', placed, 'skipped', skipped, 'of', len(d['regions']))
