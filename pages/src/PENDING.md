# Pages waiting for a line drawing

These paintings are approved for Color Cafe but cannot be built yet, because a
colour-by-number page needs a black-and-white drawing that matches the painting.

## greenhouse-growth ("Growth is slow. Keep watering yourself.")

- Painting: `pages/src/greenhouse-growth-color.jpg` (landscape, 1672 x 941). Kandy asked for this
  one by name on 2026-11-14.
- Needed: `pages/src/greenhouse-growth-line.png`, a clean line drawing of the same picture at the
  same size and framing, including the two lines of lettering as outlined letters.
- How to get it: give the painting to an image tool as a reference with this prompt:

      Turn this exact picture into black-and-white line art for an adult coloring book. Keep the
      same composition, objects and framing. Thin, clean, even black outlines on pure white. Every
      flower, leaf, pot, the watering can, gloves, trowel and table drawn as closed shapes of
      medium size. Keep the words "Growth is slow. Keep watering yourself." in the same place as
      outlined letters, spelled exactly. No shading, no gray, no solid black fills, no border.

- Tracing the drawing from the painting by edge detection was tried and rejected: the flowers
  come out as scribbles, not shapes.
- Then build it like the other pages (theme `quotes`):

      python3 tools/make_page.py pair greenhouse-growth pages/src/greenhouse-growth-line.png pages/src/greenhouse-growth-color.jpg --title "Keep Watering Yourself" --theme quotes --style "Realistic"
      python3 tools/book_page.py greenhouse-growth

## Magic Is Everywhere: Enchanted Night (painted, adult look Kandy wants)
- Rich painting saved: `pages/src/enchanted-night-rich.png` (2026-11-15).
- Building pieces straight from the painting gives shapeless blobs and loses the lettering (tried, not shipped).
- Needs the flat-colour version of this same picture from ChatGPT; then
  `flat_page.py enchanted-night <flat.png> --title ... --theme quotes` and `rich_page.py enchanted-night pages/src/enchanted-night-rich.png`.
