# Color Cafe

Color-by-number for grown-ups, plus free-color mandalas. Second shop in the KandyPhoenix Village,
next door to [Puzzle Parlor](https://puzzles.kandyphoenix.com).

## Layout
- `public/` — the app (single-file `index.html`), `pages.json` manifest and `pages/<slug>/` assets
- `tools/make_page.py` — turns art into a page (see below)
- `tools/simplify_page.py` — makes a colour-by-number page easy to colour (fewer pieces, thin closed outlines)
- `pages/` — source line art waiting to be built; `pages/ink/` — each built page's original ink drawing
- `.scratch/color-cafe-spec/` — the Wayfinder planning map
- `research/*` branches — experiments; never merged

## Adding a page
Color-by-number (two files from ChatGPT: the line art, then "paint this exact drawing"):

    python3 tools/make_page.py pair <slug> line.png color.jpg --title "Title" --theme fantasy --style "Watercolor"

Free-color line art (mandalas, classic pages):

    python3 tools/make_page.py line <slug> line.png --title "Title" --theme mandalas

Then simplify it (every colour-by-number page goes through this step):

    python3 tools/simplify_page.py <slug>

This merges tiny pieces and slivers, splits pieces whose outline leaks into a second colour, and replaces
the heavy black ink with thin grey outlines traced from the pieces themselves (stored as vectors in
`regions.json`, so they are always closed and stay sharp at any zoom). The original ink drawing is kept in
`pages/ink/<slug>.png`, so a page can be re-run with other settings, e.g. `--min 800` for more pieces or
`--min 1500` for fewer. Run pages one at a time (each run updates `public/pages.json`).

Then commit `public/pages/<slug>/`, `public/pages.json` and `pages/ink/<slug>.png`.

Deploying: every push to `main` publishes `public/` to color.kandyphoenix.com through
`.github/workflows/deploy.yml` (also runnable by hand from the Actions tab). It uses the repository secret
`CLOUDFLARE_API_TOKEN`, the same Cloudflare token Puzzle Parlor uses, and finds the Pages project that has
color.kandyphoenix.com attached. Commit pages here; the repo is the source of truth.

Themes in the app: fantasy, mandalas, classic (add more in `THEMES` in index.html).
