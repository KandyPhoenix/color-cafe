# Region fill on line-art PNGs in canvas — findings

Ticket: `.scratch/color-cafe-spec/issues/02-region-fill-technique.md`
Date: 2026-10-19
Every number below comes from the scripts in this folder, run against the five pages in `/pages/`
(843x843 RGB PNGs). Raw outputs are the `*_output.txt` / `bench_*.json` files next to this document.
Browser timings are headless Chromium 1194 (Playwright) on this container's CPU; "4x throttle" is
Chrome's `Emulation.setCPUThrottlingRate(4)`, a rough stand-in for a mid-range phone — treat phone
numbers as order-of-magnitude, not measurements on real hardware.

## TL;DR recommendation for v1

**Pre-segment once at load, on the native 843px bitmap, into a label map; fill by label, not by
live flood fill. Threshold the fillable "core" at grey >= 200, then grow every label simultaneously
(multi-source BFS) into the anti-aliased halo down to grey >= 64. Render as: colour layer underneath,
original line-art PNG drawn on top with `globalCompositeOperation = 'multiply'`.**

- Load cost (decode + label + halo-grow + bboxes): **32–127 ms** unthrottled, **125–425 ms** at 4x
  throttle, per page, all five pages (`pipeline_output.txt`). One-time; can move to a Worker later.
- Fill cost: the largest region on a page (the background, 130k–258k px) paints and `putImageData`s
  in **4–24 ms** unthrottled, **16–112 ms** at 4x. A typical region (median 155 px) is < 0.2 ms.
- Zero leaks between regions at T=200 on native pixels; the halo growth leaves **no white sliver**
  between fill and line and cannot leak (regions grow together, so each halo pixel goes to whichever
  region reaches it first — a gap gets split, not crossed). See `img/halo_grow_multiply_crop.png`.
- Memory: `Uint16Array` label map = 1.4 MB at 843px (max regions per page is 2,868 < 65,535).
- Bonus: saved state becomes `{regionId: colour}` (a few KB) instead of a bitmap.

Do **not** segment on a canvas-upscaled (smoothed) bitmap, and do **not** use T=128: both leak
(numbers below).

## What the source pages actually look like

`analyze_pages.py`, `histogram_and_merge.py` (garden-gate.png unless noted; the other four are
within a few % on every metric, see `analysis_output.txt`):

| metric | value |
|---|---|
| pure black (0) / pure white (255) | 9.0% / 34.9% of pixels |
| grey 1–254 | **56.1%** of pixels |
| ...of which near-black (1–63) | 22.4% |
| ...near-white (192–254) | 24.9% |
| mid-grey band (32–223) | 15.8% |
| dark (<128) | 35.9% |
| peak grey levels | 0,1,2,3,5,6 and 249,250,251,253,254,255 |
| stroke half-width (distance transform on dark mask) | median 1.4 px, p90 2.2 px → strokes ~2–4 px |
| isolated dark specks (<5 px components) | 79 per page |

So "black" is really 0–6 and "white" is 249–255: the PNGs have been through resampling or lossy
compression. Any threshold must leave slack on both ends. **36% of pixels are line**, which matters
for tap targeting (below). The drawings are dense: thin strokes, hundreds of small cells
(`img/source_crop_6x.png`).

## Region counts by threshold (4-connected components of `grey >= T`)

Garden-gate; other pages in `analysis_output.txt`:

| T | regions | >= 50 px | < 10 px | largest region |
|---|---|---|---|---|
| 64 | 1418 | 767 | 199 | 24.1% of page |
| **128** | **1555** | 728 | 328 | 23.1% |
| 160 | 1670 | 721 | 441 | 22.5% |
| **200** | **1991** | **711** | 742 | 21.9% |
| 230 | 2635 | 706 | 1310 | 20.8% |
| 250 | 5774 | 666 | 4248 | 19.0% |

The JS labeler in `browser_bench.html` reproduces scipy exactly (1991 regions at T=200, 1555 at T=128).

Across all five pages at T=200: 1,651–2,106 regions; 1,127–1,309 of them are < 50 px but together
hold only **2.8–4.2% of fillable area** (`region_sizes_output.txt`). Median "real" (>= 50 px) region
is 146–202 px, i.e. about 12x12 native px.

