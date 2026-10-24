# Numbering, palette size and hints

Type: grilling
Status: resolved
Blocked by: 11

## Question

Reference: docs/reference/happy-color/ (numbers only drawn where the region is big enough at the current zoom; selecting a colour tints or hatches all its regions; palettes can run to 100+ colours on detailed pages).

How does the number system feel to the player: how many colours per page (more = finer shading but more hunting), whether the palette shows a progress count per colour, whether un-coloured regions of the selected number get highlighted, a 'find next' hint, long-press to pick a colour from the picture, and auto-advance to the next colour when one is done. Resolution = the interaction rules for the spec.

## Answer

Decided 2026-10-24: numbers are the region's dominant palette colour; palette size per page is whatever the content tool produced (16-36 for pairs); auto-advance to the next unfinished colour when one completes; 'find next' hint pans to an unfilled region of the selected colour; long-press on a filled region selects its colour.
