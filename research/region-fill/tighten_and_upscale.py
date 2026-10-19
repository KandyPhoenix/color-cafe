"""(1) Cost of tightening the strict core to close small outline gaps: how many real regions (>=50px at
T=200) have NO surviving core pixel under erode-1px / T=240 / T=250 (they would vanish or be absorbed).
And how many of the gap-joined 'pieces' get separated.
(2) Upscale 843->1500 (bilinear, like canvas drawImage smoothing) and re-run the merge/leak test."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
S4=[[0,1,0],[1,1,1],[0,1,0]]
path=sys.argv[1]
im=Image.open(path).convert("L"); g=np.asarray(im,dtype=np.uint8)
base,nb=ndimage.label(g>=200,structure=S4); bsz=np.bincount(base.ravel()); real=np.nonzero(bsz>=50)[0]; real=real[real>0]
print(f"baseline T=200: {len(real)} regions >=50px")
def survive(mask, name):
    lab,n=ndimage.label(mask,structure=S4)
    # a baseline region survives if any of its pixels is in mask
    has=np.zeros(nb+1,bool); has[np.unique(base[mask])]=True
    lost=(~has[real]).sum()
    # merges: baseline regions whose surviving pixels fall into >1 tightened region? (cannot: tightened ⊂ baseline). Instead: tightened regions >=50px count
    tsz=np.bincount(lab.ravel()); 
    # gap closing: baseline regions split into several tightened regions >=30px (joined by a thin neck in baseline)
    big=np.nonzero(tsz>=30)[0]; big=big[big>0]
    fl=lab.ravel(); fb=base.ravel(); order=np.argsort(fl,kind='stable'); rep=order[np.searchsorted(fl[order],big)]
    parent=fb[rep]; cnt=np.bincount(parent); split=(cnt>1).sum()
    print(f"{name:16s}: regions={n}; baseline regions lost (no core left)={lost} of {len(real)}; baseline regions that split into 2+ pieces(>=30px)={split} (gap-joined groups separated)")
survive(g>=200,"T=200 (base)")
survive(g>=230,"T=230")
survive(g>=240,"T=240")
survive(g>=250,"T=250")
survive(ndimage.binary_erosion(g>=200,structure=np.ones((3,3))),"T=200 erode1")
survive(ndimage.binary_erosion(g>=200,structure=S4),"T=200 erode1(4n)")
# (2) upscale
for size,resample,name in ((1500,Image.BILINEAR,'bilinear'),(1500,Image.LANCZOS,'lanczos'),(1500,Image.NEAREST,'nearest')):
    u=np.asarray(im.resize((size,size),resample),dtype=np.uint8)
    for T in (200,128):
        ul,nu=ndimage.label(u>=T,structure=S4); usz=np.bincount(ul.ravel())
        # map baseline regions (>=50px) by their centroid-ish representative pixel scaled up
        cy,cx=np.array(ndimage.center_of_mass(np.ones_like(g),base,real)).T if False else (None,None)
        # use one representative pixel per baseline region, scaled
        fb=base.ravel(); order=np.argsort(fb,kind='stable'); rep=order[np.searchsorted(fb[order],real)]
        ry,rx=np.divmod(rep,g.shape[1]); uy=np.clip((ry*size)//g.shape[0],0,size-1); ux=np.clip((rx*size)//g.shape[1],0,size-1)
        uid=ul[uy,ux]; valid=uid>0
        cnt=np.bincount(uid[valid]); merged=(cnt>1).sum(); swallowed=cnt[cnt>1].sum()
        print(f"upscale {size} {name:8s} T={T}: regions={nu} (>=50px: {(usz[1:]>=50).sum()}); of {len(real)} baseline regions, {(~valid).sum()} rep pixels landed on line; {merged} upscaled regions swallow {swallowed} baseline regions; largest={usz[1:].max()} ({usz[1:].max()/u.size:.1%})")
