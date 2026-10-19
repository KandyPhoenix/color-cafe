"""Analyze line-art pages: grey histogram, connected-component counts at thresholds,
region-size distributions, and whether thresholds merge regions (outline gaps).
Usage: python3 analyze_pages.py /home/user/color-cafe/pages/*.png
"""
import sys, time
import numpy as np
from PIL import Image
from scipy import ndimage  # may be unavailable; fallback below

def load_grey(path):
    im = Image.open(path).convert("L")
    return np.asarray(im, dtype=np.uint8)

def label(mask):
    lab, n = ndimage.label(mask, structure=[[0,1,0],[1,1,1],[0,1,0]])  # 4-connectivity
    return lab, n

def summarize(path):
    g = load_grey(path)
    h, w = g.shape
    total = g.size
    print(f"\n=== {path.split('/')[-1]}  {w}x{h}")
    hist = np.bincount(g.ravel(), minlength=256)
    pure_black = hist[0] / total; pure_white = hist[255] / total
    grey = 1 - pure_black - pure_white
    print(f"pixels: black(0)={pure_black:.3%}  white(255)={pure_white:.3%}  grey(1..254)={grey:.3%}")
    dark = (g < 128).sum() / total
    print(f"dark(<128)={dark:.3%}  light(>=200)={(g>=200).sum()/total:.3%}")
    # grey band distribution
    for lo, hi in [(1,63),(64,127),(128,191),(192,254)]:
        print(f"  grey {lo:3d}-{hi:3d}: {hist[lo:hi+1].sum()/total:.3%}")
    results = {}
    for t in (64, 128, 160, 200, 230, 250):
        mask = g >= t  # fillable (white-ish)
        lab, n = label(mask)
        sizes = np.bincount(lab.ravel())[1:]
        big = (sizes >= 50).sum(); tiny = (sizes < 10).sum()
        largest = sizes.max() if n else 0
        results[t] = (n, big, tiny, largest, sizes)
        print(f"  T={t:3d}: regions={n:5d}  >=50px={big:4d}  <10px={tiny:4d}  largest={largest} ({largest/total:.1%})")
    return g, results

if __name__ == "__main__":
    for p in sys.argv[1:]:
        summarize(p)
