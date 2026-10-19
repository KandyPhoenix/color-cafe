# Research: splitting a painting into numbered color-by-number regions

Type: research
Status: resolved
Blocked by: 

## Question

Given a finished colour painting (e.g. puzzle-parlor/public/img/haunted-village.jpg or witch-kitchen.jpg at 2912px), how do we automatically produce a Happy-Color-style page: a palette of N colours (N roughly 20-40), every pixel assigned to one palette colour, regions = connected areas of one colour, tiny regions merged into neighbours so every region is tappable on a phone, outlines drawn between regions, and a number placed inside each region? Try it for real in this environment (OpenCV 5, Pillow, numpy are available; scikit-image is not): colour quantisation (k-means / median cut in a perceptual colour space), smoothing before quantising, min-region-size merging, outline extraction, number placement (largest inscribed point). Save sample outputs under research/segment/ and measure: region count, smallest tappable region, how recognisable the outline page is, and how close the 'all revealed' result is to the original painting (it should be the original pixels, so exact). Recommend a pipeline for the content tool and the data format the app loads (label map + palette + original image).

## Answer

Findings: branch `research/segment`, file `research/segment/findings.md` (scripts, previews and one full sample set alongside).

- Pipeline that works end to end on Haunted Hollow Village and Witch's Kitchen: strong bilateral smoothing -> k-means to 24 colours in CIE Lab -> connected regions per colour -> merge regions under 900 px^2 / inscribed radius < 8 px into neighbours -> split any region over 3% of the image along texture edges -> outlines from the label map -> number at the most interior point. ~15 s per page.
- Results: 548 / 581 regions, smallest 901 px^2, largest ~5.7%, every region numbered, fully revealed output is byte-identical to the painting.
- N=24 colours is right for these dark paintings; N=36 wastes a third of the palette on near-blacks. A palette-distance-based choice of N is the follow-up.
- The half-revealed page looks exactly like a Happy Color page mid-play. The pure outline page is only medium-recognisable: painterly art has no line work, so in-between regions are organic blobs. Flat or cel-style source art gives much cleaner pages. No edge simplification yet; visible seams in flat dark areas; only two dark paintings tested.
- App format per page (~2.2 MB): original.jpg + labels.png (region id packed into R and G channels; 16-bit PNGs get flattened by canvas) + regions.json (palette, per-region colour, number position, radius, area). Outlines, hit-testing and reveal derive from the label map at runtime.
