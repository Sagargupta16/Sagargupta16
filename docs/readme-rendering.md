# Rendering the SVG profile

`README.md`, `COMMUNITY.md` and `assets/svg/` are generated. Edit the renderer,
its source data or a card module, then regenerate; do not patch the output.

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

While working on one card group, `python scripts/preview.py <module>` renders
that module alone into `.scratch/preview/<module>/` (gitignored), and
`python scripts/preview.py --ctx` writes the context the modules receive.
`python scripts/render-svgs.py --data-only` refreshes `data.json` and
`icons.json` and stops.

## How a render runs

1. `render-svgs.py` loads `assets/svg/data.json`, refreshes each source unless
   `--offline` is set, and scrubs the portfolio snapshot (see Confidentiality).
2. `build_context()` turns the snapshot into one `ctx` dictionary: the title,
   the hero lines, the proof cells, engagements, projects, tools, open source,
   certifications and so on. Every card at both widths reads the same `ctx`, so
   two cards cannot disagree about a count.
3. Each module named in `scripts/cards/__init__.py` (`hero`, `chrome`,
   `career`, `samples`, `projects`, `oss`, `stack`, `tools`, `stats`) is called as
   `render(data, ctx)` and returns `{file name: svg}`. A module reads no files
   and makes no requests. The run stops when a listed module is missing, when
   two modules return the same file, or when a module returns `github.svg`,
   `leetcode.svg` or `certs.svg` (drawn elsewhere) or a name that is not a
   plain lower-case `.svg`.
4. The vendored GitHub and LeetCode cards are drawn, then `README.md` and
   `COMMUNITY.md` are assembled from the same `ctx`.

The README takes each card's alt text from that file's own `aria-label`, so the
words a screen reader hears are the words the card was drawn from.

## The context

`build_context(data)` returns the one dictionary every module reads. Values are
plain data unless noted; `python scripts/preview.py --ctx` writes the current
one to `.scratch/preview/ctx.json`.

| Key | Value |
|---|---|
| `today` | ISO date string; modules never read the clock |
| `aws_title`, `aws_title_long`, `location`, `greeting`, `disclaimer` | strings |
| `intro`, `intro_keywords` | the portfolio's intro sentence, and the phrases in it to accent |
| `hero_lines`, `availability` | the portfolio's hero taglines (list) and its "Now: ..." line (string, may be empty) |
| `years_at_aws` | int |
| `proof` | the hero's four cells, each `{value, label}`: aws-samples, AWS certifications, LeetCode peak, years at AWS |
| `milestones` | list of `{year, what, where, city, kind, current}`, oldest first |
| `engagements` | the customer engagements only, oldest first, as `{number, title, sector, when, client, role, stack, kind, ongoing, start, end}`: `title` is "Customer <number>", numbered over every customer, `sector` is the public label without " customer" (empty for "AWS customer"), and `client` is the public label. Programs stay in `data.json` and are not drawn |
| `education` | list of `{degree, school, city, when}` |
| `recognition` | list of `(group title, [(text, year), ...])`; a line naming an SME program is left out |
| `samples` | list of `{key, title, url, date, tags}` for the aws-samples, newest first |
| `projects` | list of `{slug, title, summary, date, tech, url, live, stars}` |
| `project_count` | int |
| `tools` | list of `{slug, title, summary, tech, url, repo, stars, kind, npm_monthly, top}`; `top` marks the nine on the profile |
| `oss` | `{merged, open, merged_count, open_count, repos, combined_stars, community_line}`; `merged` and `open` are lists of `{repo, title, url, date, stars}`, newest first |
| `certs` | `{active, lapsed, active_count, issuer}` |
| `leetcode`, `github`, `contests`, `coding_stats` | the snapshot's objects |
| `headers` | list of `(key, number, title, subtitle)` in page order |
| `header_counts` | `{key: short datum for the right side of that header, or ""}`, in sentence case; empty when a card in that section already shows the number |
| `get_cards` | list of `(key, repo, card name)` |
| `connect` | list of `{key, label, icon, url, primary}` |
| `icon` | callable: `icon(slug)` returns 24 x 24 Simple Icons path data or `None`, from the checked-in cache |
| `updated` | `{source: ISO timestamp}` |
| `badges` | the Credly badges as `{name, image}`, read from `certs.svg` |

## The design kit

`scripts/kit.py` is the one place for colour, type and motion. Every module
draws in its look; a helper only one module needs stays in that module, and
one that two modules would define the same way moves to the kit.

- Palette: canvas `#0b1012`, one blue family, green only for live or ok, amber
  only for LeetCode and work waiting on review. Cards are flat: one fill and
  one hairline border, no gradient, glow or sheen on the cards in the new look.
- Type: mono micro-labels (10.5px desktop, 11.5px phone) and sans for
  everything a person reads as a sentence.
- Clock: every loop lasts 2, 3, 4, 6, 12 or 24 s, so cards that sit together
  realign. Entrances take 0.4 s with a 0.08 s stagger and run once.
- Helpers: `enter`, `group` and `draw` for poster-safe entrances, `loop` and
  `beam` for repeating motion, `rotating` for lines that take turns, `chip`,
  `chips`, `tile`, `ring` and `sparkline` for data marks, `text_width` and
  `wrap_text` for layout, and `num`, `rect`, `keys`, `STAR`, `TICK` and `WELL`
  shared by several modules.

Section headers own the break between sections: there are no divider images.
A header's chip shows a datum only when no card below it shows the same number.

