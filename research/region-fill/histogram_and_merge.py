"""Histogram peaks, line-width estimate, and threshold-merge test (do regions leak into each
other when the fill threshold moves?)."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage

S4 = [[0,1,0],[1,1,1],[0,1,0]]
for path in sys.argv[1:]:
    g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
    name = path.split('/')[-1]
    hist = np.bincount(g.ravel(), minlength=256)
    top = np.argsort(hist)[::-1][:12]
    print(f"\n=== {name}")
    print("top-12 grey levels by count:", [(int(v), f"{hist[v]/g.size:.1%}") for v in sorted(top)])
    # noise check: isolated dark pixels inside white areas / isolated light pixels inside black
    dark = g < 128
    lab, n = ndimage.label(dark, structure=S4)
    sizes = np.bincount(lab.ravel())[1:]
    print(f"dark(<128) components: {n}; specks <5px: {(sizes<5).sum()}; <20px: {(sizes<20).sum()}")
    # line width via distance transform on dark mask: 2*median distance at ridge ~ stroke width
    dt = ndimage.distance_transform_edt(dark)
    ridge = dt[(dt>0)]
    # approximate stroke width = 2*max local DT along skeleton; use 90th pct of DT as proxy
    print(f"dark-stroke DT: median={np.median(ridge):.2f} p90={np.percentile(ridge,90):.2f} max={ridge.max():.1f}  (stroke width ~ 2x ridge DT)")
    # Width of anti-alias band: pixels with 32<g<224 adjacent to a dark pixel
    band = (g>=32)&(g<224)
    print(f"mid-grey band (32..223): {band.sum()/g.size:.2%} of pixels")
    # Merge test: regions at T=200 (strict) vs T=128 and T=64 (loose). For each loose region,
    # count how many strict regions (>=50px) it contains. >1 means those strict regions LEAK into one.
    strict_lab, ns = ndimage.label(g>=200, structure=S4)
    ssz = np.bincount(strict_lab.ravel()); 
    keep = np.nonzero(ssz>=50)[0]; keep = keep[keep>0]
    for T in (160, 128, 96, 64):
        loose_lab, nl = ndimage.label(g>=T, structure=S4)
        # map strict region -> loose region (via any pixel of the strict region)
        # all pixels of a strict region are white>=200 so they are also >=T, so each strict region sits in exactly one loose region
        first_idx = {}
        flat_s = strict_lab.ravel(); flat_l = loose_lab.ravel()
        # find one pixel index per strict region
        order = np.argsort(flat_s, kind='stable')
        sorted_s = flat_s[order]
        starts = np.searchsorted(sorted_s, keep)
        rep = order[starts]
        loose_of = flat_l[rep]
        counts = np.bincount(loose_of)
        merged_groups = (counts>1).sum(); merged_regions = counts[counts>1].sum()
        print(f"  T={T}: {len(keep)} strict regions(>=50px @T=200) collapse into {len(np.unique(loose_of))} loose regions; "
              f"{merged_groups} loose regions swallow {merged_regions} strict regions (leaks)")
        # biggest offender
        if merged_groups:
            worst = counts.argmax()
            print(f"    worst: loose region {worst} contains {counts[worst]} strict regions")
