#!/usr/bin/env python3
"""Round-trip check of the recommended app data format:
  labels.png  : 8-bit RGB PNG, region id = R + 256*G (browser-canvas safe; 16-bit grey PNGs get flattened to 8-bit)
  regions.json: palette + per-region colour index, number position, inscribed radius, area
  original.jpg: the painting (what the app reveals)
Rebuilds outlines + the fully revealed image from those three files only."""
import sys, json, os, numpy as np, cv2
tag, out = sys.argv[1], sys.argv[2]
orig_path = sys.argv[3]
lm = cv2.imread(f"{out}/{tag}_labels16.png", cv2.IMREAD_UNCHANGED).astype(np.uint32)
rgb = np.zeros(lm.shape + (3,), np.uint8)
rgb[..., 2] = lm & 255; rgb[..., 1] = lm >> 8          # cv2 is BGR: put R in [2], G in [1]
cv2.imwrite(f"{out}/{tag}_labels_rgb.png", rgb, [cv2.IMWRITE_PNG_COMPRESSION, 9])
print("labels_rgb.png bytes", os.path.getsize(f"{out}/{tag}_labels_rgb.png"))
# --- load back as the app would
back = cv2.imread(f"{out}/{tag}_labels_rgb.png", cv2.IMREAD_COLOR).astype(np.uint32)
ids = back[..., 2] + 256 * back[..., 1]
assert np.array_equal(ids, lm), "label round-trip failed"
meta = json.load(open(f"{out}/{tag}_regions.json"))
assert len(meta["regions"]) == ids.max() and ids.min() == 1
colour_of = np.zeros(ids.max() + 1, np.int32)
for r in meta["regions"]: colour_of[r["id"]] = r["c"]
pal = np.array(meta["palette"], np.uint8)[:, ::-1]   # RGB -> BGR
orig = cv2.imread(orig_path, cv2.IMREAD_COLOR)
assert orig.shape[:2] == ids.shape
# outlines derived at runtime from the label map
edge = np.zeros(ids.shape, bool); edge[:, :-1] |= ids[:, :-1] != ids[:, 1:]; edge[:-1, :] |= ids[:-1, :] != ids[1:, :]
print("outline pixels", int(edge.sum()), f"({edge.mean()*100:.2f}%)")
# simulate play: reveal every region -> must equal the original exactly
page = np.full(orig.shape, 255, np.uint8); page[edge] = 90
revealed = np.where((ids > 0)[..., None], orig, page)
print("fully revealed == original:", np.array_equal(revealed, orig))
# hit-test sanity: the number position of every region lies inside that region
pos_ok = all(ids[r["y"], r["x"]] == r["id"] for r in meta["regions"])
print("every number position inside its own region:", pos_ok)
# flat preview from palette (what a 'hint' view could show)
flat = pal[colour_of[ids]]
print("regions", len(meta["regions"]), "palette", len(pal), "flat preview ok", flat.shape == orig.shape)
