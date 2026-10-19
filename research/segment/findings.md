# Research: splitting a painting into numbered color-by-number regions

Ticket: `.scratch/color-cafe-spec/issues/11-segment-painting-into-regions.md`
Date: 2026-10-19. Environment: Python 3, OpenCV 5.0.0, Pillow 12.3, numpy 2.5.3, scipy 1.18.1
(scipy was already installed; nothing was pip-installed). scikit-image not available, not needed.

Note: the ticket pointed at `research/region-fill/findings.md` and `research/line-art/findings.md` for
reusable ideas; neither file (nor `research/`) exists in this checkout, so everything below was built
from scratch.

Everything here was run for real on both source paintings (2912 x 2176 px):
`puzzle-parlor/public/img/haunted-village.jpg` and `witch-kitchen.jpg`.
Scripts: `segment.py` (pipeline), `run_matrix*.sh` (parameter sweeps), `verify_format.py`
(round-trip check of the recommended app format). Outputs in `out/`.

## TL;DR

- A fully automatic pipeline works: ~15 s per 2912 px page, 550-700 regions, every region at least
  900 px2 with an inscribed radius of at least 8 px, and the fully revealed result is byte-identical
  to the original painting (asserted in code, both paintings).
- The hard part was not quantisation but what happens after it: these painterly images have
  135k-300k colour islands, and merging the sub-tappable ones turns ~45 % of the painting into one
  near-black region. Fixed with (a) stronger edge-preserving smoothing before quantising and (b) a
  post-merge split of any region over 3 % of the image along real texture edges.
- N = 24 feels right for this kind of dark painting. N = 36 spends 13 of its 36 slots on near-black
  shades that players cannot tell apart; it adds ~15 % more regions and no visible fidelity.
- The outline page is recognisable (moon, castle, pumpkins, cauldron, window, book, broom read
  clearly) but it is an "organic blob" page, not a crisp line drawing, because the source art has no
  line work. The half-revealed view is the satisfying part. Flat-shaded / cel-style source art would
  give much better pages; see Limitations.

## Pipeline (what `segment.py` does)

1. **Smoothing (edge-preserving).** `cv2.bilateralFilter`, 3 passes, d = 11, sigmaColor = 50,
   sigmaSpace = 9 ("strong"). Also tried: none, 2 lighter bilateral passes ("bilateral"), and
   `cv2.pyrMeanShiftFiltering` at half resolution (sp = 8, sr = 20) upsampled back.
   Purpose: flatten brush texture so the quantiser produces islands, not confetti.
2. **Quantise to N colours in CIE Lab.** `cv2.kmeans` (k-means++ init, 5 restarts) on a 200k-pixel
   random sample of the smoothed image converted with `COLOR_BGR2LAB` on float input (true L* 0-100
   scale; the 8-bit Lab conversion scales L* by 2.55 and over-weights luminance). Every pixel is then
   assigned to its nearest centroid in chunks of 1M. Palette sorted dark to light so number 1 is the
   darkest colour.
   An optional adaptive step (`--max-share`) re-splits any palette colour that owns more than X % of
   pixels. It turned out not to matter (see "What went wrong first").
3. **Connected components per colour.** `cv2.connectedComponentsWithStats`, 4-connectivity, run once
   per palette colour and offset into one global int32 label map.
4. **Merge sub-tappable regions.** A region is "small" if area < `min_area` OR its inscribed radius
   (max of the distance transform inside it) < `min_radius`. The inscribed-radius test matters: a long
   1-px sliver can have a large area but is untappable and has nowhere to put a number.
   Each small region merges into the touching neighbour maximising
   `shared_border_length / (1 + deltaE(colour_a, colour_b))`, with a 0.5 penalty if the neighbour is
   itself small. The merge graph is forced acyclic (only merge into a strictly larger region, ties by
   id) and chains are collapsed by pointer-jumping, then the colour index map is rewritten and the
   components recomputed. Converges in 3 passes. Without the acyclic rule adjacent small regions swap
   colours forever (first attempt: 12 passes, still 14k single-pixel regions).
5. **Split giant regions** (`--max-share-region 0.03`). Any region bigger than 3 % of the image is cut
   into ceil(area / 3 %) chunks with a SLIC-style k-means on (x, y, L*, a*, b*) of the *original*
   pixels (spatial weight 12 / chunk side), so cuts follow real content edges (trunk vs sky) rather
   than a grid. Chunks keep the parent's palette number; chunk slivers below `min_area` or
   `min_radius` are merged into the chunk sharing the longest border. Adjacent regions with the same
   number are normal on Happy-Color pages.
