# Content pipeline: where pages come from and how they are vetted

Type: grilling
Status: resolved
Blocked by: 11

## Question

Updated 2026-10-20: regions must follow object shapes, so source art is flat/cel-shaded vector style (test scene pending from Kandy via ChatGPT). Painterly Puzzle Parlor art is not suitable as-is.
Updated 2026-10-19 after ticket 01: the source material is finished colour paintings, not line art.
Where do Color Cafe pages come from and what is the intake process? Options: ChatGPT line art Kandy generates (like pages/), converted Puzzle Parlor art (see research 03), or both. Decide: required resolution, closed-outline check, spell check of any lettering, naming/slug convention, how pages are queued and released (reuse Puzzle Parlor's weekly release script?), and categories/themes for the gallery.

## Answer

Decided with Kandy, 2026-10-20.

- **Source art:** flat cel-shaded scenes (ChatGPT, e.g. Trick-or-Treat Lane) are the main content because they segment into clean, object-shaped regions (~200 per page). Painterly Puzzle Parlor art is a second tier, labelled as busier/harder (~300 regions). Evidence: research/segment previews `lane_obj_*` vs `hv_obj3_*`.
- **Vetting:** Puzzle Parlor rules (original or owned art only; no logos, trademarked characters, real people; any lettering spell-checked at full size; source at least 1536 px long side) plus an automatic region check from the segmenter: region count, smallest region tappable (inscribed radius >= 8 px at native size), largest region <= ~4%, fully revealed == original.
- **Release:** weekly from a queue like Puzzle Parlor (Monday scheduled task, same script pattern), 'New page' chip for three weeks after release. Themed packs can be added later (fog).
- **Gallery:** organised by theme, reusing Puzzle Parlor's theme ids (halloween, christmas, holiday, landscapes, animals, vibes, ...) plus coloring-specific themes where needed (e.g. mandalas), and every page also carries a difficulty label derived from region count (Easy / Medium / Detailed) usable as a filter. ("All of the above" per Kandy.)
- Intake tool: `research/segment/object_segment2.py` is the seed of the content tool (smoothing, dominant-colour numbering, recursive split of oversized regions). Output per page: original.jpg + labels.png (region id in R/G) + regions.json.
