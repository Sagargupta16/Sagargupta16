#!/usr/bin/env python3
"""Update static star/follower badges in README.md with live GitHub counts.

shields.io's dynamic /github/* badges share a public GitHub token pool that
intermittently exhausts and renders "Unable to select next GitHub token from
pool" on the profile. Static /badge/ URLs never touch that pool, so the README
uses static badges and this script keeps their numbers fresh.

Run by .github/workflows/update-star-badges.yml. Stdlib only, like
update-credly-badges.py. GITHUB_TOKEN env is optional (rate limits).
"""

import json
import os
import re
import urllib.request

USER = "Sagargupta16"
README = "README.md"


def api(url):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER,
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.load(resp), resp.headers


def paginate(url):
    results = []
    while url:
        data, headers = api(url)
        results.extend(data)
        match = re.search(r'<([^>]+)>;\s*rel="next"', headers.get("Link", ""))
        url = match.group(1) if match else None
    return results


def main():
    user, _ = api(f"https://api.github.com/users/{USER}")
    followers = user["followers"]

    repos = paginate(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner")
    stars = {repo["name"]: repo["stargazers_count"] for repo in repos}
    total_stars = sum(stars.values())

    with open(README, encoding="utf-8") as f:
        text = f.read()
    original = text

    text = re.sub(
        r"(img\.shields\.io/badge/Followers-)\d+(-)",
        rf"\g<1>{followers}\g<2>",
        text,
    )
    text = re.sub(
        r"(img\.shields\.io/badge/Total%20Stars-)\d+(-)",
        rf"\g<1>{total_stars}\g<2>",
        text,
    )

    def update_row(match):
        count = stars.get(match.group("name"))
        if count is None:
            return match.group(0)
        return re.sub(
            r"(img\.shields\.io/badge/Stars-)\d+(-)",
            rf"\g<1>{count}\g<2>",
            match.group(0),
        )

    text = re.sub(
        rf"^\| \[(?P<name>[\w.-]+)\]\(https://github\.com/{USER}/[^)]+\) \|.*img\.shields\.io/badge/Stars-.*$",
        update_row,
        text,
        flags=re.MULTILINE,
    )

    if text != original:
        with open(README, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"Updated badges: followers={followers}, total_stars={total_stars}")
    else:
        print("Badges already current")


if __name__ == "__main__":
    main()