6. **Outlines.** A pixel is an edge if its right or down neighbour has a different label. Rendered as
   a 2-px grey line on white. This is derived from the label map, so the app can compute it at
   runtime instead of shipping a page image.
7. **Number placement.** `cv2.distanceTransform` on the non-edge mask, then
   `scipy.ndimage.maximum_position` per label gives each region's most interior point in one call.
   Font size scales with the inscribed radius; because every surviving region has radius >= 8 px,
   every region got a number (548/548, 581/581, 636/636, 689/689).
8. **Reveal.** Revealed pixels are copied from the original. `np.array_equal(revealed_all, orig)` is
   asserted on every run and re-checked from the serialised files by `verify_format.py`.

## Numbers

Timing is a single clean run on one core (nothing else running); the sweep logs show higher numbers
because three runs shared four cores.

haunted-village, N = 24, strong smoothing, min_area 900, min_radius 8, split 3 %:

| stage | time |
|---|---|
| load | 0.1 s |
| smoothing (3x bilateral) | 0.8 s |
| k-means + assign 6.3M px | 2.0 s |
| raw components (134,916 regions, 134,081 below 900 px2) | 0.7 s |
| merge, 3 passes -> 487 regions | 4.6 s |
| giant split (63 chunks) -> 548 regions | 6.5 s |
| page render + numbers | 0.1 s |
| **compute total** | **14.8 s** |
| writing all sample files (incl. 11 MB lossless PNG) | 5.5 s |

Mean-shift smoothing adds ~7 s at half resolution; not worth it (see sweep).

Final configurations (all: strong smoothing, min_area 900, min_radius 8, split at 3 %):

| run | palette | regions | largest region | smallest area / radius | median area | regions r < 12 px | outline px | mean dE76 flat vs original |
|---|---|---|---|---|---|---|---|---|
| haunted-village N=24 | 24 | 548 | 5.7 % | 901 px2 / 8.0 px | 3,352 px2 | 82 | 3.5 % | 16.6 |
| haunted-village N=36 | 36 | 636 | 6.5 % | 905 / 8.0 | 3,709 | 92 | 3.7 % | 16.5 |
| witch-kitchen N=24 | 24 | 581 | 5.6 % | 901 / 8.0 | 3,507 | 84 | 3.7 % | 13.2 |
| witch-kitchen N=36 | 36 | 689 | 4.6 % | 922 / 8.4 | 3,951 | 92 | 4.0 % | 13.0 |

"mean dE76 flat vs original" = mean CIE76 distance between the flat palette render and the painting;
it says how much texture the palette throws away, not how good the page is (the app reveals original
pixels, so the player never sees the flat render unless we add a hint view).

Sweep before the giant split was added (bilateral = 2 light passes; a/r = min_area / min_radius):

| run | regions | largest region | note |
|---|---|---|---|
| hv N=24 none a400 r6 | 803 | 52.6 % | no smoothing: 218k raw islands |
| hv N=24 bilateral a400 r6 | 933 | 45.7 % | first baseline, sample files kept |
| hv N=24 meanshift a400 r6 | 1,056 | 36.2 % | best dE (14.2) but +7 s |
| hv N=36 bilateral a400 r6 | 1,105 | 24.2 % | |
| hv N=24 bilateral a1600 r10 | 245 | 57.2 % | too coarse: 245 regions is a toddler page |
| hv N=36 bilateral a900 r8 | 537 | 41.8 % | |
| hv N=24 bilateral a900 r8, max-share 12 % | 460 | 43.7 % | adaptive palette split did nothing useful |
| hv N=24 strong a900 r8, max-share 12 % | 517 | 37.6 % | strong smoothing helps |
| wk N=24 bilateral a400 r6 | 1,047 | 22.6 % | baseline, sample files kept |
| wk N=36 bilateral a900 r8 | 569 | 36.7 % | |
| wk N=24 strong a900 r8, max-share 12 % | 549 | 20.7 % | |

### What went wrong first, and why it matters for the content tool

The darkest palette colour owns only ~33 % of pixels after k-means, yet the final black region was
42-50 % of the painting at every N and every smoothing. The growth comes from the **merge**: the dark
half of these paintings is texture (bark, cobbles, shadowed foliage) whose colour islands are almost
all under 900 px2, and each one's best neighbour is the big black region. Re-splitting the palette
(`--max-share`) cannot fix that: the dark cluster is tight (sub-split deltaE 5-6) and the fragments
merge away again. The post-merge geometric split is the fix that worked: largest region went from
42-50 % to 4.6-6.5 % with 31-63 extra chunks.

