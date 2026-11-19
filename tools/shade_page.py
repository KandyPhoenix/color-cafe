#!/usr/bin/env python3
"""Paint depth into a flat-colour page: what a tap reveals becomes shaded and rich instead of flat.

  python3 tools/shade_page.py <slug> [<slug> ...] [--depth 1.0] [--rich 1.0] [--mix 0.35]

For a page built by flat_page.py from flat art only. Reads the pieces (labels.png) and the flat picture
(pages/src/<slug>-flat.*) and writes a new public/pages/<slug>/color.jpg in which every piece has:
  * a light side and a shadow side (light from the upper left), so shapes look rounded, not cut out
  * a soft darker rim just inside its outline and a gentle glow toward its middle
  * deeper, more saturated colour, and a fine paper grain
Big background pieces (sky, walls, water) get a slow top-to-bottom gradient instead of a round shade.
The pieces do not change, so saved progress is kept. Also redraws feature.jpg. Needs opencv, numpy.
"""
import sys, os, json, argparse, glob
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+')
ap.add_argument('--depth', type=float, default=1.0, help='strength of the light and shadow')
ap.add_argument('--rich', type=float, default=1.0, help='strength of the colour deepening')
ap.add_argument('--mix', type=float, default=0.0, help='0-1: how much of the real repaint (pages/rich/<slug>.jpg, saved by rich_page.py) to blend into the shading')
ap.add_argument('--palette', action='store_true', help="fill every piece with its number's own colour (shaded), so a number never paints anything but its colour")
a = ap.parse_args()
for slug in a.slugs:
    d = os.path.join(R, 'public', 'pages', slug)
    L = cv2.imread(os.path.join(d, 'labels.png')); src = sorted(glob.glob(os.path.join(R, 'pages', 'src', slug + '-flat.*')))
    if L is None or not src: print('skip', slug, '(needs labels.png and pages/src/<slug>-flat.*)'); continue
    lbl = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32); h, w = lbl.shape; n = int(lbl.max()) + 1; fl = lbl.ravel()
    flat = cv2.resize(cv2.imread(src[0]), (w, h), interpolation=cv2.INTER_AREA)
    # each piece's own flat colour (median-ish: mean of the pixels away from its edges)
    e = np.zeros((h, w), np.uint8); e[:, 1:] |= (lbl[:, 1:] != lbl[:, :-1]).astype(np.uint8); e[1:, :] |= (lbl[1:, :] != lbl[:-1, :]).astype(np.uint8)
    e[0, :] = e[-1, :] = 1; e[:, 0] = e[:, -1] = 1
    dist = cv2.distanceTransform(1 - e, cv2.DIST_L2, 5)                 # px to the nearest outline
    lab = cv2.cvtColor(flat, cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
    wgt = np.clip(dist.ravel() - 1.5, 0.05, 4)
    den = np.bincount(fl, weights=wgt, minlength=n)
    base = np.stack([np.bincount(fl, weights=lab[:, i] * wgt, minlength=n) for i in range(3)], 1) / np.maximum(den, 1e-6)[:, None]
    if a.palette:   # the number's colour, not the picture's: what the dot shows is what the tap paints
        m = json.load(open(os.path.join(d, 'regions.json'))); pl = cv2.cvtColor(np.array(m['palette'], np.uint8).reshape(1, -1, 3)[:, :, ::-1].copy(), cv2.COLOR_BGR2LAB)[0].astype(np.float32)
        for r in m['regions']: base[r['id']] = pl[r['c']]
    area = np.bincount(fl, minlength=n).astype(np.float32); rmax = np.zeros(n, np.float32); np.maximum.at(rmax, fl, dist.ravel())
    # position of each pixel inside its piece along the light direction (upper left -> lower right), 0..1
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); proj = (xx * 0.55 + yy * 0.83).ravel()
    pmin = np.full(n, 1e9, np.float32); pmax = np.full(n, -1e9, np.float32); np.minimum.at(pmin, fl, proj); np.maximum.at(pmax, fl, proj)
    t = (proj - pmin[fl]) / np.maximum(pmax[fl] - pmin[fl], 1.0)         # 0 = lit side, 1 = shadow side
    big = (area[fl] > 0.035 * h * w)                                    # backgrounds: slow vertical gradient
    ymin = np.full(n, 1e9, np.float32); ymax = np.full(n, -1e9, np.float32); np.minimum.at(ymin, fl, yy.ravel()); np.maximum.at(ymax, fl, yy.ravel())
    ty = (yy.ravel() - ymin[fl]) / np.maximum(ymax[fl] - ymin[fl], 1.0)
    dn = np.clip(dist.ravel() / np.maximum(np.minimum(rmax[fl], 60.0), 1.0), 0, 1)   # 0 at the outline, 1 deep inside
    B = base[fl].copy(); Lc = B[:, 0]
    k = a.depth
    shade = np.where(big, (0.5 - ty) * 26 * k, (0.5 - t) * 46 * k)      # light to dark across the piece
    rim = -22 * k * np.exp(-dist.ravel() / 5.0) * np.where(big, 0.5, 1.0)  # soft dark rim inside the outline
    glow = 12 * k * (dn ** 1.5) * np.where(big, 0.3, 1.0)               # lighter toward the middle
    room = np.clip((255 - Lc) / 90, 0.25, 1.0)                           # pale colours brighten less, so whites stay white-ish
    dark = np.clip(Lc / 110, 0.35, 1.0)                                  # very dark colours darken less
    dL = np.where(shade + glow > 0, (shade + glow) * room, (shade + glow) * dark) + rim * dark
    out = B.copy(); out[:, 0] = np.clip(Lc + dL, 0, 255)
    sat = (1.0 + 0.22 * a.rich) * (1 + 0.10 * a.rich * (0.5 - t))        # deeper colour, a touch warmer on the lit side
    out[:, 1] = np.clip(128 + (B[:, 1] - 128) * sat, 0, 255); out[:, 2] = np.clip(128 + (B[:, 2] - 128) * sat + 3 * a.rich * (0.5 - t), 0, 255)
    img = cv2.cvtColor(out.reshape(h, w, 3).astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
    rng = np.random.RandomState(7); grain = cv2.GaussianBlur(rng.randn(h, w).astype(np.float32), (0, 0), 0.8) * 5.0
    img = np.clip(img + grain[..., None], 0, 255)
    img = cv2.bilateralFilter(img.astype(np.uint8), 5, 12, 3)
    rp = os.path.join(R, 'pages', 'rich', slug + '.jpg')
    if a.mix > 0 and os.path.exists(rp):   # mostly the computed shading, with some of the repaint's real texture and light
        img = cv2.addWeighted(img, 1 - a.mix, cv2.resize(cv2.imread(rp), (w, h)), a.mix, 0)
    cv2.imwrite(os.path.join(d, 'color.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    line = cv2.imread(os.path.join(d, 'line.png'), cv2.IMREAD_GRAYSCALE)
    if line is not None:
        blank = cv2.cvtColor(cv2.erode(line, np.ones((2, 2), np.uint8)), cv2.COLOR_GRAY2BGR)
        tt = np.clip(((xx - 0.60 * w) + (yy - 0.5 * h) * 0.35) / (0.06 * w) + 0.5, 0, 1)[..., None]
        feat = (np.minimum(img, blank) * (1 - tt) + blank * tt).astype(np.uint8)
        cv2.imwrite(os.path.join(d, 'feature.jpg'), cv2.resize(feat, (900, round(900 * h / w)), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 86])
    print(slug, 'shaded:', n - 1, 'pieces')
