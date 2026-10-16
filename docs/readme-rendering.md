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
values when a source fails. Offline output is a pure function of the checked-in
data and the UTC date, so `validate-profiles.yml` re-renders every push and pull
request and fails when the committed files differ.

## GitHub-compatible presentation

GitHub strips custom README CSS. Cards use numeric image widths and ordinary
inline wrapping, so rows of cards wrap on narrow screens. Every image sits in a
`<picture>`, which keeps GitHub from styling linked images as blocks. Where a
`-mobile.svg` exists, a `(max-width: 600px)` source picks that 320px phone
layout; header sources also pick the viewer's color scheme, narrow pair first.
Cards without a phone layout (the AWS sample diagrams, the snake, the divider)
scale down to the column.

Phone cards keep the desktop look and motion: mono micro-labels, flat bordered
tiles, logos and badge images, blocks that fade and rise in order, pulsing
accents and a shine. Long lists are capped with a "+N more" line. There are no
reduced-motion variants.

Links belong around the image, because links inside an SVG displayed through
`<img>` are not interactive.

## Ownership

- `render-svgs.py`: profile content, links, section order, desktop cards (and
  the phone stack and AI-tools cards, which need the fetched icons), source
  refresh metadata and integration.
- `mobile_cards.py`: the phone layouts, from the same snapshot and context the
  renderer passes in, and `cert_status()`, the one expiry rule every
  certification count uses.
- `scripts/vendor/`: the licensed GitHub Stats and LeetCode renderer versions
  already used by the profile. Those cards, the hero and the profile badges
  share one data snapshot, so a partial service failure cannot leave them
  disagreeing.
- The pinned Credly Action: its gallery. After a badge change the Credly
  workflow commits the gallery and dispatches the renderer, which redraws the
  README alt text and the phone badge grid from the new badges.
- `validate-readme.py`: image references, links, usernames, the configured role,
  years at AWS from `career.start_date` and the active certification count.

The certification status card uses portfolio expiry dates; the Credly gallery
also contains previously earned certifications and learning badges.

Before changing a layout, check the GitHub-sanitized markup at desktop and phone
widths. Keep images free of fixed heights unless their aspect ratio is
intentionally constrained.
