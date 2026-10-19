# Research: region fill on line-art PNGs in canvas

Type: research
Status: resolved
Blocked by: 

## Question

What is the most reliable way to fill enclosed regions of a black-and-white line-art PNG on an HTML canvas, on a phone? Cover: flood fill with anti-aliased edges (grey pixels leaking), pre-segmenting regions once at load (connected components) vs filling live, performance at ~1500px, handling gaps in the outline, and how to keep the black lines crisp over fills. Report concrete approaches with trade-offs and a recommendation.

## Answer

Findings: branch `research/region-fill`, file `research/region-fill/findings.md` (scripts and evidence images alongside).

- v1 approach: pre-segment each page once at load on the native 843px bitmap (4-connected regions of grey >= 200), then grow all regions together into the anti-alias halo down to grey >= 64; fill by region id; draw the line-art PNG over the colour layer with `multiply`. Load 32-127 ms per page (125-425 ms at 4x CPU throttle); a fill 4-24 ms; saved state is just {regionId: colour}.
- Threshold 200, not 128: at 128, 109 real regions on garden-gate merge with neighbours (bird body + wings, sky + background). At 200, zero leaks.
- Segment on native pixels; upscaling first (bilinear/bicubic) causes leaks. Upscale only for display.
- Outline gaps: ~9-14 tiny cells per page leak into the background through <= 2 px necks. Accept at runtime and fix in the art; `halo_and_gaps.py` doubles as a QA script that lists suspect necks for the content pipeline.
- Touch: the median region is ~12 native px, and 36% of taps land on a line, so resolve taps to the nearest region within 3-4 px and make pinch-zoom mandatory (reuse Puzzle Parlor's camera).
- Caveats: phone timings are a 4x-throttle proxy, not real hardware; visual leak checks were done on garden-gate only.
