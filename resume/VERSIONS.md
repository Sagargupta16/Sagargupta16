# Resume Versions

## Latest Version
- **File**: `sagar_resume.pdf` (always the current version)
- **Version**: v1.0.0
- **Last Updated**: 2025-07-25

## Naming Convention
**Format**: `Sagar_Resume_vX.Y.Z.pdf`

- **Major (X)**: Career milestones (graduation, new job, major role change)
- **Minor (Y)**: New projects, skills, certifications, experience updates
- **Patch (Z)**: Small fixes, formatting improvements, typos

## Version History

| Version | Date | File Name | Changes |
|---------|------|-----------|---------|
| v1.0.0 | 2025-07-25 | `Sagar_Resume_v1.0.0.pdf` | Initial version with current projects and NIT Warangal experience |

---

## How to Update Resume

### When to Increment Versions:
- **Major (2.0.0)**: Got a new job, graduated, major career change
- **Minor (1.1.0)**: Added new project, learned new technology, updated experience
- **Patch (1.0.1)**: Fixed typos, improved formatting, small corrections

### Steps:
1. **Edit your resume** and save as `sagar_resume.pdf`
2. **Determine version number** based on changes made
3. **Copy to versions folder**: `Copy-Item "sagar_resume.pdf" "resume\versions\Sagar_Resume_vX.Y.Z.pdf"`
4. **Update this log** with version details
5. **Commit to git** with message: "📄 Release resume vX.Y.Z - [description]"

## Quick Commands

```powershell
# Example: Creating version 1.1.0 after adding a new project
Copy-Item "sagar_resume.pdf" "resume\versions\Sagar_Resume_v1.1.0.pdf"

# Using the script (run from root directory)
.\resume\new-version.ps1 "1.1.0" "Added AI project and React skills"

# Commit changes
git add .
git commit -m "📄 Release resume v1.1.0 - Added AI project and React skills"
```

## Version Examples
- `v1.0.0` → `v1.0.1`: Fixed spelling errors
- `v1.0.1` → `v1.1.0`: Added new internship experience  
- `v1.1.0` → `v2.0.0`: Graduated and got first job