## Leaks: lowering the threshold merges real regions

`histogram_and_merge.py`: take the 711 regions >= 50 px at T=200 as ground truth, then ask how many
distinct regions they collapse into at a looser threshold.

| loose T | garden-gate: 711 regions collapse into | leaks (regions swallowed) | sea-turtle (524 regions) |
|---|---|---|---|
| 160 | 668 | 80 | 58 |
| **128** | 650 | **109 (15%)** | 77 |
| 96 | 638 | 126 | 99 |
| 64 | 622 | 148 | 120 |

What the leaks are: in dense areas the core of a thin stroke is only mid-grey (~130–200), so at
T=128 it is "fillable". `img/garden-gate_regions_T128.png` vs `img/garden-gate_regions_T200.png`:
at T=128 the whole bird becomes one region (wing feathers merge with body) and the sky inside the
arch merges with the outside background; at T=200 they are separate. `img/butterfly_leak_T200_vs_T128.png`
shows wing cells (separate at T=200, centre panel) merging into one blob at T=128 (right panel).

**Conclusion: fillable core must be T ≈ 200.** 230 also works (zero lost regions, see below) but
fragments more.

## Upscaled bitmaps leak even at T=200

`upscale_leak.py`: resize 843 → 1500 the way `drawImage` with smoothing would, label at T=200, and
check whether the 711 native regions stay distinct (representative pixel = each region's
distance-transform maximum, i.e. deep interior).

| segmentation input | T=200 leaks | T=128 leaks |
|---|---|---|
| native 843 | **0** | 109 |
| 1500 nearest-neighbour | 0 | 109 |
| 1500 bilinear | **18 regions swallowed (9 groups)** | 119 |
| 1500 bicubic | **36 regions swallowed (17 groups)** | 122 |

Smoothing lightens thin dark cores above 200 and opens gaps. So: **segment on the native pixels**
(decode the PNG into an 843px canvas with no scaling, or use nearest-neighbour), and only upscale
for display.

## Anti-aliased edges: the halo problem and the fix

With a T=200 core and nothing else, **5.1% of the page** (36,552 px) is grey halo that is neither
filled nor line — a visible pale rim around every fill (`halo_gaps_output.txt`).

Fix measured in `halo_and_gaps.py` and timed in JS (`runPipeline` in `browser_bench.html`): after
labelling the core, grow all labels at once, one ring per BFS round, into pixels with
`grey >= T_HALO`. Because all seeds advance together, two regions separated by a mid-grey stroke
meet in the middle of the stroke and stop; nothing crosses.

| T_HALO | halo px assigned (garden-gate) | fillable px left unreached | remaining line core |
|---|---|---|---|
| 128 | 36,373 | 179 | 35.9% of page |
| **64** | 68,163 | 395 | 31.4% |
| 32 | 93,317 | 481 | 27.8% |

The unreached pixels are isolated grey specks inside line areas; they keep the PNG's own colour and
are invisible. `img/halo_grow_multiply_crop.png` / `..._full.png` are the result composited with the
line art via multiply: no white rims, strokes intact, no leaks. T_HALO=64 is the recommendation
(fills reach under the dark edge of the stroke, so even thin strokes have no light seam); 128 is
safer if a page ever has grey *shading* that must not be painted — none of the five do.

Cost of the grow step: 9–30 ms unthrottled, 37–81 ms at 4x, for 66k–108k pixels (`pipeline_output.txt`).

## Gaps in the outline

Two kinds show up; they need different handling.

**True gaps (rare).** `halo_and_gaps.py` erodes the T=200 mask by 1 px and looks at which
regions fall apart. The page background (155,576 px) is joined through a <= 2 px neck to **9 small
cells of 230–390 px** — leaf interiors whose outline does not quite close
(`img/background_gap_pieces_erode1.png`: the coloured specks). 14 regions on the page are affected in
total (43 pieces). Filling the sky also tints those nine cells.

