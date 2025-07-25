# Resume Management Scripts

## PowerShell Scripts for Windows

### Create New Version
```powershell
# save-resume-version.ps1
param(
    [Parameter(Mandatory=$true)]
    [string]$VersionNote
)

$year = Get-Date -Format "yyyy"
$currentPath = "resume\current\sagar_resume.pdf"
$versionsPath = "resume\versions\$year"

# Get next version number
$existingVersions = Get-ChildItem "$versionsPath\sagar_resume_v$year.*.pdf" -ErrorAction SilentlyContinue
$nextVersion = ($existingVersions.Count + 1)

$newVersionPath = "$versionsPath\sagar_resume_v$year.$nextVersion.pdf"

# Copy current to versioned
Copy-Item $currentPath $newVersionPath

# Update changelog
$changelogEntry = @"

## [v$year.$nextVersion] - $(Get-Date -Format "yyyy-MM-dd")

### Changed
- $VersionNote

"@

$changelogPath = "resume\CHANGELOG.md"
$changelogContent = Get-Content $changelogPath -Raw
$updatedChangelog = $changelogContent -replace "(# Resume Changelog)", "`$1$changelogEntry"
Set-Content $changelogPath $updatedChangelog

# Create git tag
git add .
git commit -m "📄 Release resume v$year.$nextVersion - $VersionNote"
git tag "resume-v$year.$nextVersion"

Write-Host "✅ Created version v$year.$nextVersion: $VersionNote"
```

### Usage Examples
```powershell
# Create new version after updating resume
.\save-resume-version.ps1 "Added new Machine Learning project"

# Create version after job change
.\save-resume-version.ps1 "Updated with Software Engineer role at XYZ Corp"
```
