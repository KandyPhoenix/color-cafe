import cv2, numpy as np, sys, os, json
OUT='/home/user/color-cafe/research/line-art'
os.makedirs(OUT, exist_ok=True)

def region_stats(bw):
    """bw: uint8, 255 = white (colourable), 0 = black line. Returns closed-region stats."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats((bw==255).astype(np.uint8), connectivity=4)
    areas = stats[1:, cv2.CC_STAT_AREA]
    total = bw.size
    white = (bw==255).sum()
    return dict(regions=int(n-1),
                regions_over_500px=int((areas>500).sum()),
                largest_region_pct_of_white=round(float(areas.max())/white*100,1) if len(areas) else 0,
                black_pct=round(100-white/total*100,1))

def canny(img, lo=60, hi=160):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.bilateralFilter(g, 9, 75, 75)
    e = cv2.Canny(g, lo, hi)
    e = cv2.dilate(e, np.ones((3,3),np.uint8), iterations=1)
    return 255 - e

def xdog(img, sigma=1.0, k=1.6, p=18, eps=0.72, phi=12):
    """Winnemoeller et al. XDoG (thresholded difference-of-Gaussians)."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)/255
    g1 = cv2.GaussianBlur(g,(0,0),sigma); g2 = cv2.GaussianBlur(g,(0,0),sigma*k)
    d = (1+p)*g1 - p*g2
    out = np.clip(np.where(d>=eps, 1.0, 1+np.tanh(phi*(d-eps))),0,1)
    _, bw = cv2.threshold((out*255).astype(np.uint8), 128, 255, cv2.THRESH_BINARY)
    return bw

def pencil(img, blur=21, thresh=235):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    inv = 255-g
    b = cv2.GaussianBlur(inv,(blur,blur),0)
    sketch = cv2.divide(g, 255-b, scale=256)
    _, bw = cv2.threshold(sketch, thresh, 255, cv2.THRESH_BINARY)
    return bw

def posterize_regions(img, k=12, spatial=12, color=30, min_area=400):
    """mean-shift smoothing -> k-means colour quantisation -> remove tiny regions -> draw region boundaries.
    Regions are closed by construction."""
    small = cv2.pyrMeanShiftFiltering(img, spatial, color)
    Z = small.reshape(-1,3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, centers = cv2.kmeans(Z, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    lab = labels.reshape(img.shape[:2]).astype(np.int32)
    # merge tiny connected components into neighbours (majority of dilated ring)
    for _ in range(2):
        n, cc, stats, _ = cv2.connectedComponentsWithStats((lab>=0).astype(np.uint8)*0+1, connectivity=4)
        # per-label components
        for c in range(k):
            m = (lab==c).astype(np.uint8)
            n, cc, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
            for i in range(1,n):
                if stats[i, cv2.CC_STAT_AREA] < min_area:
                    comp = (cc==i)
                    ring = cv2.dilate(comp.astype(np.uint8), np.ones((3,3),np.uint8)) .astype(bool) & ~comp
                    vals = lab[ring]
                    vals = vals[vals!=c]
                    if len(vals):
                        lab[comp] = np.bincount(vals).argmax()
    # boundaries: pixel differs from right or down neighbour
    b = np.zeros(lab.shape, np.uint8)
    b[:, :-1] |= (lab[:, :-1] != lab[:, 1:])
    b[:-1, :] |= (lab[:-1, :] != lab[1:, :])
    b = cv2.dilate(b*255, np.ones((3,3),np.uint8))
    return 255-b

def combo(img):
    """posterize boundaries (closed) + canny detail lines, unioned."""
    a = posterize_regions(img, k=10, min_area=600)
    c = canny(img, 80, 200)
    return cv2.bitwise_and(a, c)

if __name__=='__main__':
    results={}
    for name, path in [('treasure-cove','/home/user/puzzle-parlor/queue/img/treasure-cove.jpg'),
                       ('pine-forest','/home/user/puzzle-parlor/public/img/pine-forest.jpg')]:
        img = cv2.imread(path)
        # work at 1456px wide (half) so line weight is sensible relative to detail; pages are 843px
        s = 1456/img.shape[1]
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        for meth, fn in [('canny',canny),('xdog',xdog),('pencil',pencil),('posterize',posterize_regions),('combo',combo)]:
            bw = fn(img)
            fnm = f'{name}--{meth}.png'
            cv2.imwrite(os.path.join(OUT,fnm), bw)
            results[fnm]=region_stats(bw)
            print(fnm, results[fnm], flush=True)
    # reference: ChatGPT page
    ref = cv2.imread('/home/user/color-cafe/pages/sea-turtle-treasure.png', 0)
    _, refbw = cv2.threshold(ref, 128, 255, cv2.THRESH_BINARY)
    results['REF sea-turtle-treasure.png']=region_stats(refbw)
    print('REF', results['REF sea-turtle-treasure.png'])
    json.dump(results, open(os.path.join(OUT,'region-stats.json'),'w'), indent=1)
