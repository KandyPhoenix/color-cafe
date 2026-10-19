# Map: Color Cafe build-ready spec

Label: wayfinder:map
Charted: 2026-10-19

## Destination

A build-ready spec for Color Cafe: every product decision made (coloring mechanic, content pipeline,
free/full split, finished-page features, hosting, license reuse) so one later session can start
building without asking anything. Not the build itself.

## Notes

- Audience: adults, relaxation and brain-health angle, same crowd as Puzzle Parlor (decided while charting).
- Pricing: same model as Puzzle Parlor: a few free pages, one-time price for everything, license codes, all sales final (decided while charting).
- Platform: browser web app like Puzzle Parlor (touch + mouse, installable, Cloudflare Pages; Android wrapper later) (decided while charting).
- Reference codebase: `/home/user/puzzle-parlor` (public/index.html app, functions/ license API, tools/ release scripts).
- Source content: finished colour paintings (Canva Halloween scenes, Puzzle Parlor art, ChatGPT scenes). The five line-art pages in `pages/` are kept for a possible later 'classic' mode.
- Skills every session should consult: grilling, domain-modeling; prototype for "how should it feel" questions.
- Kandy is on a phone most of the time: keep questions short, lead with a recommendation.

## Decisions so far

<!-- one line per resolved ticket: [title](path): gist -->

- [Coloring mechanic](issues/01-coloring-mechanic.md): color-by-number with painted reveal (Happy Color style); source pages are finished colour paintings; flat fills and free brush out of scope for v1.

- [Research: region fill on line-art PNGs in canvas](issues/02-region-fill-technique.md): pre-segment at native resolution (threshold 200) with halo growth, fill by region id, line art multiplied on top; nearest-region tap + mandatory pinch-zoom; a gap-QA script for intake.
- [Research: splitting a painting into numbered regions](issues/11-segment-painting-into-regions.md): working pipeline (24 Lab colours, merge < 900 px^2, split giants), ~550 regions per page, reveal is pixel-exact; outline page is only medium-clear on painterly art, flatter art reads better; data format = original + packed label PNG + regions.json.
- [Research: turning Puzzle Parlor art into coloring pages](issues/03-line-art-from-puzzle-art.md): automatic conversion is not colorable; re-generate scenes as line art from the puzzle image as reference, and QA closure with a script.
- [Research: reusing Puzzle Parlor's license system](issues/06-license-reuse.md): share one license service with a `product` field (Design B), two-step rollout; use different prices per product.

## Not yet specified

- Outline readability: edge simplification, seam cleanup in flat dark areas, and whether source art should be commissioned in a flatter cel style for cleaner pages.
- A 'classic' free-colour mode using the black-and-white pages in `pages/` (region fill research in ticket 02 applies): later, if ever.
- Accessibility: colour-blind-friendly palettes, large tap targets.
- Sharing a finished page to social / the village.
- Saved work syncing across devices (Puzzle Parlor saves per device today).
- Android wrapper (Capacitor) and store listing: after the web app exists.
- Brain-health / relaxation marketing copy for the buy page, reusing the Southampton study wording from Puzzle Parlor's buy page.
- Launch content: how many pages at launch, weekly release cadence, seasonal packs (Halloween, Christmas).
- Village landing page tie-in: how Color Cafe appears in the street and cross-sells with Puzzle Parlor.

## Out of scope

- The KandyPhoenix Village landing page itself (separate effort, needs the street illustration first).
- A kids tier / simpler pages (Kandy chose adults-only for this map).
- A printable-PDF-only product (on-screen coloring is the product; printing may still be a feature, see tickets).