### Tappability yardsticks

At 2912 px wide, fit-to-width on a 390 CSS px phone is a 7.5x reduction. 900 px2 (30 x 30) is 4 CSS px
unzoomed and 16 CSS px at 4x zoom; an inscribed radius of 8 px is a 2.1 CSS px half-width unzoomed,
8.5 CSS px at 4x. That is Happy-Color territory (their fiddly bits need 4-8x zoom too). 82-92
regions per page still have radius < 12 px; raising `min_radius` to 12 would remove the fiddliest
~15 % of regions at the cost of more merging in the detailed areas. Worth exposing as a per-page knob
in the content tool.

## Does it look like a satisfying color-by-number page?

Sample files (all under `out/`, 1456-px previews unless noted; `*_page_full.png` is full 2912 px):

| file | what |
|---|---|
| `haunted-village_n24_strong_a900_r8_split3_page.png` | outline + numbers page (recommended config) |
| `haunted-village_n24_strong_a900_r8_split3_page_crop.png` | 1000 x 800 crop at 1:1 from the page centre |
| `haunted-village_n24_strong_a900_r8_split3_palette.png` | the 24-colour palette, numbered |
| `haunted-village_n24_strong_a900_r8_split3_labelvis.jpg` | label map painted with its palette colours |
| `haunted-village_n24_strong_a900_r8_split3_labels16.png` | label map, 16-bit grey PNG (region id) |
| `haunted-village_n24_strong_a900_r8_split3_labels_rgb.png` | label map, 8-bit RGB PNG, id = R + 256 G (app format) |
| `haunted-village_n24_strong_a900_r8_split3_half.jpg` | darker half of the palette revealed over the page |
| `haunted-village_n24_strong_a900_r8_split3_revealed.png` | everything revealed; byte-equal to the original |
| `haunted-village_n24_strong_a900_r8_split3_regions.json` | palette + per-region metadata (app format) |
| same set with `n36` | N = 36 comparison (no revealed.png; identical by construction) |
| same two sets for `witch-kitchen_*` | second painting |
| `haunted-village_n24_bilateral_a400_r6_*`, `witch-kitchen_n24_bilateral_a400_r6_*` | first baseline (giant black region, 400 px2 minimum) for comparison |
| `*.json` (no suffix) | per-run stats for every sweep run, incl. merge history |

Honest assessment:

- **The half-revealed view is the product.** Revealed regions show real painting pixels, so the
  moment a player taps the moon or a pumpkin they get the actual art, and the un-revealed white
  shapes with numbers read as "what's left". That looks exactly like a Happy Color page mid-play.
- **The pure outline page is medium.** Silhouettes carry it: the moon with witches, the castle,
  the ghosts, the jack-o-lanterns, the cauldron, the round window, the spell book and broom are all
  identifiable without the colours. But the regions between them are wobbly amoebas (the shape of
  brush texture after smoothing), not the clean cartoon shapes of a drawn colouring page. Nothing in
  the pipeline can invent line work the painting does not have.
- **The giant-split cuts are visible** as a few straight-ish seams in flat dark areas (e.g. the
  witch-kitchen lower right, the haunted-village sky). They are the price of not having one 45 %
  region; tolerable, and they follow texture where there is any.
- **N = 24 vs 36.** With N = 36, 13 palette colours have L* < 20 (vs 6 at N = 24) and the closest
  pair is deltaE 4.5-6.7 apart; players would be guessing between 1, 3, 5, 8. N = 36 produces 15-19 %
  more regions and a mean dE improvement of 0.1. N = 24 is the better page for dark paintings;
  brighter, flatter art could use 28-32. A follow-up worth doing: merge palette centroids closer
  than deltaE ~8 after k-means (and let N float), rather than fixing N.

## Limitations

- Only two paintings tested, both dark, painterly, AI-generated scenes with no line work. These are
  close to the worst case for this pipeline. Flat-shaded or cel-style art (the Happy Color house
  style) would quantise into far fewer, cleaner islands and need little merging; worth generating a
  test image in that style before locking parameters.
- Region shapes are organic, not drawn; there is no edge simplification. Smoothing the label-map
  boundaries (e.g. morphological open/close per region, or rendering outlines from a simplified
  contour) would make the page look more hand-drawn. Not attempted.
