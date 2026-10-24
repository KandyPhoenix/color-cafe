# Palette and tool UI

Type: grilling
Status: resolved
Blocked by: 11, 12

## Question

Reference: docs/reference/happy-color/ (palette = scrolling row of numbered colour circles, selected one raised; hint lightbulb with counter; back button).

Updated after ticket 01: the palette is the numbered colour list derived from the painting, not a free picker.
With the mechanic chosen, what tools does v1 need: palette size and how colours are picked, undo/redo, zoom and pan, eraser or 'clear region', a hint of which regions are still blank, and how it all fits on a phone screen. Resolution = the tool list and layout for the spec.

## Answer

Decided 2026-10-24 from the Happy Color reference: bottom palette strip of numbered colour circles with a per-colour progress ring, selected circle raised; pinch-zoom and pan; selecting a colour tints all its unfilled regions; numbers drawn only where the region is big enough at the current zoom; back button; a 'find next' hint button. Mandala (free-colour) pages use a colour picker palette instead of numbers.
