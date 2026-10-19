# Research: turning Puzzle Parlor art into coloring-page line art

Ticket: `.scratch/color-cafe-spec/issues/03-line-art-from-puzzle-art.md`
Date: 2026-10-19
Outputs and script: this directory (`research/line-art/`). Nothing was committed.

## Question

Can the 2912px colour puzzle JPGs in `puzzle-parlor` be converted *automatically* into
clean coloring pages with closed regions, comparable to the ChatGPT-made pages in
`color-cafe/pages/*.png` (843x843, pure black outlines on white, every area enclosed)?

## Short answer

**No, not with the tooling in this environment.** Every automatic method produced either
(a) open, noisy, wobbly lines that are at best a tracing reference, or (b) closed regions
that no longer depict the subject. None is colorable as-is. The practical path is to
re-render each scene as line art with an image model (ChatGPT / the same pipeline that made
the five existing pages), using the puzzle art as the reference image. Prompt below.

## What is installed (checked, not assumed)

| Tool | Present? | Notes |
|---|---|---|
| Pillow 12.3.0, numpy 2.5.3 | yes | |
| OpenCV 5.0.0 (`cv2`) incl. `cv2.ximgproc` namespace | yes | used for everything below |
| scikit-image | **no** | `ModuleNotFoundError` |
| scipy | **no** | `ModuleNotFoundError` |
| potrace / mkbitmap / vtracer / inkscape | **no** | nothing on PATH |
| ImageMagick 6.9.12 (`convert`) | yes | no vectoriser; IM6 cannot trace |

So "potrace / vectorise" could not be tried here. Note potrace only converts an existing
bitmap into vector paths; it does not decide where the lines go, so it would not fix the
open-region problem shown below, only make the result scalable.

## Sources used

- `puzzle-parlor/queue/img/treasure-cove.jpg` (2912x2188) - busy AI-rendered scene, pirates, ship, skull cave.
- `puzzle-parlor/public/img/pine-forest.jpg` (3000x2033) - painterly forest with bears (soft edges, low contrast).

Both were processed at 1456px wide (half size, `INTER_AREA`) so a 3px line reads as a
coloring-page line rather than a hairline. Reference page used for the stats baseline:
`pages/sea-turtle-treasure.png`.

## Methods tried (all in `lineart.py`, run with `python3 lineart.py`)

1. **Canny edges** - bilateral filter -> `cv2.Canny(60,160)` -> 3x3 dilate, inverted.
2. **XDoG** (Winnemoeller thresholded difference-of-Gaussians, sigma 1.0, k 1.6, p 18, eps 0.72).
3. **"Pencil sketch"** - grayscale colour-dodged against its blurred inverse, thresholded at 235.
4. **Posterize + trace boundaries** - `pyrMeanShiftFiltering` -> k-means to 12 colours ->
   absorb components under 400px into neighbours -> draw label boundaries. Regions are closed
   *by construction*. Also a coarse variant (6 colours, min region 2500px).
5. **Combo** - posterize boundaries (closed) unioned with Canny detail.

## Measured closed-region stats (`region-stats.json`)

"Regions" = 4-connected white components. "Largest region %" = share of all white pixels in the
single biggest component; a leaky page has one huge component because colour would flood
between areas. The ChatGPT reference sits at 52.7% because its outer background is one
legitimately large region, so the number only means something together with the visual check.

| Output file | regions | regions > 500px | largest region % | black % |
|---|---|---|---|---|
| REF `pages/sea-turtle-treasure.png` | 1150 | 114 | 52.7 | 32.3 |
| `treasure-cove--canny.png` | 3092 | 95 | 25.0 | 26.7 |
| `treasure-cove--xdog.png` | 7008 | 57 | 51.0 | **71.6** |
| `treasure-cove--pencil.png` | 4552 | 127 | 58.2 | 36.3 |
| `treasure-cove--posterize.png` | 1537 | 412 | 3.8 | 23.0 |
| `treasure-cove--posterize-coarse.png` | 631 | 108 | 9.4 | 12.7 |
| `treasure-cove--combo.png` | 3766 | 339 | 3.6 | 33.3 |
| `pine-forest--canny.png` | 723 | 5 | **98.9** | 8.7 |
| `pine-forest--xdog.png` | 11768 | 19 | 11.9 | **84.0** |
| `pine-forest--pencil.png` | 11770 | 53 | 80.5 | 31.0 |
| `pine-forest--posterize.png` | 1185 | 315 | 6.4 | 21.0 |
| `pine-forest--combo.png` | 1437 | 275 | 5.8 | 21.6 |

## Verdict per method (visual inspection at full res and 900px)

