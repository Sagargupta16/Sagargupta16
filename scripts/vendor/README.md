# Pinned card renderers

The profile generator imports these standard-library-only renderers so the
desktop, mobile, static and accessible descriptions use one fetched snapshot.
The daily workflow calls the profile generator once instead of fetching each
service separately through a composite Action.

| Module | Upstream source | License |
| --- | --- | --- |
| `github_stats_card.py` | [github-stats-card-action at 6490d5b (v1.3.0)](https://github.com/Sagargupta16/github-stats-card-action/blob/6490d5bfb062551f8721ff5250d936cacf034775/github_stats_card.py) | [MIT](LICENSE.github-stats-card-action) |
| `leetcode_card.py` | [leetcode-card-action at b379afe (v1.2.0)](https://github.com/Sagargupta16/leetcode-card-action/blob/b379afe1f1b74cada139a63bda48b8a4dfd5f07c/leetcode_card.py) | [MIT](LICENSE.leetcode-card-action) |

LeetCode is copied without changes. GitHub has one local addition:
`fetch_stats()` returns a `repo_stars` dictionary from the same paginated,
public, non-fork repository list used for the aggregate statistics. Community
cards can then show repository stars without another request. The existing
query already selects repository names; filtering and pagination are unchanged.

Both upstream copyright notices are retained with their original MIT licenses.
When updating these copies, record the new source revisions here, retain the
licenses and the documented GitHub addition, and run the profile tests and
offline rendering checks.
