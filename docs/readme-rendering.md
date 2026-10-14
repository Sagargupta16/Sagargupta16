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
inline wrapping. `<picture>` selects the 320px phone layout below 600px; header
sources also account for the viewer's color scheme, narrow pair first.

Every card moves, on phones as on desktop: blocks fade and rise into place in
order, accent bars pulse, a shine sweeps each card, the career rail and the
rating chart draw themselves in. There is no reduced-motion variant.

The alternate SVG controls its own content layout; it does not reorder README
sections. Links belong around the image, because links inside an SVG displayed
through `<img>` are not interactive.

## Ownership

- `render-svgs.py`: profile content, links, section order, desktop cards,
  source refresh metadata and integration.
- `mobile_cards.py`: phone layouts from the same cached data, and
  `cert_status()`, the one expiry rule every certification count uses.
- `scripts/vendor/`: the licensed GitHub Stats and LeetCode renderer versions
  already used by the profile. Desktop and mobile share one data snapshot,
  so partial service failures cannot update only one screen size.
- The pinned Credly Action: its desktop gallery. After a badge change the Credly
  workflow commits the gallery and dispatches the renderer, which redraws the
  phone card and alt text from the new badges.
- `validate-readme.py`: image references, links, usernames, the configured role,
  years at AWS from `career.start_date` and the active certification count.

The certification status card uses portfolio expiry dates; the Credly gallery
also contains previously earned certifications and learning badges.

Before changing a layout, check the GitHub-sanitized markup at desktop and phone
widths. Test sources without fixed heights unless their aspect ratio is
intentionally constrained.
