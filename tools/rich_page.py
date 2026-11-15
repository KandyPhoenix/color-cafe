#!/usr/bin/env python3
"""Put a rich repaint on a shapes-first page, keeping its pieces.

  python3 tools/rich_page.py <slug> <rich.png> [--style "Kodachrome"]

For a page built by flat_page.py. <rich.png> is the same picture repainted rich and shaded with every shape
kept in place. It is aligned to the flat picture (a small shift/scale), then becomes what a tap reveals
(color.jpg) and the finished half of feature.jpg. The pieces and outlines do not change, so saved progress
is kept. Prints how well the painting's edges sit on the piece outlines; below about 60% the repaint has
moved things and should be redone. Needs opencv, numpy.
"""
import sys, os, json, argparse, glob, shutil
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slug'); ap.add_argument('rich'); ap.add_argument('--style', default='Kodachrome')
a = ap.parse_args()
d = os.path.join(R, 'public', 'pages', a.slug); L = cv2.imread(os.path.join(d, 'labels.png'))
src = sorted(glob.glob(os.path.join(R, 'pages', 'src', a.slug + '-flat.*'))); rich0 = cv2.imread(a.rich)
if L is None or not src or rich0 is None: sys.exit('need public/pages/<slug>/labels.png, pages/src/<slug>-flat.* and the rich picture')
lbl = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32); h, w = lbl.shape
rich = cv2.resize(rich0, (w, h), interpolation=cv2.INTER_AREA); flat = cv2.resize(cv2.imread(src[0]), (w, h), interpolation=cv2.INTER_AREA)
def edges(im): return cv2.GaussianBlur(cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY), (0, 0), 2), 40, 120).astype(np.float32), (0, 0), 4)
al = rich
try:
    cc, warp = cv2.findTransformECC(edges(flat), edges(rich), np.eye(2, 3, dtype=np.float32), cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), None, 5)
    if abs(warp[0, 0] - 1) < .05 and abs(warp[1, 1] - 1) < .05 and abs(warp[0, 2]) < .04 * w and abs(warp[1, 2]) < .04 * h:
        al = cv2.warpAffine(rich, warp, (w, h), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    print(f'aligned: shift {warp[0,2]:.1f}, {warp[1,2]:.1f} px')
except cv2.error:
    print('could not align; using the painting as it is')
e = np.zeros((h, w), np.uint8); e[:, 1:] |= (lbl[:, 1:] != lbl[:, :-1]).astype(np.uint8); e[1:, :] |= (lbl[1:, :] != lbl[:-1, :]).astype(np.uint8)
ce = cv2.Canny(cv2.GaussianBlur(cv2.cvtColor(al, cv2.COLOR_BGR2GRAY), (0, 0), 1.5), 60, 160) > 0
fit = 100 * ((cv2.dilate(ce.astype(np.uint8), np.ones((9, 9), np.uint8)) > 0) & (e > 0)).sum() / max(1, (e > 0).sum())
cv2.imwrite(os.path.join(d, 'color.jpg'), al, [cv2.IMWRITE_JPEG_QUALITY, 92])
os.makedirs(os.path.join(R, 'pages', 'rich'), exist_ok=True); cv2.imwrite(os.path.join(R, 'pages', 'rich', a.slug + '.jpg'), al, [cv2.IMWRITE_JPEG_QUALITY, 92])   # kept for shade_page.py --mix
shutil.copy(a.rich, os.path.join(R, 'pages', 'src', a.slug + '-color' + os.path.splitext(a.rich)[1]))
line = cv2.imread(os.path.join(d, 'line.png'), cv2.IMREAD_GRAYSCALE); blank = cv2.cvtColor(cv2.erode(line, np.ones((2, 2), np.uint8)), cv2.COLOR_GRAY2BGR)
yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); t = np.clip(((xx - 0.60 * w) + (yy - 0.5 * h) * 0.35) / (0.06 * w) + 0.5, 0, 1)[..., None]
cv2.imwrite(os.path.join(d, 'feature.jpg'), cv2.resize((al * (1 - t) + blank * t).astype(np.uint8), (900, round(900 * h / w)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 86])
pj = os.path.join(R, 'public', 'pages.json'); P = json.load(open(pj, encoding='utf-8'))
for x in P:
    if x['slug'] == a.slug: x['style'] = a.style
json.dump(P, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'{a.slug}: rich painting installed; {fit:.0f}% of piece outlines have a painted edge within 4 px' + ('' if fit >= 60 else '  <-- LOW: the repaint moved things'))
