"""Eyeball: regions that are one region at T=200 but split into 2+ pieces at T=230 / erode-1.
Panel per case: grey crop | T=200 region (white) | tightened pieces (colours)."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
S4=[[0,1,0],[1,1,1],[0,1,0]]
g=np.asarray(Image.open(sys.argv[1]).convert("L"),dtype=np.uint8); out=sys.argv[2]
base,nb=ndimage.label(g>=200,structure=S4); bsz=np.bincount(base.ravel())
rng=np.random.default_rng(5)
for name,mask in (("T230",g>=230),("erode1",ndimage.binary_erosion(g>=200,structure=np.ones((3,3))))):
    lab,n=ndimage.label(mask,structure=S4); tsz=np.bincount(lab.ravel())
    big=np.nonzero(tsz>=30)[0]; big=big[big>0]
    fl=lab.ravel(); fb=base.ravel(); order=np.argsort(fl,kind='stable'); rep=order[np.searchsorted(fl[order],big)]
    parent=fb[rep]; cnt=np.bincount(parent)
    cases=[p for p in np.argsort(cnt)[::-1] if cnt[p]>1 and 300<=bsz[p]<=6000][:6]
    panels=[]
    for p in cases:
        ys,xs=np.nonzero(base==p); x0,y0,x1,y1=max(xs.min()-5,0),max(ys.min()-5,0),min(xs.max()+5,842),min(ys.max()+5,842)
        crop=g[y0:y1+1,x0:x1+1]; rgb=np.stack([crop]*3,-1)
        bm=(base[y0:y1+1,x0:x1+1]==p); bimg=np.where(bm[...,None],255,np.stack([crop//3]*3,-1)).astype(np.uint8)
        sub=lab[y0:y1+1,x0:x1+1]; pal=rng.integers(80,255,size=(n+1,3),dtype=np.uint8); pal[0]=(0,0,0)
        timg=pal[sub]; timg[~bm]=(crop//3)[~bm,None]
        z=max(1,min(6,260//max(crop.shape)))
        panel=np.concatenate([rgb,np.full((crop.shape[0],3,3),255,np.uint8),bimg,np.full((crop.shape[0],3,3),255,np.uint8),timg],1)
        panel=np.asarray(Image.fromarray(panel).resize((panel.shape[1]*z,panel.shape[0]*z),Image.NEAREST))
        panels.append(panel); print(f"{name}: baseline region {p} size={bsz[p]} pieces={cnt[p]} bbox=({x0},{y0})-({x1},{y1})")
    w=max(p.shape[1] for p in panels); h=sum(p.shape[0]+6 for p in panels)
    canvas=np.full((h,w,3),128,np.uint8); y=0
    for p in panels: canvas[y:y+p.shape[0],:p.shape[1]]=p; y+=p.shape[0]+6
    Image.fromarray(canvas).save(f"{out}_splits_{name}.png")
