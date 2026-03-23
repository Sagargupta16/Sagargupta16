# Changelog

All notable changes to this profile README repository.

## [3.2.0] - 2026-03-23

- Remove unnecessary config files (.editorconfig, .dockerignore, .nvmrc, .prettierrc, .python-version, SECURITY.md)
- Remove .github/CODEOWNERS, FUNDING.yml, PR template (solo repo)
- Remove notes/ directory (30 study notes) and journal.md
- Add aws-iot-twinmaker-samples #166 to Open Source section
- Rewrite CHANGELOG with proper versioning

## [3.1.0] - 2026-03-17

- Update Open Source section: Feast #6081 moved to Merged
- Add Terraform provider-aws #46867 and tokemon #13 to Under Review
- Add portfolio screenshot for awesome-dev-portfolios submission
- Point resume download badge to latex-resume GitHub Release

## [3.0.0] - 2026-03-04

- Major redesign: replace "Recent Activity" with Open Source Contributions section (Merged + Under Review tables)
- Introduce `profiles.yml` as single source of truth for all usernames
- Add `validate-profiles.yml` workflow (consistency checks on push)
- Add `snake.yml` workflow (contribution graph animation)
- Switch to working GitHub trophy/stats widget instances
- Update role to "ProServe (Cloud Consultant) - DevOps/MLOps" at AWS
- Add Ledger Sync live demo link to featured projects
- Release resume v1.0.4 and v1.0.5

## [2.3.0] - 2026-02-24

- Implement automated Credly badge updates via `update-credly-badges.yml`
- Custom Python script fetches badges from Credly API, categorizes into Industry/Professional/Knowledge
- Harden all workflows with error handling
- Add `validate-profiles.yml` CI for README accuracy

## [2.2.0] - 2025-08-23

- Add GitHub Metrics section with 30+ auto-generated SVGs
- Create `metrics.yml` workflow (runs every 2 days)
- Metrics include: languages, achievements, calendar, habits, LeetCode performance

## [2.1.0] - 2025-08-08

- Add resume versioning system with GitHub Actions
- `resume-versioning.yml` auto-detects version bump from commit messages
- Creates versioned PDFs in resume/versions/

## [2.0.0] - 2025-07-25

- Major overhaul: add automation infrastructure
- Add Credly badge integration (pemtajo/badge-readme)
- Add `merge-dependency-prs.yml` workflow for batch Renovate PR merging
- Add issue templates, contributing guidelines, security policy
- Expand repository structure documentation

## [1.1.0] - 2024-12-17

- Add 30 technical study notes (algorithms, AWS, Docker, FastAPI, Go, K8s, ML, Python, React, Terraform, etc.)

## [1.0.1] - 2024-03-01

- Add MonkeyType typing speed stats workflow (daily SVG generation on `monkeytype-readme` branch)

## [1.0.0] - 2022-05-31

- Initial profile README creation
- Tech stack badges (skillicons.dev)
- GitHub stats widgets (streak, trophies, activity graph)
- Featured projects and social links
- LeetCode stats card
