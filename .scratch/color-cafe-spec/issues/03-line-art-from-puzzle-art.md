# Research: turning Puzzle Parlor art into coloring pages

Type: research
Status: resolved
Blocked by: 

## Question

Can the existing colour puzzle images (2912px JPGs in puzzle-parlor/img) be converted automatically into clean coloring-page line art with closed regions? Evaluate practical methods available in this environment (edge detection + thresholding, posterize + trace, potrace/vectorising, or asking ChatGPT to re-render as line art). Try at least one method on one puzzle image, save the result under research/, and judge whether the output is good enough to color or only good enough as a reference.

## Answer

Findings: branch `research/line-art`, file `research/line-art/findings.md` (11 sample PNGs, region-stats.json, lineart.py).

- Five automatic methods tried on treasure-cove and pine-forest (Canny, XDoG, pencil sketch, posterize boundaries, posterize+Canny). None produced a colorable page: edge methods give open, speckled lines (pine-forest Canny flood-fills as one region); XDoG is a 70-84% black engraving; posterize closes regions but turns the subject into an unrecognisable blob map.
- Vectorising tools (potrace, vtracer, Inkscape) and deep-learning sketch models were not available here and were not tested; they would likely improve legibility but still leave open lines.
- Recommendation: generate, don't convert. Re-render a scene as line art with an image model using the puzzle JPG as the reference (prompt in findings.md), then run `region_stats()` from lineart.py as the automatic closed-region QA check on every page that ships.