## GitHub-compatible presentation

GitHub strips custom README CSS. Cards use numeric image widths and ordinary
inline wrapping, so rows of cards wrap on narrow screens. Every image sits in a
`<picture>`, which keeps GitHub from styling linked images as blocks. Where a
`-mobile.svg` exists, the `<img>` shows that 320px phone layout and a
`(min-width: 1012px)` source swaps in the 840px card; header sources also pick
the viewer's color scheme, wide pair first. The breakpoint follows GitHub's
column, not the screen: from 768px to 1011px the profile sidebar leaves the
README 383 to 626px, where a desktop card would shrink to 0.46-0.75x. Putting
the phone card in the `<img>` also serves clients without `<picture>`, such as
GitHub's mobile app. The AWS sample diagrams' phone layouts redraw the same
diagram on a 320px grid and wrap the title and tags. The AgentCore sample is
840 wide on its own row; the other two sit two-up at 400.

Text floor: 10.5px in every desktop and phone card, which holds about that size
where each is shown (the README column is 831 to 846px from a 1280px window up,
about 308px on a 390px phone); phone micro-labels sit at 11.5px, and so do
the AWS sample diagrams' phone node labels (10.5px on desktop). The vendored
GitHub and LeetCode cards and the Credly action's `certs.svg` hold the same
10.5px floor upstream since github-stats-card-action v1.3.0, leetcode-card-action
v1.2.0 and credly-badge-readme-action v1.4.0, except one 8.2px label the Credly
action still draws for a long badge name; raise a size there and re-vendor
rather than patch the copies here.

Phone cards keep the desktop look and motion: mono micro-labels, flat bordered
tiles, badge images and icons, blocks that fade and rise in order and pulsing
accents. Long lists are capped with a "+N more" line. There are no
reduced-motion variants.

Entrances are poster-safe on every card: the element's own attributes hold the
finished frame, and its animation runs from 0 s holding the start value until its
turn. A still render (link previews, print, viewers that skip SMIL) shows the
whole card, and browsers still play the entrance. Use `kit.enter()`,
`kit.group()` or `kit.draw()` rather than `opacity="0"` plus a `begin` delay.

Links belong around the image, because links inside an SVG displayed through
`<img>` are not interactive.

## Ownership

- `render-svgs.py`: source refresh, the public snapshot, `build_context()`,
  links, section order and the two generated pages.
- `scripts/kit.py`: the design system every module and the phone engine draw
  with.
- `scripts/cards/<module>.py`: one card group each, desktop and phone twins
  side by side, from the `ctx` the renderer passes in.
- `mobile_cards.py`: the phone layout engine (`Card`), and the rules the
  renderer and the validator must agree on: `cert_status()` (the one expiry
  rule every certification count uses), `cert_issuer()`, the customer label
  table and the public program names.
- `scripts/vendor/`: the licensed GitHub Stats and LeetCode renderer versions
  already used by the profile. Those cards, the hero's proof cells and the
  phone twins share one data snapshot, so a partial service failure cannot
  leave them disagreeing.
- The pinned Credly Action: its gallery, with `hide-expired` on so the heading
  counts active certifications only. After a badge change the Credly workflow
  commits the gallery and dispatches the renderer, which redraws the README alt
  text and the phone badge grid from the new badges.
- `validate-readme.py`: image references, links, usernames, the configured role,
  the counts a visitor reads (years at AWS from `career.start_date`, active
  certifications, AWS certifications) in card text and alt text, customer and
  program labels against the fixed tables, the bracketed sector under each "Customer N", the ambassador wording, no long
  dashes or emojis (raw or as entities), no Markdown-syntax links in the
  generated pages, and every SVG free of scripts, external references and
  broken animation timing.
- `tests/`: one `test_cards_<module>.py` per module, plus the renderer, the
  phone engine and the validator.

The certification status card uses portfolio expiry dates; the Credly gallery
also contains learning and partner badges.

## Confidentiality

Customers are never named on the profile, and their metrics never appear.
`public_portfolio()` in `render-svgs.py` runs on every fresh portfolio snapshot
and on the cached `data.json` before anything renders. Each engagement is
rebuilt from a fixed set of public fields (dates, role, stack and a label), so
a field the portfolio adds later cannot leak through. `split_engagement()`
reads the role and the client whatever separator the portfolio uses. A customer
engagement's label always comes from `CUSTOMER_LABELS` in `mobile_cards.py`,
by its start month, never from the portfolio's own wording; a program listed
in `PROGRAMS` keeps its public name. The table is keyed by month so no customer
name lives in this public repo.

For a new engagement, add its start month and a generic label to
`CUSTOMER_LABELS`. Until then the card shows "AWS customer" and the render
prints a warning; the validator does not fail on a missing month. It does fail
on any customer label that is not in the table or "AWS customer", on any
program name that is not in `PROGRAMS`, and on an engagement that still carries
the portfolio's raw `name` field.

The line that counts AWS community ambassador roles is rewritten to the public
wording ("7x AWS community ambassador") whatever the portfolio writes, and the
validator fails on the word "ambassador" anywhere outside that wording or the
exact title of a Credly badge listed in `assets/credly-badges.md`. The internal
name of that community is never stored here, so a title that used it without
the word "ambassador" would not be caught: check new recognition lines by eye.

Before changing a layout, check the GitHub-sanitized markup at desktop and phone
widths. Keep images free of fixed heights unless their aspect ratio is
intentionally constrained.
