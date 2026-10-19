"""Render colorized region maps at two thresholds and a crop of the worst leak, for eyeballing."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
S4=[[0,1,0],[1,1,1],[0,1,0]]
path, out = sys.argv[1], sys.argv[2]
g = np.asarray(Image.open(path).convert("L"), dtype=np.uint8)
rng = np.random.default_rng(1)
def colorize(lab, n):
    pal = rng.integers(60, 255, size=(n+1,3), dtype=np.uint8); pal[0]=(0,0,0)
    return pal[lab]
sl, ns = ndimage.label(g>=200, structure=S4)
ll, nl = ndimage.label(g>=128, structure=S4)
Image.fromarray(colorize(sl,ns)).resize((700,700), Image.NEAREST).save(f"{out}_T200.png")
Image.fromarray(colorize(ll,nl)).resize((700,700), Image.NEAREST).save(f"{out}_T128.png")
# worst leak: loose region containing most strict regions
ssz=np.bincount(sl.ravel()); keep=np.nonzero(ssz>=50)[0]; keep=keep[keep>0]
flat_s=sl.ravel(); flat_l=ll.ravel(); order=np.argsort(flat_s,kind='stable'); rep=order[np.searchsorted(flat_s[order],keep)]
loose_of=flat_l[rep]; counts=np.bincount(loose_of); worst=counts.argmax()
members = keep[loose_of==worst]
ys,xs=np.nonzero(ll==worst); print("worst loose region", worst, "bbox", xs.min(),ys.min(),xs.max(),ys.max(), "strict members", len(members))
# pick second-worst that is smaller for a readable crop
cand=[(counts[i],i) for i in range(len(counts)) if counts[i]>1]
cand.sort(reverse=True)
for c,i in cand[:6]:
    ys,xs=np.nonzero(ll==i); print(f"  loose {i}: {c} strict regions, bbox {xs.min()},{ys.min()}-{xs.max()},{ys.max()} size {(ll==i).sum()}")
c,i = [t for t in cand if 60 < (ll==t[1]).sum() < 20000][0]
ys,xs=np.nonzero(ll==i); x0,y0,x1,y1=max(xs.min()-6,0),max(ys.min()-6,0),min(xs.max()+6,842),min(ys.max()+6,842)
crop=g[y0:y1+1,x0:x1+1]
# show: grey crop | strict labels | loose labels, side by side, zoomed
rgb=np.stack([crop]*3,-1)
sc=colorize(sl[y0:y1+1,x0:x1+1], ns); lc=colorize(ll[y0:y1+1,x0:x1+1], nl)
panel=np.concatenate([rgb, np.full((crop.shape[0],4,3),255,np.uint8), sc, np.full((crop.shape[0],4,3),255,np.uint8), lc],1)
z=max(1, 900//panel.shape[1])
Image.fromarray(panel).resize((panel.shape[1]*z, panel.shape[0]*z), Image.NEAREST).save(f"{out}_leak_crop.png")
print("leak crop from loose region", i, "bbox", x0,y0,x1,y1, "zoom", z)
