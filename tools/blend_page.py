#!/usr/bin/env python3
"""Rebuild a line-art page the way "blend" pages work in coloring apps.

  python3 tools/blend_page.py <slug> [<slug> ...] [--colors 22] [--min 220]

The page still shows the artist's black-and-white drawing, but the spots you colour are not the drawn
shapes: they are the patches of one colour in the painting (a shadow under a shelf, the lit side of a wall,
a crease in a sleeve). Spots have no outlines of their own. Choosing a number shades its spots; a tap fills
one with its number's colour, lighter and darker exactly where the painting is. So every spot is one colour
and everything a number paints is that number's colour.

Paints the drawing's lines out of color.jpg, flattens it lightly, and hands that to flat_page.py for the
spots (the painting stays as what a tap reveals). Then puts the drawing back (ink.png, ink.json, line.png)
and marks the page "blend": 1 so the app draws the drawing only. Spots change, so saved progress restarts.
"""
import sys, os, json, argparse, subprocess, tempfile, shutil
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+'); ap.add_argument('--colors', type=int, default=26); ap.add_argument('--min', type=float, default=220)
ap.add_argument('--split', type=float, default=260, help='a patch of a clearly different colour inside a spot becomes its own spot when at least this big (px on a 1254px page)')
ap.add_argument('--near', type=float, default=11, help='two palette colours closer than this are one number')
W3 = np.array([.5, 1, 1], np.float32)   # hue counts twice as much as light and dark: a green leaf and a brown shelf never share a number

