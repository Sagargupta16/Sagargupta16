#!/usr/bin/env python3
"""Fetch Credly badges and update README.md between CREDLY-BADGES markers."""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

CREDLY_USERNAME = os.environ.get("CREDLY_USERNAME", "sagar-gupta.f8eb96cc")
README_PATH = os.environ.get("README_PATH", "README.md")
BADGE_SIZE = int(os.environ.get("BADGE_SIZE", "100"))
MAX_RETRIES = 3

CERT_KEYWORDS = ["Certified"]
PROFESSIONAL_KEYWORDS = [
    "Partner: Technical",
    "Generative AI Technical Intermediate",
    "AI Foundational",
    "Well-Architected Proficient",
]
# Everything else falls into knowledge/learning


def fetch_badges(username):
    """Fetch all badges from Credly public JSON API with retry logic."""
    url = f"https://www.credly.com/users/{username}/badges.json"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "GitHub-Actions-Credly-Badge-Updater",
        },
    )
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 5 * (attempt + 1)
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"ERROR: All {MAX_RETRIES} attempts failed for {url}")
                raise


def categorize_badges(badges):
    """Split badges into certifications, professional, and knowledge categories."""
    certifications = []
    professional = []
    knowledge = []

    for badge in badges:
        template = badge.get("badge_template", {})
        name = template.get("name", "")

        if any(kw in name for kw in CERT_KEYWORDS):
            certifications.append(badge)
        elif any(kw in name for kw in PROFESSIONAL_KEYWORDS):
            professional.append(badge)
        else:
            knowledge.append(badge)

    return certifications, professional, knowledge


def badge_to_html(badge, size=BADGE_SIZE):
    """Generate an HTML anchor+img tag for a single badge."""
    template = badge.get("badge_template", {})
    name = template.get("name", "Badge")
    image_url = template.get("image_url", "")
    badge_id = badge.get("id", "")
    badge_url = f"https://www.credly.com/badges/{badge_id}"

    # Insert size prefix into Credly CDN URL
    sized_url = image_url.replace(
        "images.credly.com/images/",
        f"images.credly.com/size/{size}x{size}/images/",
    )

    return (
        f'<a href="{badge_url}" title="{name}">'
        f'<img src="{sized_url}" alt="{name}" width="{size}" height="{size}">'
        f"</a>"
    )


def generate_section(certifications, professional, knowledge):
    """Generate the full markdown/HTML for the badges section."""
    lines = []

    # Industry Certifications
    lines.append("#### \U0001f3c5 Industry Certifications")
    lines.append("")
    lines.append('<div align="center">')
    lines.append("")
    for badge in certifications:
        lines.append(badge_to_html(badge))
    lines.append("")
    lines.append("</div>")

    # Professional & Partner Badges
    if professional:
        lines.append("")
        lines.append("#### \U0001f396\ufe0f Professional & Partner Badges")
        lines.append("")
        lines.append('<div align="center">')
        lines.append("")
        for badge in professional:
            lines.append(badge_to_html(badge))
        lines.append("")
        lines.append("</div>")

    # Knowledge & Learning Badges
    if knowledge:
        lines.append("")
        lines.append("#### \U0001f4da Knowledge & Learning Badges")
        lines.append("")
        lines.append('<div align="center">')
        lines.append("")
        for badge in knowledge:
            lines.append(badge_to_html(badge))
        lines.append("")
        lines.append("</div>")

    return "\n".join(lines)


def update_readme(section_content):
    """Replace content between CREDLY-BADGES markers in README."""
    with open(README_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = r"<!-- CREDLY-BADGES:START -->.*?<!-- CREDLY-BADGES:END -->"
    replacement = (
        f"<!-- CREDLY-BADGES:START -->\n{section_content}\n<!-- CREDLY-BADGES:END -->"
    )

    new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

    if count == 0:
        print("ERROR: Could not find CREDLY-BADGES markers in README.md")
        sys.exit(1)

    if new_content == content:
        print("No changes detected in badges section.")
        return False

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("README.md updated with latest Credly badges.")
    return True


def main():
    print(f"Fetching badges for Credly user: {CREDLY_USERNAME}")
    data = fetch_badges(CREDLY_USERNAME)

    # The API returns {"data": [...]}
    badges = data.get("data", data)
    if not isinstance(badges, list):
        print(f"ERROR: Unexpected API response format: {type(badges)}")
        sys.exit(1)

    print(f"Found {len(badges)} total badges on Credly.")

    certs, prof, know = categorize_badges(badges)
    print(
        f"  Industry Certifications: {len(certs)}\n"
        f"  Professional & Partner:  {len(prof)}\n"
        f"  Knowledge & Learning:    {len(know)}"
    )

    section = generate_section(certs, prof, know)
    changed = update_readme(section)

    if changed:
        print("Badges section has been updated.")
    else:
        print("Badges section is already up to date.")


if __name__ == "__main__":
    main()
