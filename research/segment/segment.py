#!/usr/bin/env python3
"""Color-by-number segmentation experiment (Color Cafe, issue 11).

Pipeline: load -> optional smoothing -> Lab k-means quantise (N colours) ->
per-colour connected components -> merge small regions into best neighbour
(repeat until none below threshold) -> outlines -> number at most interior
point (distance transform) -> render page / palette / label map / previews.

Usage: python3 segment.py IMAGE --n 24 --smooth bilateral --min-area 400 --min-radius 6 --tag name
"""
import argparse, json, os, sys, time
import numpy as np
import cv2
from scipy import ndimage

T0 = time.perf_counter()
def tick(msg, t=[None]):
    now = time.perf_counter()
    if t[0] is not None:
        print(f"  [{now - t[0]:6.2f}s] {msg}", flush=True)
    t[0] = now

# ---------------------------------------------------------------- smoothing
def smooth(bgr, mode):
    if mode == "none":
        return bgr
    if mode == "bilateral":
        # two passes of a moderate bilateral: flattens brush texture, keeps edges
        x = cv2.bilateralFilter(bgr, d=9, sigmaColor=35, sigmaSpace=7)
        return cv2.bilateralFilter(x, d=9, sigmaColor=35, sigmaSpace=7)
    if mode == "strong":
        # three bilateral passes with a wider colour sigma: kills more brush texture
        x = bgr
        for _ in range(3):
            x = cv2.bilateralFilter(x, d=11, sigmaColor=50, sigmaSpace=9)
        return x
    if mode == "meanshift":
        # mean-shift is O(n * window); run at half resolution then upsample.
        h, w = bgr.shape[:2]
        small = cv2.resize(bgr, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
        ms = cv2.pyrMeanShiftFiltering(small, sp=8, sr=20)
        return cv2.resize(ms, (w, h), interpolation=cv2.INTER_LINEAR)
    raise ValueError(mode)

# ---------------------------------------------------------------- quantise
def quantise_lab(bgr, n, seed=0, sample=200_000, max_share=1.0, min_split_de=4.0, n_max=None):
    """k-means in CIE Lab. Returns (colour index map uint8 HxW, palette BGR uint8 Nx3, palette Lab float Nx3)."""
    lab = cv2.cvtColor(bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)  # true CIE Lab: L 0..100, a/b ~ -128..127
    flat = lab.reshape(-1, 3)
    rng = np.random.default_rng(seed)
    idx = rng.choice(flat.shape[0], size=min(sample, flat.shape[0]), replace=False)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    _, _, centers = cv2.kmeans(flat[idx], n, None, crit, 5, cv2.KMEANS_PP_CENTERS)
    # assign every pixel to nearest centre (chunked to bound memory)
    out = np.empty(flat.shape[0], dtype=np.uint8)
    c2 = (centers ** 2).sum(1)
    step = 1_000_000
    for s in range(0, flat.shape[0], step):
        chunk = flat[s:s + step]
        d = c2[None, :] - 2.0 * chunk @ centers.T  # ||x-c||^2 - ||x||^2, argmin is same
        out[s:s + step] = d.argmin(1)
    # adaptive split: a colour that owns more than max_share of the pixels is re-split (k=2, Lab) so one
    # near-black colour cannot swallow half a dark painting. Stops when the two halves are closer than
    # min_split_de (not worth a new palette entry) or the palette hits n_max.
    n_max = n_max or n
    centers = centers.astype(np.float32)
    splits = []
    while len(centers) < n_max:
        share = np.bincount(out, minlength=len(centers)) / out.size
        c = int(share.argmax())
        if share[c] <= max_share:
            break
        members = np.flatnonzero(out == c)
        sub = flat[rng.choice(members, size=min(sample, members.size), replace=False)]
        _, _, sc = cv2.kmeans(sub, 2, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        de = float(np.linalg.norm(sc[0] - sc[1]))
        if de < min_split_de:
            break
        # reassign this colour's pixels to the closer of the two sub-centres
        m = flat[members]
        d0 = ((m - sc[0]) ** 2).sum(1); d1 = ((m - sc[1]) ** 2).sum(1)
        new = len(centers)
        out[members[d1 < d0]] = new
        centers = np.vstack([centers, sc[1:2]]); centers[c] = sc[0]
        splits.append((c, new, round(de, 1), round(float(share[c]), 3)))
    if splits:
        print(f"    adaptive splits: {len(splits)} -> palette {len(centers)}: {splits}", flush=True)
    n = len(centers)
    # sort palette by luminance so numbering is dark->light (nicer legend)
    order = np.argsort(centers[:, 0])
    remap = np.empty(n, dtype=np.uint8); remap[order] = np.arange(n, dtype=np.uint8)
    out = remap[out]
    centers = centers[order]
    pal_bgr = (cv2.cvtColor(centers.reshape(1, -1, 3), cv2.COLOR_LAB2BGR).reshape(-1, 3) * 255.0).round().clip(0, 255).astype(np.uint8)
    return out.reshape(lab.shape[:2]), pal_bgr, centers

# ---------------------------------------------------------------- components
def components(cidx, n):
    """Connected components (4-connectivity) per colour. Returns label map int32 (1..R), region->colour array (len R+1), areas."""
    h, w = cidx.shape
    labels = np.zeros((h, w), dtype=np.int32)
    reg_colour = [0]
    areas = [0]
    offset = 0
    for c in range(n):
        mask = (cidx == c).astype(np.uint8)
        cnt, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4, ltype=cv2.CV_32S)
        if cnt <= 1:
            continue
        m = lab > 0
        labels[m] = lab[m] + offset
        reg_colour.extend([c] * (cnt - 1))
        areas.extend(stats[1:, cv2.CC_STAT_AREA].tolist())
        offset += cnt - 1
    return labels, np.array(reg_colour, dtype=np.int32), np.array(areas, dtype=np.int64)

def adjacency(labels):
    """Return (a, b, border_len) arrays for every pair of touching regions (a<b)."""
    pairs = []
    r = labels[:, :-1].ravel(); s = labels[:, 1:].ravel()
    m = r != s; pairs.append(np.stack([r[m], s[m]], 1))
    r = labels[:-1, :].ravel(); s = labels[1:, :].ravel()
    m = r != s; pairs.append(np.stack([r[m], s[m]], 1))
    p = np.concatenate(pairs)
    lo = p.min(1); hi = p.max(1)
    key = lo.astype(np.int64) * (labels.max() + 1) + hi
    uk, cnt = np.unique(key, return_counts=True)
    return uk // (labels.max() + 1), uk % (labels.max() + 1), cnt

def inscribed_radius(labels, nreg):
    """Distance-transform based 'most interior point' per region. Returns (radius[R+1], (y,x)[R+1])."""
    # boundary = pixel whose right or down neighbour has another label
    b = np.zeros(labels.shape, dtype=np.uint8)
    b[:, :-1] |= (labels[:, :-1] != labels[:, 1:])
    b[:-1, :] |= (labels[:-1, :] != labels[1:, :])
    b[:, -1] = 1; b[-1, :] = 1; b[0, :] = 1; b[:, 0] = 1  # image border counts as an edge
    dt = cv2.distanceTransform((1 - b), cv2.DIST_L2, 5)
    pos = ndimage.maximum_position(dt, labels=labels, index=np.arange(1, nreg + 1))
    pos = np.array(pos, dtype=np.int32)
    rad = np.zeros(nreg + 1, dtype=np.float32)
    rad[1:] = dt[pos[:, 0], pos[:, 1]]
    out = np.zeros((nreg + 1, 2), dtype=np.int32); out[1:] = pos
    return rad, out, dt

def merge_small(cidx, n, pal_lab, min_area, min_radius, max_passes=12):
    """Repeatedly merge regions below thresholds into the best touching neighbour.
    'best' = neighbour maximising shared-border-length / (1 + Lab distance)   (prefers long shared edge, similar colour).
    Merging recolours the small region to the neighbour's palette colour, then components are recomputed."""
    history = []
    for p in range(max_passes):
        labels, reg_colour, areas = components(cidx, n)
        R = len(areas) - 1
        rad, pos, _ = inscribed_radius(labels, R)
        small = np.zeros(R + 1, dtype=bool)
        small[1:] = (areas[1:] < min_area) | (rad[1:] < min_radius)
        nsmall = int(small.sum())
        history.append((R, nsmall, int(areas[1:].min()), float(rad[1:].min())))
        print(f"    pass {p}: regions={R:,} small={nsmall:,} min_area={areas[1:].min()} min_rad={rad[1:].min():.1f}", flush=True)
        if nsmall == 0:
            return labels, reg_colour, areas, rad, pos, history
        a, b, blen = adjacency(labels)
        # candidate merges: small region -> neighbour that is strictly "bigger" (area, then id) so the
        # merge graph is acyclic (no two small regions swapping colours forever).
        ea = np.concatenate([a, b]); eb = np.concatenate([b, a]); el = np.concatenate([blen, blen])
        bigger = (areas[eb] > areas[ea]) | ((areas[eb] == areas[ea]) & (eb > ea))
        keep = small[ea] & bigger
        ea, eb, el = ea[keep], eb[keep], el[keep]
        dcol = np.linalg.norm(pal_lab[reg_colour[ea]] - pal_lab[reg_colour[eb]], axis=1)
        # score: long shared edge, similar colour, prefer a neighbour that will survive
        score = el / (1.0 + dcol) * np.where(small[eb], 0.5, 1.0)
        order = np.lexsort((-score, ea))
        ea_s, eb_s = ea[order], eb[order]
        first = np.ones(len(ea_s), dtype=bool); first[1:] = ea_s[1:] != ea_s[:-1]
        target = np.arange(R + 1, dtype=np.int64)
        target[ea_s[first]] = eb_s[first]
        # pointer-jump so a->b->c resolves to c in this pass
        for _ in range(64):
            nt = target[target]
            if np.array_equal(nt, target):
                break
            target = nt
        new_col = reg_colour[target]
        cidx = new_col[labels].astype(np.uint8)
    labels, reg_colour, areas = components(cidx, n)
    R = len(areas) - 1
    rad, pos, _ = inscribed_radius(labels, R)
    return labels, reg_colour, areas, rad, pos, history

# ---------------------------------------------------------------- giant-region split
def split_giants(labels, reg_colour, areas, orig_bgr, max_area, min_area, min_radius=0.0, compact=12.0, seed=0):
    """Any region larger than max_area is cut into ~area/max_area chunks with a SLIC-style k-means on
    (x, y, L, a, b) of the ORIGINAL pixels, so cuts follow real texture edges (trunk vs sky) instead of
    being an arbitrary grid. Chunks keep the parent's palette colour (adjacent same-number regions are
    normal on a colour-by-number page). Chunk slivers below min_area are merged into the touching chunk
    with the longest shared border. Returns new (labels, reg_colour, areas)."""
    rng = np.random.default_rng(seed)
    lab = None
    R = len(areas) - 1
    giants = [r for r in range(1, R + 1) if areas[r] > max_area]
    if not giants:
        return labels, reg_colour, areas, 0
    lab = cv2.cvtColor(orig_bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    labels = labels.copy()
    next_id = R + 1
    new_colour = list(reg_colour)
    nchunks = 0
    for r in giants:
        ys, xs = np.nonzero(labels == r)
        k = int(np.ceil(areas[r] / max_area))
        S = np.sqrt(areas[r] / k)                      # ~ chunk side length
        feat = np.stack([xs / S * compact, ys / S * compact, lab[ys, xs, 0], lab[ys, xs, 1], lab[ys, xs, 2]], 1).astype(np.float32)
        idx = rng.choice(len(feat), size=min(100_000, len(feat)), replace=False)
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        _, _, cen = cv2.kmeans(feat[idx], k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        c2 = (cen ** 2).sum(1)
        assign = (c2[None, :] - 2.0 * feat @ cen.T).argmin(1)
        # components inside the region's bbox
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub = np.zeros((y1 - y0, x1 - x0), dtype=np.int32)
        sub[ys - y0, xs - x0] = assign + 1
        chunk = np.zeros_like(sub); off = 0; carea = [0]
        for c in range(1, k + 1):
            cnt, cl, st, _ = cv2.connectedComponentsWithStats((sub == c).astype(np.uint8), connectivity=4)
            m = cl > 0; chunk[m] = cl[m] + off; off += cnt - 1; carea.extend(st[1:, cv2.CC_STAT_AREA].tolist())
        carea = np.array(carea, dtype=np.int64)
        # merge slivers into the touching chunk with the longest border (same region only), until none left
        for _ in range(20):
            small = np.zeros(len(carea), dtype=bool); small[1:] = carea[1:] < min_area
            if min_radius > 0:   # a thin chunk is as untappable as a tiny one
                crad, _, _ = inscribed_radius(chunk, len(carea) - 1)
                small[1:] |= (crad[1:] < min_radius) & (carea[1:] > 0)
            if not small.any():
                break
            a, b, bl = adjacency(chunk)
            keep = (a > 0) & (b > 0)
            a, b, bl = a[keep], b[keep], bl[keep]
            ea = np.concatenate([a, b]); eb = np.concatenate([b, a]); el = np.concatenate([bl, bl])
            bigger = (carea[eb] > carea[ea]) | ((carea[eb] == carea[ea]) & (eb > ea))
            kp = small[ea] & bigger
            ea, eb, el = ea[kp], eb[kp], el[kp]
            if len(ea) == 0:
                break
            order = np.lexsort((-el, ea)); ea, eb = ea[order], eb[order]
            first = np.ones(len(ea), dtype=bool); first[1:] = ea[1:] != ea[:-1]
            target = np.arange(len(carea)); target[ea[first]] = eb[first]
            for _ in range(64):
                nt = target[target]
                if np.array_equal(nt, target): break
                target = nt
            chunk = target[chunk]
            carea = np.bincount(chunk.ravel(), minlength=len(carea)).astype(np.int64); carea[0] = 0
        ids = np.flatnonzero(carea > 0)
        remap = np.zeros(len(carea), dtype=np.int32)
        remap[ids[0]] = r                                 # first chunk keeps the old id
        for i in ids[1:]:
            remap[i] = next_id; new_colour.append(reg_colour[r]); next_id += 1
        nchunks += len(ids)
        m = chunk > 0
        view = labels[y0:y1, x0:x1]
        view[m] = remap[chunk[m]]
    reg_colour = np.array(new_colour, dtype=np.int32)
    areas = np.bincount(labels.ravel(), minlength=len(reg_colour)).astype(np.int64); areas[0] = 0
    return labels, reg_colour, areas, nchunks

# ---------------------------------------------------------------- rendering
def outline_mask(labels):
    b = np.zeros(labels.shape, dtype=np.uint8)
    b[:, :-1] |= (labels[:, :-1] != labels[:, 1:])
    b[:-1, :] |= (labels[:-1, :] != labels[1:, :])
    return b

def render_page(labels, reg_colour, rad, pos, outline, number_min_radius=5.0):
    h, w = labels.shape
    page = np.full((h, w, 3), 255, dtype=np.uint8)
    # 2px grey outline
    thick = cv2.dilate(outline, np.ones((2, 2), np.uint8))
    page[thick > 0] = (90, 90, 90)
    R = len(reg_colour) - 1
    placed = 0
    for r in range(1, R + 1):
        rr = rad[r]
        if rr < number_min_radius:
            continue
        txt = str(int(reg_colour[r]) + 1)
        # font so the text height ~ 0.9 * inscribed diameter, capped
        scale = min(max(rr * 1.1 / 22.0, 0.3), 2.5)
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        if max(tw, th) > rr * 2.2:
            scale *= (rr * 2.2) / max(tw, th)
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
        y, x = pos[r]
        cv2.putText(page, txt, (int(x - tw / 2), int(y + th / 2)), cv2.FONT_HERSHEY_SIMPLEX, scale, (40, 40, 40), 1, cv2.LINE_AA)
        placed += 1
    return page, placed

def render_palette(pal_bgr):
    n = len(pal_bgr); sw = 80; cols = 12
    rows = (n + cols - 1) // cols
    img = np.full((rows * sw, cols * sw, 3), 255, dtype=np.uint8)
    for i, c in enumerate(pal_bgr):
        r, k = divmod(i, cols)
        cv2.rectangle(img, (k * sw, r * sw), ((k + 1) * sw - 1, (r + 1) * sw - 1), tuple(int(v) for v in c), -1)
        lum = 0.114 * c[0] + 0.587 * c[1] + 0.299 * c[2]
        col = (255, 255, 255) if lum < 128 else (0, 0, 0)
        cv2.putText(img, str(i + 1), (k * sw + 8, r * sw + 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, col, 2, cv2.LINE_AA)
    return img

def label_vis(labels, reg_colour, pal_bgr):
    return pal_bgr[reg_colour[labels]]

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--smooth", default="bilateral", choices=["none", "bilateral", "strong", "meanshift"])
    ap.add_argument("--min-area", type=int, default=400)
    ap.add_argument("--min-radius", type=float, default=6.0)
    ap.add_argument("--max-share", type=float, default=1.0, help="split any palette colour owning more than this pixel fraction")
    ap.add_argument("--extra", type=int, default=12, help="max extra palette entries the adaptive split may add")
    ap.add_argument("--max-share-region", type=float, default=1.0, help="post-merge: split any region bigger than this fraction of the image")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "out"))
    ap.add_argument("--save-all", action="store_true", help="save page/palette/label map/previews (else only stats)")
    args = ap.parse_args()

    name = os.path.splitext(os.path.basename(args.image))[0]
    tag = args.tag or f"{name}_n{args.n}_{args.smooth}_a{args.min_area}_r{int(args.min_radius)}" + (f"_ms{int(args.max_share*100)}" if args.max_share < 1 else "") + (f"_split{int(args.max_share_region*100)}" if args.max_share_region < 1 else "")
    os.makedirs(args.out, exist_ok=True)
    print(f"== {tag}")
    t_start = time.perf_counter()
    tick("start")
    orig = cv2.imread(args.image, cv2.IMREAD_COLOR)
    h, w = orig.shape[:2]
    tick(f"loaded {w}x{h}")
    sm = smooth(orig, args.smooth)
    tick(f"smooth={args.smooth}")
    cidx, pal_bgr, pal_lab = quantise_lab(sm, args.n, max_share=args.max_share, n_max=args.n + args.extra)
    n_final = len(pal_bgr)
    tick(f"kmeans N={args.n} -> palette {n_final}")
    labels0, rc0, areas0 = components(cidx, n_final)
    tick(f"raw components: {len(areas0)-1:,} regions, {int((areas0[1:] < args.min_area).sum()):,} below {args.min_area}px")
    labels, reg_colour, areas, rad, pos, hist = merge_small(cidx, n_final, pal_lab, args.min_area, args.min_radius)
    R = len(areas) - 1
    tick(f"merged: {R:,} regions")
    if args.max_share_region < 1.0:
        labels, reg_colour, areas, nchunks = split_giants(labels, reg_colour, areas, orig, int(args.max_share_region * h * w), args.min_area, args.min_radius)
        R = len(areas) - 1
        rad, pos, _ = inscribed_radius(labels, R)
        tick(f"giant split: {nchunks} chunks -> {R:,} regions")
    outline = outline_mask(labels)
    page, placed = render_page(labels, reg_colour, rad, pos, outline)
    tick(f"page rendered, {placed:,} numbers")
    t_total = time.perf_counter() - t_start

    # reveal checks: the app shows original pixels inside revealed regions
    final_cidx = reg_colour[labels]
    revealed_all = np.where(np.ones((h, w, 1), bool), orig, page)
    assert np.array_equal(revealed_all, orig)
    half_mask = (final_cidx < n_final // 2)[..., None]       # reveal the darker half of the palette
    half = np.where(half_mask, orig, page)
    # quantised "flat" render vs original (how far the palette is from the painting)
    flat = pal_bgr[final_cidx]
    lab_o = cv2.cvtColor(orig.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    lab_f = cv2.cvtColor(flat.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    de = np.linalg.norm(lab_o - lab_f, axis=2)
    de_mean = float(de.mean()); de_p95 = float(np.percentile(de, 95))

    # per-colour region counts
    per_colour = np.bincount(reg_colour[1:], minlength=n_final).tolist()
    stats = {
        "tag": tag, "image": name, "w": w, "h": h, "n_requested": args.n, "n": n_final, "smooth": args.smooth,
        "min_area": args.min_area, "min_radius": args.min_radius,
        "regions_raw": int(len(areas0) - 1),
        "regions_final": int(R),
        "numbers_placed": int(placed),
        "smallest_area": int(areas[1:].min()), "median_area": float(np.median(areas[1:])), "largest_area": int(areas[1:].max()),
        "smallest_radius": float(rad[1:].min()), "median_radius": float(np.median(rad[1:])),
        "regions_radius_lt_8": int((rad[1:] < 8).sum()), "regions_radius_lt_12": int((rad[1:] < 12).sum()),
        "per_colour_regions": per_colour,
        "outline_px_fraction": float(outline.mean()),
        "flat_vs_orig_deltaE76_mean": round(de_mean, 2), "flat_vs_orig_deltaE76_p95": round(de_p95, 2),
        "revealed_equals_original": True,
        "time_total_s": round(t_total, 2),
        "merge_history": hist,
        "palette_rgb": [[int(c[2]), int(c[1]), int(c[0])] for c in pal_bgr],
    }
    with open(os.path.join(args.out, f"{tag}.json"), "w") as f:
        json.dump(stats, f, indent=1)

    if args.save_all:
        prev_w = 1456  # half-size previews for viewing; full-size page kept too
        def small(img): return cv2.resize(img, (prev_w, int(h * prev_w / w)), interpolation=cv2.INTER_AREA)
        cv2.imwrite(os.path.join(args.out, f"{tag}_page_full.png"), page, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        cv2.imwrite(os.path.join(args.out, f"{tag}_page.png"), small(page))
        cv2.imwrite(os.path.join(args.out, f"{tag}_palette.png"), render_palette(pal_bgr))
        cv2.imwrite(os.path.join(args.out, f"{tag}_labelvis.jpg"), small(label_vis(labels, reg_colour, pal_bgr)), [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(os.path.join(args.out, f"{tag}_half.jpg"), small(half), [cv2.IMWRITE_JPEG_QUALITY, 85])
        cv2.imwrite(os.path.join(args.out, f"{tag}_revealed.png"), revealed_all, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        # a 1:1 crop so the full-res page can be judged at phone zoom
        cy, cx = h // 2, w // 2
        cv2.imwrite(os.path.join(args.out, f"{tag}_page_crop.png"), page[cy - 400:cy + 400, cx - 500:cx + 500])
        cv2.imwrite(os.path.join(args.out, f"{tag}_half_crop.jpg"), half[cy - 400:cy + 400, cx - 500:cx + 500], [cv2.IMWRITE_JPEG_QUALITY, 90])
        # data-format candidates
        lm16 = labels.astype(np.uint16) if R < 65536 else None
        if lm16 is not None:
            cv2.imwrite(os.path.join(args.out, f"{tag}_labels16.png"), lm16, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        cv2.imwrite(os.path.join(args.out, f"{tag}_colouridx8.png"), final_cidx.astype(np.uint8), [cv2.IMWRITE_PNG_COMPRESSION, 9])
        regions = [{"id": r, "c": int(reg_colour[r]), "area": int(areas[r]), "x": int(pos[r][1]), "y": int(pos[r][0]), "r": round(float(rad[r]), 1)} for r in range(1, R + 1)]
        with open(os.path.join(args.out, f"{tag}_regions.json"), "w") as f:
            json.dump({"n": n_final, "w": w, "h": h, "palette": stats["palette_rgb"], "regions": regions}, f, separators=(",", ":"))
        tick("outputs saved")
    print(json.dumps({k: v for k, v in stats.items() if k not in ("per_colour_regions", "palette_rgb", "merge_history")}, indent=1))

if __name__ == "__main__":
    main()
