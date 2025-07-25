# Resume Management

This folder contains all resume-related files and version management.

## Files
- `versions/` - All versioned resume files
- `VERSIONS.md` - Version history and management guide
- `new-version.ps1` - Script to create new versions easily

## Quick Usage

```powershell
# From repository root directory:

# Create new version manually
Copy-Item "sagar_resume.pdf" "resume\versions\sagar-resume-v1.1.0.pdf"

# Or use the script
.\resume\new-version.ps1 "1.1.0" "Added new project"
```

For detailed instructions, see `VERSIONS.md`.
