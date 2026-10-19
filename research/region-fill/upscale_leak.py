"""Does segmenting on a 1500px upscale (as canvas drawImage would produce) leak more or less than native?
Representative pixel per baseline region = its distance-transform maximum (deep interior)."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
S4=[[0,1,0],[1,1,1],[0,1,0]]
im=Image.open(sys.argv[1]).convert("L"); g=np.asarray(im,dtype=np.uint8); H,W=g.shape
base,nb=ndimage.label(g>=200,structure=S4); bsz=np.bincount(base.ravel()); real=np.nonzero(bsz>=50)[0]; real=real[real>0]
dt=ndimage.distance_transform_edt(g>=200)
pos=np.array(ndimage.maximum_position(dt,base,real))  # (y,x) per region
print(f"baseline native T=200: {len(real)} regions>=50px; interior DT at rep: min={dt[pos[:,0],pos[:,1]].min():.1f}")
for size,resample,name in ((1500,Image.BILINEAR,'bilinear'),(1500,Image.BICUBIC,'bicubic'),(1500,Image.NEAREST,'nearest'),(843,Image.NEAREST,'native')):
    u=np.asarray(im.resize((size,size),resample),dtype=np.uint8)
    for T in (200,128):
        ul,nu=ndimage.label(u>=T,structure=S4); usz=np.bincount(ul.ravel())
        uy=np.clip((pos[:,0]*size+size//2)//H,0,size-1); ux=np.clip((pos[:,1]*size+size//2)//W,0,size-1)
        uid=ul[uy,ux]; valid=uid>0
        cnt=np.bincount(uid[valid]); merged=(cnt>1).sum(); swallowed=cnt[cnt>1].sum()
        print(f"{name:8s} {size}px T={T}: regions={nu} (>=50px: {(usz[1:]>=50).sum()}); reps on line={(~valid).sum()}; "
              f"{merged} regions swallow {swallowed} baseline regions (leaks vs native T=200); largest={usz[1:].max()/u.size:.1%}")
