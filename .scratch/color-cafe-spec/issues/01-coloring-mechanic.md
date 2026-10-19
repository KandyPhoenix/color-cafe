# Coloring mechanic: tap-to-fill, brush, or both

Type: prototype
Status: resolved
Blocked by: 

## Question

How should coloring work on screen? Options: tap-to-fill enclosed regions (fast, phone-friendly, needs closed outlines); free brush that stays inside the lines (closer to real coloring, harder on small screens); or both. Build a rough demo of fill and of brush on one of the pages in pages/ and let Kandy react. Resolution = the mechanic for v1, and whether the other is a later addition or out of scope.

## Answer

Decided by Kandy in conversation (2026-10-19), no prototype needed: Color Cafe is **color-by-number with painted reveal**, like the Happy Color app.
The source of every page is a finished full-colour painting (the Canva Halloween scenes, Puzzle Parlor art, ChatGPT scenes). The page is shown as outlines with numbered regions; tapping a region reveals the original painted pixels of that region, including its shading and gradients, so nothing looks "squared off" and the finished page is the painting itself.
Flat single-colour fills and a free brush are out of scope for v1. The black-and-white line-art pages in `pages/` are no longer the content model (they can still be offered later as a "classic" mode, see fog).
