# Manual Resume Update Process

## Step-by-Step Instructions

### Step 1: Update Your Resume File
1. Open your resume editing software (Word, LaTeX, Canva, etc.)
2. Make your changes (add projects, update experience, etc.)
3. Export/Save as PDF with filename: `sagar_resume.pdf`

### Step 2: Replace Current Version
```powershell
# Navigate to your repository
cd "C:\Code\GitHub\My Repos\Sagargupta16"

# Copy your updated resume to replace the current version
Copy-Item "path\to\your\updated\sagar_resume.pdf" "resume\current\sagar_resume.pdf" -Force
```

### Step 3: Create New Version
```powershell
# Get current year
$year = Get-Date -Format "yyyy"

# Find next version number
$existingVersions = Get-ChildItem "resume\versions\$year\sagar_resume_v$year.*.pdf"
$nextVersion = ($existingVersions.Count + 1)

# Copy to versions folder
Copy-Item "resume\current\sagar_resume.pdf" "resume\versions\$year\sagar_resume_v$year.$nextVersion.pdf"
```

### Step 4: Update Changelog
Edit `resume\CHANGELOG.md` and add:
```markdown
## [v2025.X] - 2025-07-25

### Added
- [What you added]

### Changed
- [What you changed]

### Removed
- [What you removed]
```

### Step 5: Commit to Git
```powershell
git add .
git commit -m "📄 Release resume v$year.$nextVersion - [Your description]"
git tag "resume-v$year.$nextVersion"
```

## Quick Commands Cheat Sheet

### Copy updated resume to current
```powershell
Copy-Item "path\to\updated\resume.pdf" "resume\current\sagar_resume.pdf"
```

### Use automation script
```powershell
.\save-resume-version.ps1 "Description of changes"
```

### Check current version
```powershell
Get-ChildItem "resume\versions\2025\" | Sort-Object Name | Select-Object -Last 1
```

### View changelog
```powershell
Get-Content "resume\CHANGELOG.md" | Select-Object -First 20
```