def purify(d, clean, split, near):
    """Every spot one colour, every number the colour of its spots, no two numbers that look alike."""
    rp = os.path.join(d, 'regions.json'); m = json.load(open(rp))
    L = cv2.imread(os.path.join(d, 'labels.png')); lbl = L[:, :, 2].astype(np.int32) + 256 * L[:, :, 1].astype(np.int32); h, w = lbl.shape
    lab = cv2.cvtColor(cv2.resize(clean, (w, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2LAB).astype(np.float32) * W3
    def means(lb):
        n = lb.max() + 1; f = lb.ravel(); cnt = np.bincount(f, minlength=n).astype(np.float64)
        return np.stack([np.bincount(f, weights=lab[:, :, i].ravel(), minlength=n) for i in range(3)], 1) / np.maximum(cnt, 1)[:, None], cnt
    mean, cnt = means(lbl); MIN = split * (w * h) / (1254 * 1254); nxt = int(lbl.max()) + 1
    far = np.sqrt(((lab - mean[lbl]) ** 2).sum(2)) > 24                       # pixels that are not their spot's colour
    far = cv2.morphologyEx(far.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, cc, st, _ = cv2.connectedComponentsWithStats(far, connectivity=4)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < MIN: continue
        x, y, ww, hh = st[i, 0], st[i, 1], st[i, 2], st[i, 3]; sub = cc[y:y + hh, x:x + ww] == i; ls = lbl[y:y + hh, x:x + ww]
        for r in np.unique(ls[sub]):                                           # one new spot per old spot it sat in
            part = sub & (ls == r)
            if part.sum() >= MIN: ls[part] = nxt; nxt += 1
    mean, cnt = means(lbl); ids = [i for i in range(1, len(cnt)) if cnt[i] > 0]
    # palette: the spots' own colours, clustered; colours that look alike share a number
    K = len(m['palette']); pts = mean[ids].astype(np.float32); rep = np.repeat(pts, np.clip(np.sqrt(cnt[ids]) // 6, 1, 40).astype(int), 0)
    _, _, cen = cv2.kmeans(rep, min(K, len(ids)), None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 60, .2), 6, cv2.KMEANS_PP_CENTERS)
    cen = [c for c in cen]
    while len(cen) > 6:
        D = np.array([[np.linalg.norm(p - q) if i < j else 1e9 for j, q in enumerate(cen)] for i, p in enumerate(cen)]); i, j = np.unravel_index(D.argmin(), D.shape)
        if D[i, j] >= near: break
        cen[i] = (cen[i] + cen[j]) / 2; cen.pop(j)
    cen = np.array(cen); c = np.argmin(((pts[:, None, :] - cen[None]) ** 2).sum(2), 1); used = sorted(set(c.tolist())); remap = {o: k for k, o in enumerate(used)}
    m['palette'] = [[int(v) for v in x] for x in cv2.cvtColor((cen[used] / W3).clip(0, 255).astype(np.uint8).reshape(1, -1, 3), cv2.COLOR_LAB2BGR)[0][:, ::-1]]
    new = np.zeros(len(cnt), np.int32); regions = []
    for k, (r, ci) in enumerate(zip(ids, c), 1):
        new[r] = k; ys, xs = np.nonzero(lbl == r); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        mk = np.zeros((y1 - y0 + 2, x1 - x0 + 2), np.uint8); mk[ys - y0 + 1, xs - x0 + 1] = 1; dt = cv2.distanceTransform(mk, cv2.DIST_L2, 5); y, x = np.unravel_index(dt.argmax(), dt.shape)
        regions.append({'id': k, 'c': remap[int(ci)], 'a': int(len(ys)), 'x': int(x + x0 - 1), 'y': int(y + y0 - 1), 'r': round(float(dt.max()), 1)})
    lbl = new[lbl]; rgb = np.zeros((h, w, 3), np.uint8); rgb[:, :, 2] = lbl % 256; rgb[:, :, 1] = lbl // 256
    cv2.imwrite(os.path.join(d, 'labels.png'), rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    m['regions'] = regions; m.pop('lines', None); json.dump(m, open(rp, 'w'), separators=(',', ':'))
    worst = float(np.sort(np.sqrt(((pts - cen[c]) ** 2).sum(1)))[-max(1, len(ids) // 20)])
    print(f'  purify: {len(regions)} spots, {len(m["palette"])} colours; 95% of spots are within {worst:.0f} of their number\'s colour')

a = ap.parse_args(); pj = os.path.join(R, 'public', 'pages.json'); tmp = tempfile.mkdtemp()
for slug in a.slugs:
    d = os.path.join(R, 'public', 'pages', slug); old = next(x for x in json.load(open(pj, encoding='utf-8')) if x['slug'] == slug)
    keep = {f: open(os.path.join(d, f), 'rb').read() for f in ('ink.png', 'ink.json', 'line.png', 'thumb.jpg') if os.path.exists(os.path.join(d, f))}
    paint = os.path.join(tmp, slug + '-paint.jpg'); shutil.copy(os.path.join(d, 'color.jpg'), paint)
    col = cv2.imread(paint); h, w = col.shape[:2]
    # only the drawing's own lines are painted out (from line.png); dark painted things, a black cat, a night sky, stay dark
    ln = cv2.resize(cv2.imread(os.path.join(d, 'line.png'), cv2.IMREAD_GRAYSCALE), (w, h), interpolation=cv2.INTER_AREA)
    thin = (ln < 150).astype(np.uint8); thin = thin & (cv2.morphologyEx(thin, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)) == 0)
    clean = cv2.inpaint(col, cv2.dilate(thin, np.ones((3, 3), np.uint8)) * 255, 3, cv2.INPAINT_TELEA)
    clean = cv2.pyrMeanShiftFiltering(cv2.medianBlur(clean, 5), 8, 20)
    flat = os.path.join(tmp, slug + '-flat.png'); cv2.imwrite(flat, clean)
    subprocess.run([sys.executable, os.path.join(R, 'tools', 'flat_page.py'), slug, flat, paint, '--title', old['title'], '--theme', old['theme'], '--style', old.get('style', ''),
                    '--artist', old.get('artist', 'Original art'), '--colors', str(a.colors), '--min', str(a.min)], check=True, stdout=subprocess.DEVNULL)
    purify(d, clean, a.split, a.near)
    for f, b in keep.items(): open(os.path.join(d, f), 'wb').write(b)
    for f in (slug + '-flat.png', slug + '-color.jpg', slug + '-color.png'):                          # flat_page's source copies are not sources here
        p = os.path.join(R, 'pages', 'src', f)
        if os.path.exists(p) and f.endswith('-flat.png'): os.remove(p)
    rp = os.path.join(d, 'regions.json'); m = json.load(open(rp)); m['blend'] = 1; m['tone'] = 1; m['reveal'] = 0; m['shade'] = 1.0; m['ink'] = 2; m['inkv'] = 1 if 'ink.json' in keep else 0; m.pop('flat', None)
    json.dump(m, open(rp, 'w'), separators=(',', ':'))
    P = json.load(open(pj, encoding='utf-8'))
    for x in P:
        if x['slug'] == slug: x['regions'] = len(m['regions']); x['colors'] = len(m['palette']); x['added'] = old['added']; x['mode'] = 'pair'; x.pop('level', None); print(f"{slug}: {old['regions']} -> {x['regions']} spots, {x['colors']} colours")
    json.dump(P, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
