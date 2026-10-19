"""(1) Watershed the anti-alias halo: label regions at T_strict, then grow each label simultaneously
into pixels with grey >= T_halo (BFS, all seeds at once) so the halo is split between neighbours
instead of leaking. Report how many pixels remain unassigned and whether any strict regions merged.
(2) Outline-gap test: erode the fillable mask by 1 and 2 px; count regions (>=200px) that were one
region at T_strict but become several when the neck is removed => joined only through a thin neck."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage
S4=[[0,1,0],[1,1,1],[0,1,0]]
path=sys.argv[1]; out=sys.argv[2]
g=np.asarray(Image.open(path).convert("L"),dtype=np.uint8)
H,W=g.shape
T_STRICT=200
for T_HALO in (128, 64, 32):
    sl,ns=ndimage.label(g>=T_STRICT,structure=S4)
    grow=(g>=T_HALO)
    # simultaneous BFS growth == nearest-seed assignment restricted to the 'grow' mask. Approximate with
    # iterative dilation rounds (each round grows all labels 1px; conflicts resolved by first-come = tie to lower label).
    lab=sl.copy(); rounds=0
    while True:
        front=(lab==0)&grow
        if not front.any() or rounds>12: break
        # candidate label from 4 neighbours (take max over neighbours; ties are arbitrary but no leak since seeds grow together)
        up=np.zeros_like(lab); up[1:]=lab[:-1]
        dn=np.zeros_like(lab); dn[:-1]=lab[1:]
        lf=np.zeros_like(lab); lf[:,1:]=lab[:,:-1]
        rt=np.zeros_like(lab); rt[:,:-1]=lab[:,1:]
        cand=np.maximum(np.maximum(up,dn),np.maximum(lf,rt))
        newly=front&(cand>0)
        lab[newly]=cand[newly]; rounds+=1
    unassigned=((lab==0)&grow).sum()
    line_core=(g<T_HALO).sum()
    # did any pixel adjacent to two different labels exist? (count label boundaries where neighbours differ and both nonzero)
    print(f"T_halo={T_HALO}: rounds={rounds} halo pixels assigned={(lab>0).sum()-(sl>0).sum()} unassigned(fillable but unreached)={unassigned} line-core(<T_halo)={line_core} ({line_core/g.size:.1%})")
    if T_HALO==128:
        rng=np.random.default_rng(1); pal=rng.integers(60,255,size=(ns+1,3),dtype=np.uint8); pal[0]=(0,0,0)
        col=pal[lab]
        # composite with line art via multiply to preview the crisp-line result
        comp=(col.astype(np.uint16)*np.stack([g]*3,-1)//255).astype(np.uint8)
        y0,x0=200,160; crop=comp[y0:y0+90,x0:x0+90]
        Image.fromarray(crop).resize((630,630),Image.NEAREST).save(f"{out}_halo_multiply_crop.png")
        Image.fromarray(comp).resize((700,700),Image.LANCZOS).save(f"{out}_halo_multiply_full.png")
        # also: how many fillable pixels does the strict map leave as 'white halo' if we DON'T grow?
        print(f"  without halo growth, white gap pixels between fill and line core(<128): {((sl==0)&(g>=128)).sum()} ({((sl==0)&(g>=128)).sum()/g.size:.1%})")

# (2) thin-neck / outline-gap test
sl,ns=ndimage.label(g>=T_STRICT,structure=S4)
ssz=np.bincount(sl.ravel())
for r in (1,2):
    er=ndimage.binary_erosion(g>=T_STRICT, structure=np.ones((2*r+1,2*r+1)))
    el,ne=ndimage.label(er,structure=S4)
    esz=np.bincount(el.ravel())
    big=np.nonzero(esz>=200)[0]; big=big[big>0]
    # parent strict label for each eroded region
    flat_e=el.ravel(); flat_s=sl.ravel(); order=np.argsort(flat_e,kind='stable'); rep=order[np.searchsorted(flat_e[order],big)]
    parent=flat_s[rep]; counts=np.bincount(parent)
    necks=counts[counts>1]
    print(f"erode {r}px: {len(big)} eroded regions>=200px; {len(necks)} strict regions are made of 2+ such pieces (joined only via a neck <= {2*r}px wide); pieces involved={necks.sum()}")
    # list top strict regions by number of pieces with their sizes
    top=np.argsort(counts)[::-1][:5]
    for s in top:
        if counts[s]>1: print(f"   strict region {s} size={ssz[s]} pieces={counts[s]}")
    if r==1:
        # visualize: pieces of the largest strict region (background) in different colours
        bg=ssz[1:].argmax()+1
        pieces=big[parent==bg]
        rng=np.random.default_rng(3); pal=rng.integers(60,255,size=(ne+1,3),dtype=np.uint8); pal[:]=(40,40,40)
        for p in pieces: pal[p]=rng.integers(60,255,3)
        img=pal[el]; img[g<128]=(0,0,0)
        Image.fromarray(img).resize((700,700),Image.NEAREST).save(f"{out}_bg_pieces_erode1.png")
        print(f"   background strict region {bg}: {len(pieces)} pieces >=200px after 1px erosion; piece sizes top: {sorted([int(esz[p]) for p in pieces])[::-1][:8]}")
