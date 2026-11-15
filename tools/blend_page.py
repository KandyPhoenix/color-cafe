#!/usr/bin/env python3
"""Rebuild a line-art page the way "blend" pages work in coloring apps.

  python3 tools/blend_page.py <slug> [<slug> ...] [--colors 22] [--min 220]

The page still shows the artist's black-and-white drawing, but the spots you colour are not the drawn
shapes: they are the patches of one colour in the painting (a shadow under a shelf, the lit side of a wall,
a crease in a sleeve). Spots have no outlines of their own. Choosing a number shades its spots; a tap fills
one with the painting. So every spot is one colour, its number is that colour, and the finished page is the
painting exactly.

Paints the drawing's lines out of color.jpg, flattens it lightly, and hands that to flat_page.py for the
spots (the painting stays as what a tap reveals). Then puts the drawing back (ink.png, ink.json, line.png)
and marks the page "blend": 1 so the app draws the drawing only. Spots change, so saved progress restarts.
"""
import sys, os, json, argparse, subprocess, tempfile, shutil
import numpy as np, cv2
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('slugs', nargs='+'); ap.add_argument('--colors', type=int, default=22); ap.add_argument('--min', type=float, default=220)
a = ap.parse_args(); pj = os.path.join(R, 'public', 'pages.json'); tmp = tempfile.mkdtemp()
for slug in a.slugs:
    d = os.path.join(R, 'public', 'pages', slug); old = next(x for x in json.load(open(pj, encoding='utf-8')) if x['slug'] == slug)
    keep = {f: open(os.path.join(d, f), 'rb').read() for f in ('ink.png', 'ink.json', 'line.png', 'thumb.jpg') if os.path.exists(os.path.join(d, f))}
    paint = os.path.join(tmp, slug + '-paint.jpg'); shutil.copy(os.path.join(d, 'color.jpg'), paint)
    col = cv2.imread(paint); h, w = col.shape[:2]
    g = cv2.cvtColor(col, cv2.COLOR_BGR2GRAY); hsv = cv2.cvtColor(col, cv2.COLOR_BGR2HSV)
    ink = (((g < 70) & (hsv[:, :, 1] < 120)) | (g < 40)).astype(np.uint8)
    thin = ink & (cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones((13, 13), np.uint8)) == 0)        # lines, not big dark areas
    clean = cv2.inpaint(col, cv2.dilate(thin, np.ones((3, 3), np.uint8)) * 255, 3, cv2.INPAINT_TELEA)
    clean = cv2.pyrMeanShiftFiltering(cv2.medianBlur(clean, 5), 8, 20)
    flat = os.path.join(tmp, slug + '-flat.png'); cv2.imwrite(flat, clean)
    subprocess.run([sys.executable, os.path.join(R, 'tools', 'flat_page.py'), slug, flat, paint, '--title', old['title'], '--theme', old['theme'], '--style', old.get('style', ''),
                    '--artist', old.get('artist', 'Original art'), '--colors', str(a.colors), '--min', str(a.min)], check=True, stdout=subprocess.DEVNULL)
    for f, b in keep.items(): open(os.path.join(d, f), 'wb').write(b)
    for f in (slug + '-flat.png', slug + '-color.jpg', slug + '-color.png'):                          # flat_page's source copies are not sources here
        p = os.path.join(R, 'pages', 'src', f)
        if os.path.exists(p) and f.endswith('-flat.png'): os.remove(p)
    rp = os.path.join(d, 'regions.json'); m = json.load(open(rp)); m['blend'] = 1; m['ink'] = 2; m['inkv'] = 1 if 'ink.json' in keep else 0; m.pop('flat', None)
    json.dump(m, open(rp, 'w'), separators=(',', ':'))
    P = json.load(open(pj, encoding='utf-8'))
    for x in P:
        if x['slug'] == slug: x['added'] = old['added']; x['mode'] = 'pair'; x.pop('level', None); print(f"{slug}: {old['regions']} -> {x['regions']} spots, {x['colors']} colours")
    json.dump(P, open(pj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