**Open-ended strokes (by design, ambiguous).** Tightening the core (T=230, T=250, or 1 px erosion)
"fixes" the gaps but splits 65 / 120 / 93 regions respectively (`tighten_upscale_output.txt`), and 1
px erosion deletes 6–14 real regions outright (no core left). `img/splits_T230.png` and
`img/splits_erode1.png` show what the splits are: leaf veins and rose-petal strokes that stop short of
the edge, so the leaf is one region at T=200 and several vein-cells at T=230. Neither answer is wrong;
a tighter core trades ~10 true gaps for ~100 extra fragments and slivers. Not worth it.

**Recommendation:** accept T=200 behaviour in the app; fix true gaps in the art. The erosion check in
`halo_and_gaps.py` is a usable QA script — it lists regions joined only by a thin neck, so a page can
be checked (and the PNG touched up) before it ships. A later feature could offer a per-region
"split here" or an "eraser" for the user, but that is not v1.

## Performance (browser, `bench_summary.txt`)

Live scanline flood fill on an RGBA ImageData vs pre-labelled map, garden-gate, worst case = the
background region:

| size | op | unthrottled | 4x throttle |
|---|---|---|---|
| 843 | flood fill background, T=200 (156k px) | 1.8 ms | 7.4 ms |
| 843 | label whole page, T=200 | 28 ms (+4 ms bboxes) | 73 ms (+16) |
| 843 | fill background by label + full putImageData | 2.5 ms | 9.9 ms |
| 1500 | flood fill background, T=200 (481k px) | 9.5 ms | 32 ms |
| 1500 | label whole page | 61 ms (+13–110 bboxes*) | 151 ms (+51) |
| 1500 | fill background by label | 11 ms | 35 ms |
| 2000 | flood fill background (855k px) | 12 ms | 53 ms |
| 2000 | label whole page | 67 ms | 249 ms |
| 1500 | draw colour layer + line art (multiply), per frame | 0.97 ms | 3.75 ms |
| 2000 | same | 1.46 ms | 6.6 ms |

\* one outlier (110 ms) in the 1500 bbox pass; the other runs were 11–23 ms. GC noise — timings in
this harness vary ~2x run to run; read them as magnitudes.

Takeaways: a live flood fill at 1500 px is fast enough (tens of ms on a slow device), so speed is
*not* the reason to pre-segment. The reasons are correctness (no leaks, halo handled once, no
per-tap tolerance heuristics), a tiny saveable state, trivial undo/redo and "fill all of colour X"
features, and that the hit-test for a tap is a single array lookup. Pre-segmenting at native 843 is
also 2–4x cheaper than at 1500.

Compositing cost is negligible: redraw the whole page every frame if convenient (Puzzle Parlor
already does a full redraw per frame).

## Rendering so the lines stay crisp

- Keep two canvases: `colour` (native 843px, RGBA, written via `putImageData` of the touched region's
  bbox only) and the decoded `lineArt` image. On each frame draw white, then `colour` scaled to the
  view, then `lineArt` scaled to the view with `multiply`. Multiply makes the PNG's white transparent
  and its black opaque, and its grey edge pixels darken the colour underneath proportionally — the
  stroke keeps the PNG's own anti-aliasing at whatever zoom the user is at. Measured at 1–7 ms per frame.
- Because fills extend under the stroke (halo growth), scaling the 843px colour layer up with
  smoothing is fine: its soft edges are hidden under the line.
- Draw at `devicePixelRatio` like Puzzle Parlor (`cv.width = clientWidth * dpr`). Lines will be as
  crisp as an 843px source allows; beyond ~2x zoom they go soft. True crispness at any zoom would need
  vector (SVG) sources — out of scope for v1, but a reason to keep masters at higher resolution.
- Line-art pixels are never painted, so "paint over the lines" cannot happen.

## Touch targeting (from the numbers, not measured on a device)

- 36% of the page is line. On an unzoomed phone (843 px drawn at ~390 CSS px, 0.46x), the median
  region is ~5.5 CSS px wide and the typical stroke ~1.5 CSS px. A naive "fill the pixel under the
  finger" will often land on a line or the wrong cell.