**1. Canny** - `treasure-cove--canny.png`, `pine-forest--canny.png`
- Lines: jittery, double-edged, broken; thousands of specks where the texture is busy (foliage, treasure pile) and nothing at all where contrast is soft.
- Regions: open. Pine forest is 98.9% one region, i.e. a flood fill would paint the whole page.
- Colorable? **No.** Treasure cove is a recognisable *reference* (you can tell it is pirates and a ship); pine forest is not even that.

**2. XDoG** - `*--xdog.png`
- Produces a scratchboard / woodcut engraving with 70-84% black. Handsome as an illustration style, but it is tonal rendering, not outlines.
- Colorable? **No.** Wrong product entirely.

**3. Pencil sketch** - `*--pencil.png`
- Most "drawn-looking" of the set and the most legible reference (faces, rigging, map all readable), but it is cross-hatched etching texture everywhere; the "lines" are dense stipple, not strokes, and there are no clean white areas to colour.
- Colorable? **No.** Best candidate as a *tracing reference* for a human artist.

**4. Posterize + boundaries** - `*--posterize.png`, `treasure-cove--posterize-coarse.png`
- Regions are genuinely closed (largest region only 3.8-9.4%) and the line is a consistent 3px, so mechanically it is the only output that behaves like a coloring page.
- But the regions follow colour clusters, not objects: the pirate's face is a blob, the ship dissolves into sky-coloured patches, foliage becomes a cloud of ragged islands. At 6 colours the scene is unrecognisable. Edges are staircase/wobbly from the mean-shift.
- Colorable? **Mechanically yes, artistically no.** Looks like an abstract contour map, not an illustration.

**5. Combo** - `*--combo.png`
- Closed regions from posterize plus Canny detail. Marginally the most readable of the closed-region outputs, but it inherits both sets of faults: blobby boundaries *and* speckle. Still far from the clean, confident stroke of the ChatGPT pages.
- Colorable? **No.**

## Why automatic extraction fails here (not just a tuning problem)

- The puzzle art is fully rendered: lighting, gradients, texture, atmosphere. A coloring page is a *redrawing* that keeps only semantic contours (object outlines, major folds) and discards shading. Edge/threshold filters have no notion of "object" and cannot tell a shadow edge from a silhouette edge.
- Region-based methods (posterize) give closure but segment by colour, so one object splits into many regions and adjacent same-coloured objects merge.
- Line quality: filters produce 1px, double or ragged edges; the reference pages have a uniform, deliberate ~3-5px stroke with rounded ends. Vectorising (potrace) would smooth but not fix topology.
- The pine-forest result shows the painterly/fine-art puzzle images are the worst case: low local contrast means almost no edges at all.
- Tuning thresholds trades speckle against gaps; no setting gave both clean lines and closed regions on either image.

Deep-learning approaches (e.g. HED / "Anime2Sketch" / informative-drawings models) do better than
classical filters but are not installed here, still produce open sketches rather than closed
coloring regions, and would need manual cleanup. Not tested; stated as a limitation, not a finding.

## Recommendation

1. **Generate, don't convert.** Re-render each scene as line art with an image model using the
   puzzle JPG as the reference image, exactly as the five existing `pages/*.png` were made.
   Budget for 1-3 attempts per page and a human pass (spell-check any text, check closure).
2. Keep `lineart.py` only as a utility for a *quick reference overlay* if an artist ever hand-traces;
   do not build the product pipeline on it.
3. If a pure-code path is still wanted later, the only mechanically sound building block is the
   posterize/region approach, and it would need a segmentation model (object-aware, not
   colour-aware) in front of it plus vector smoothing. That is a project, not a script.
4. Add a small automatic QA step to whatever pipeline is chosen: binarise the page and run
   `region_stats()` (in `lineart.py`) to flag pages with one dominant region or hairline gaps
   before they ship.

## ChatGPT re-render prompt (alternative method)

Attach the puzzle JPG and use:

> Redraw this scene as a black-and-white adult coloring book page. Keep the same composition,
> characters and main objects, but render it as clean, uniform black outline art only:
> no shading, no hatching, no grey, no gradients, no color. Every shape must be a fully
> closed region with a solid white fill so it can be colored in. Use a consistent medium
> line weight, simplify fine textures (foliage, water, fur) into decorative repeating
> shapes, and leave the sky/background largely open. Square 1:1 format, pure white background,
> no text, no signature, no border.

Follow-ups that fix the usual misses: "thicker, more uniform lines", "close the gaps in the
outlines so every area is enclosed", "remove all shading and hatching", "simplify the
background". Request the output at the largest size available and keep the 843px-square
convention used by the existing pages (or downscale to it) so the app sees a consistent set.

## Files in this directory

- `lineart.py` - the five methods + `region_stats()`; reproduces every PNG here.
- `region-stats.json` - the table above.
- `treasure-cove--{canny,xdog,pencil,posterize,posterize-coarse,combo}.png`
- `pine-forest--{canny,xdog,pencil,posterize,combo}.png`
