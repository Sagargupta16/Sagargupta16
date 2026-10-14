# Rendering the SVG profile

`README.md`, `COMMUNITY.md` and `assets/svg/` are generated. Edit the renderer,
its source data or its helper modules, then regenerate; do not patch the output.

```text
python scripts/render-svgs.py --offline
python -m unittest discover -s tests
python scripts/validate-readme.py
```

The offline mode retains the checked-in statistics, portfolio data and icons.
It does not contact external services or advance successful-refresh timestamps.
The normal daily workflow refreshes those sources and retains their last good
values when a source fails.

## GitHub-compatible presentation

GitHub strips custom README CSS. Cards use numeric image widths and ordinary
inline wrapping. `<picture>` selects narrow SVGs below 600px and static SVGs
when reduced motion is requested. The combined narrow/reduced-motion condition
comes first. Header sources also account for the viewer's color scheme.

The alternate SVG controls its own content layout; it does not reorder README
sections. Links belong around the image, because links inside an SVG displayed
through `<img>` are not interactive.

## Ownership

- `render-svgs.py`: profile content, links, section order, local desktop cards,
  source refresh metadata and integration.
- `mobile_cards.py`: narrow SVG layouts from the same cached data.
- `svg_variants.py`: static companions, including visible final entrance states.
- `scripts/vendor/`: the licensed GitHub Stats and LeetCode renderer versions
  already used by the profile. Desktop and mobile now share one data snapshot,
  so partial service failures cannot update only one screen size.
- The pinned Credly Action: its desktop gallery. The profile renderer derives
  its alternatives after the Action finishes.
- The Credly workflow runs offline regeneration after changing its gallery,
  so badge, README and alternative-image updates are committed together.

The certification status card uses portfolio expiry dates; the Credly gallery
also contains previously earned certifications and learning badges.

Before changing a layout, check the GitHub-sanitized markup at desktop and phone
widths, with both normal and reduced motion. Test sources without fixed heights
unless their aspect ratio is intentionally constrained.
