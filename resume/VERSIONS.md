# Resume Versions

## Latest Version

- **Version**: v1.0.5
- **Last Updated**: 2026-03-05
- **File**: `sagar_resume.pdf` (always the current version)

## Naming Convention

**Format**: `sagar-resume-vX.Y.Z.pdf`

- **Major (X)**: Career milestones (graduation, new job, major role change)
- **Minor (Y)**: New projects, skills, certifications, experience updates
- **Patch (Z)**: Small fixes, formatting improvements, typos

## Version History

| Version | Date | File Name | Changes |
|---------|------|-----------|---------|
| v1.0.5 | 2026-03-05 | `sagar-resume-v1.0.5.pdf` | expand: typescript notes |
| v1.0.4 | 2026-03-05 | `sagar-resume-v1.0.4.pdf` | docs: kubernetes notes |
| v1.0.3 | 2026-02-24 | `sagar-resume-v1.0.3.pdf` | feat: Add GitHub Actions workflow to automate resume versioning, PDF creation, and `VERSIONS.md` updates. |
| v1.0.2 | 2025-09-27 | `sagar-resume-v1.0.2.pdf` | Add files via upload |
| v1.0.1 | 2025-08-08 | `sagar-resume-v1.0.1.pdf` | Refactor resume versioning workflow: simplify PDF detection logic and remove deprecated PowerShell script; update .gitignore to include VS Code settings and ensure proper resume upload processing. |
| v1.0.0 | 2025-07-25 | `sagar-resume-v1.0.0.pdf` | Initial version with current projects and NIT Warangal experience |

---

## How It Works Now

The resume is maintained in the [latex-resume](https://github.com/Sagargupta16/latex-resume) repo, which auto-compiles and publishes via GitHub Releases on every push.

This repo's `sagar_resume.pdf` is synced automatically every Monday via the `resume-sync.yml` workflow, which downloads the latest release from `latex-resume`. You can also trigger a manual sync from the Actions tab.

**To update your resume:** Edit the LaTeX source in `latex-resume`, push, and the PDF propagates here automatically.
