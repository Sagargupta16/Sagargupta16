# Resume Versions

## Latest Version
- **File**: `sagar_resume.pdf` (always the current version)
- **Version**: v1.0.0
- **Last Updated**: 2025-07-25

## Naming Convention
**Format**: `sagar-resume-vX.Y.Z.pdf`

- **Major (X)**: Career milestones (graduation, new job, major role change)
- **Minor (Y)**: New projects, skills, certifications, experience updates
- **Patch (Z)**: Small fixes, formatting improvements, typos

## Version History

| Version | Date | File Name | Changes |
|---------|------|-----------|---------|
| v1.0.0 | 2025-07-25 | `sagar-resume-v1.0.0.pdf` | Initial version with current projects and NIT Warangal experience |

---

## How to Update Resume

### Version bump rules

- **Major (2.0.0)**: Got a new job, graduated, major career change — include [major] in commit message
- **Minor (1.1.0)**: Added new project, new skills, certifications, experience updates — include [minor]
- **Patch (1.0.1)**: Small fixes, typos, formatting — default when no tag present

### Steps (automated)

1. Export your resume as a PDF and place it in `resume/upload/` (any filename, .pdf extension)
2. Commit and push to `main` (use [major]/[minor] as needed in your commit message)
3. The workflow will:
	- Calculate next version based on your commit message
	- Copy the uploaded PDF to `resume/versions/sagar-resume-vX.Y.Z.pdf`
	- Update root `sagar_resume.pdf` to the uploaded file
	- Update this log with the new version and date

## Version Examples

- `v1.0.0` → `v1.0.1`: Fixed spelling errors
- `v1.0.1` → `v1.1.0`: Added new internship experience  
- `v1.1.0` → `v2.0.0`: Graduated and got first job
