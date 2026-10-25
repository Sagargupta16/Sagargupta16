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
`-mobile.svg` exists, the `<img>` shows that 320px phone layout and a
`(min-width: 1012px)` source swaps in the 840px card; header sources also pick
the viewer's color scheme, wide pair first. The breakpoint follows GitHub's
column, not the screen: from 768px to 1011px the profile sidebar leaves the
README 383 to 563px, where a desktop card would shrink to under 0.7x. Putting
the phone card in the `<img>` also serves clients without `<picture>`, such as
GitHub's mobile app. Cards without a phone layout (the AWS sample diagrams, the
snake, the divider) scale down to the column.

Text floor: 10.5px in every desktop and phone card, which holds about that size
where each is shown (the README column is 831 to 846px from a 1280px window up,
about 308px on a 390px phone); phone micro-labels sit at 11.5px and the AWS
sample diagrams' node labels at 10px, the most their boxes hold. The vendored
GitHub and LeetCode cards and the Credly action's `certs.svg` keep their
upstream sizes.

Phone cards keep the desktop look and motion: mono micro-labels, flat bordered
tiles, badge images and icons, blocks that fade and rise in order, pulsing
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
  years at AWS from `career.start_date`, the active certification count, generic
  customer labels and no internal TFC acronym.

The certification status card uses portfolio expiry dates; the Credly gallery
also contains previously earned certifications and learning badges.

## Confidentiality

Customers are never named on the profile, and their metrics never appear.
`public_portfolio()` in `render-svgs.py` runs on every fresh portfolio snapshot
and on the cached `data.json` before anything renders: each customer engagement
(a `Role - Client` name) takes the generic label in `CUSTOMER_LABELS` for its
start month, and an engagement with no label there shows "AWS customer". The
table is keyed by month so no customer name lives in this public repo. For a new
engagement, add its start month and a generic label; the validator fails until
every customer label ends in "customer".

Before changing a layout, check the GitHub-sanitized markup at desktop and phone
widths. Keep images free of fixed heights unless their aspect ratio is
intentionally constrained.