- Merge choice uses border length and colour distance only. It can glue a small bright highlight
  into the wrong neighbour if the shared border is long; visually this shows as a few windows and
  stars that vanished into their surroundings.
- `min_area` / `min_radius` are in source pixels; they should really be set from the intended
  display size and max zoom. Values above are tuned for 2912 px sources on a phone with ~4-8x zoom.
- k-means uses a random sample with a fixed seed (reproducible), so a re-run with a different seed
  gives a slightly different palette and region set. The content tool should store the output, not
  regenerate on the fly.
- The giant split's SLIC k-means is not balanced, so chunks end up 1.5-2x the 3 % target (largest
  region 4.6-6.5 %). Acceptable; a strict cap would need a balanced assignment step.
- Timing is for a desktop CPU in this container; the merge and giant-split steps (~11 s of ~15 s) are
  pure numpy and would be the first things to optimise if the tool has to run on a laptop in bulk.

## Recommended data format for the app

Per page, three files (sizes are the haunted-village N = 24 result, 2912 x 2176):

| file | content | size |
|---|---|---|
| `original.jpg` | the painting, what the app reveals | 1.86 MB as shipped in Puzzle Parlor (1.35 MB as WebP q85) |
| `labels.png` | 8-bit **RGB** PNG, full resolution, region id = `R + 256 * G` (B unused, alpha opaque) | 294 KB (298 KB for witch-kitchen) |
| `regions.json` | palette + one record per region | 31 KB raw, 8 KB gzipped |

Total about 2.2 MB per page, dominated by the painting we ship anyway.

Why RGB and not 16-bit grey: browsers flatten 16-bit PNGs to 8 bits when drawn to a canvas, and
`getImageData` is the only way the app can read the map. Packing the id into two 8-bit channels of an
opaque RGB image survives the canvas exactly (verified by `verify_format.py`, which reloads the PNG,
rebuilds the id map, and asserts it equals the int32 labels). Keep alpha at 255 everywhere:
premultiplied alpha would corrupt channel values. The 16-bit grey PNG is 284 KB, so RGB costs nothing.

Why full resolution: a half-resolution label map (nearest-neighbour upsampled) mismatches 1.77 % of
pixels, all along region edges, and only saves ~170 KB. Reveal edges would visibly disagree with
outlines at zoom.

Why not just an 8-bit colour-index map: after the giant split, adjacent regions can share a colour,
so regions cannot be recovered from the colour index by connected components. The 8-bit index PNG is
186 KB (111 KB WebP lossless), so it saves little anyway.

`regions.json` schema (as written by `segment.py`):

```json
{
  "n": 24, "w": 2912, "h": 2176,
  "palette": [[8,5,8], [33,15,14], ...],           // RGB, index 0 = number 1, sorted dark -> light
  "regions": [
    {"id": 1, "c": 0, "area": 3019, "x": 1412, "y": 388, "r": 14.2},
    ...
  ]
}
```

`id` is the label-map value (1-based, 0 is unused), `c` the palette index, `(x, y)` the most interior
point where the number goes, `r` the inscribed radius in px (drives number font size and can drive
"zoom to fit" when the player picks a colour), `area` for progress and ordering.

What the app derives at runtime from `labels.png` (all cheap, one pass over 6.3M pixels):

- outlines: pixel is an edge if its right or down neighbour has a different id (3.5-4 % of pixels);
- hit testing: `id = labels[y][x]` under the tap;
- reveal: copy `original` pixels where `labels == id`, or keep a per-region mask list built once;
- per-colour region lists and progress: group `regions` by `c`.

Optional extras the tool could emit if runtime cost matters on low-end phones: the rendered page
PNG (`*_page_full.png`, 608 KB) and per-region bounding boxes (add `bbox` to each record).

## Recommended pipeline settings for the content tool

`python3 segment.py painting.jpg --n 24 --smooth strong --min-area 900 --min-radius 8 --max-share-region 0.03 --save-all`

with `--n`, `--min-radius` and `--max-share-region` exposed per page, and the three app files
(`labels_rgb.png`, `regions.json`, original) as the deliverable. Review each page's `_page.png` and
`_half.jpg` by eye before release; the sweep JSON (`regions_final`, `largest_area`,
`regions_radius_lt_12`) makes a decent automatic sanity gate (target 400-800 regions, largest < 8 %,
fewer than ~100 regions under 12 px radius).