- Resolve a tap by converting to native coordinates and taking the label there; if it is 0 (line),
  search outward a few native px (3–4 at 1x, less when zoomed) for the nearest non-zero label. The
  halo growth already makes the label map cover everything except the stroke core, so this radius is
  small.
- Pinch-zoom is required, not optional — reuse the Puzzle Parlor camera/`touch-action:none` setup.
- The 1,100–1,300 regions under 50 px are mostly slivers between double strokes. Let them be filled
  when hit (so "fill the sky" reaches them via the gap cells, and a zoomed-in user can colour them),
  but they are not worth any special UI.

## Approaches considered

| approach | verdict |
|---|---|
| **A. Live flood fill on the display bitmap** (paint-bucket with a tolerance) | Fast enough (9–50 ms at 1500) but leaks on smoothed upscales, needs a tolerance that fights the 0–6 / 249–255 noise, leaves halos unless followed by a dilation pass per tap, and state is a bitmap. Rejected. |
| **B. Pre-segment at load on native pixels (core T=200, halo grow to 64), fill by label, multiply line art on top** | **Recommended.** 32–127 ms load, fills in ms, no leaks, no halos, JSON state. |
| C. Same as B but segment offline and ship a label map per page | Saves the 100–400 ms load but doubles asset size and adds a build step and a format; not needed at these timings. Revisit if pages go to 2000+ px or load in a Worker is still too slow. |
| D. Tighten the core (T=230–250 / erosion) to close outline gaps | Fixes ~10 small gap cells per page, creates ~65–120 fragments and deletes 6–14 real regions. Rejected; fix gaps in the art with the QA script instead. |
| E. Vector (SVG) regions | Crisp at any zoom, trivial hit-testing, but needs different source assets. Not for v1. |
| F. Freehand brush clipped by the line mask | Not asked for in v1; the multiply compositing in B supports it later with no change to the line layer. |

## Concrete v1 pipeline

1. `drawImage(png, 0, 0)` into an offscreen 843px canvas (no scaling), `getImageData`, take the R
   channel into a `Uint8Array grey`.
2. Two-pass union-find labelling of `grey >= 200`, 4-connectivity, into a `Uint16Array labels`
   (code in `browser_bench.html: labelRegions`).
3. Multi-source BFS: seed from every labelled pixel adjacent to an unlabelled pixel with
   `grey >= 64`; grow (`runPipeline` in `browser_bench.html`).
4. Per-label bounding boxes and pixel counts.
5. On tap: native (x,y) → label (radius search if 0) → set `colourOf[label]` → paint the bbox into the
   colour layer → `putImageData(bbox)` → redraw frame (white, colour layer scaled, line art scaled with
   multiply).
6. State = page id + `colourOf` (array of 2–3k entries) + undo stack of `[label, prevColour]`.

Steps 1–4 can later move into a Worker (transfer `grey`, get `labels` back) if phone load times feel
slow; at the measured 125–425 ms it is acceptable on the main thread behind the page-open animation.

## Open questions / limits of this research

- Real-device timings were not taken; the 4x throttle is a proxy.
- Only garden-gate was checked visually for leaks/gaps; the other pages were checked numerically
  (region counts, size distributions) and behave the same.
- If future pages carry grey shading or textures (not just strokes), T_HALO=64 would paint over it;
  switch to 128 or make it per page.

## Files

- `analyze_pages.py` — histogram, region counts by threshold (`analysis_output.txt`)
- `histogram_and_merge.py` — grey peaks, stroke width, threshold-merge/leak test (`merge_output.txt`)
- `halo_and_gaps.py` — halo growth simulation, erosion/neck gap test (`halo_gaps_output.txt`)
- `tighten_and_upscale.py`, `upscale_leak.py` — cost of tighter cores; leaks on upscales
- `render_labels.py`, `show_splits.py` — the images in `img/`
- `browser_bench.html` + `run_browser_bench.mjs` + `print_bench.py` — flood fill vs label timings at
  843/1500/2000 (`bench_throttle1.json`, `bench_throttle4.json`, `bench_summary.txt`)
- `run_pipeline.mjs` — the recommended pipeline timed on all five pages (`pipeline_output.txt`)
