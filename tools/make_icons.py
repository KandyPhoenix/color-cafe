#!/usr/bin/env python3
"""Draw the Color Cafe app icons (taskbar, home screen, browser tab) into public/icons/.
A cream coffee cup on the cafe green, with three paint dots rising like steam."""
import os
from PIL import Image, ImageDraw
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(R, 'public', 'icons'); os.makedirs(OUT, exist_ok=True)
GREEN, CREAM, PINK, GOLD, ROSE, BROWN = '#4a6b4f', '#fbf3f1', '#f9c7d3', '#f6c453', '#d9466b', '#6b4a3a'

def art(size, pad=0.0, round_bg=True):
    S = size * 4; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if round_bg: d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * 0.22), fill=GREEN)
    else: d.rectangle([0, 0, S, S], fill=GREEN)
    k = (1 - 2 * pad); o = S * pad
    P = lambda x, y: (o + x * S * k, o + y * S * k)
    B = lambda x0, y0, x1, y1: [*P(x0, y0), *P(x1, y1)]
    w = S * k
    # saucer
    d.ellipse(B(0.17, 0.74, 0.83, 0.86), fill=CREAM)
    d.ellipse(B(0.25, 0.755, 0.75, 0.825), fill='#e7d9d4')
    # handle
    d.ellipse(B(0.62, 0.48, 0.84, 0.70), outline=CREAM, width=int(w * 0.055))
    # cup body: a bowl
    d.rectangle(B(0.22, 0.44, 0.70, 0.61), fill=CREAM)
    d.pieslice(B(0.22, 0.38, 0.70, 0.82), 0, 180, fill=CREAM)
    # coffee surface
    d.ellipse(B(0.24, 0.405, 0.68, 0.475), fill=CREAM)
    d.ellipse(B(0.265, 0.415, 0.655, 0.465), fill=BROWN)
    # paint dots rising like steam
    for (x, y, r, c) in [(0.36, 0.30, 0.065, PINK), (0.50, 0.20, 0.07, GOLD), (0.42, 0.10, 0.055, ROSE)]:
        d.ellipse(B(x - r, y - r, x + r, y + r), fill=c)
    return im.resize((size, size), Image.LANCZOS)

art(512).save(os.path.join(OUT, 'icon-512.png'))
art(192).save(os.path.join(OUT, 'icon-192.png'))
art(512, pad=0.10, round_bg=False).save(os.path.join(OUT, 'maskable-512.png'))   # Android crops to a circle/shape
art(180, pad=0.06, round_bg=False).convert('RGB').save(os.path.join(OUT, 'apple-touch-icon.png'))
art(64).save(os.path.join(OUT, 'favicon-64.png'))
art(256).save(os.path.join(OUT, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('icons written to', OUT)
