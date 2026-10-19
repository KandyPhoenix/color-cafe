# Research: region fill on line-art PNGs in canvas

Type: research
Status: open
Blocked by: 

## Question

What is the most reliable way to fill enclosed regions of a black-and-white line-art PNG on an HTML canvas, on a phone? Cover: flood fill with anti-aliased edges (grey pixels leaking), pre-segmenting regions once at load (connected components) vs filling live, performance at ~1500px, handling gaps in the outline, and how to keep the black lines crisp over fills. Report concrete approaches with trade-offs and a recommendation.
