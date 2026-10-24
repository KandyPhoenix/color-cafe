# Color Cafe

Color-by-number for grown-ups, plus free-color mandalas. Second shop in the KandyPhoenix Village,
next door to [Puzzle Parlor](https://puzzles.kandyphoenix.com).

## Layout
- `public/` — the app (single-file `index.html`), `pages.json` manifest and `pages/<slug>/` assets
- `tools/make_page.py` — turns art into a page (see below)
- `pages/` — source line art waiting to be built
- `.scratch/color-cafe-spec/` — the Wayfinder planning map
- `research/*` branches — experiments; never merged

## Adding a page
Color-by-number (two files from ChatGPT: the line art, then "paint this exact drawing"):

    python3 tools/make_page.py pair <slug> line.png color.jpg --title "Title" --theme fantasy --style "Watercolor"

Free-color line art (mandalas, classic pages):

    python3 tools/make_page.py line <slug> line.png --title "Title" --theme mandalas

Then commit `public/pages/<slug>/` and `public/pages.json`. Cloudflare Pages deploys `public/` on push to main.

Themes in the app: fantasy, mandalas, classic (add more in `THEMES` in index.html).
