param(
    [Parameter(Mandatory=$true)]
    [string]$Version,
    [Parameter(Mandatory=$true)]
    [string]$Description
)

# Validate version format (basic check)
if ($Version -notmatch "^\d+\.\d+\.\d+$") {
    Write-Error "Version must be in format X.Y.Z (e.g., 1.0.0)"
    exit 1
}

$fileName = "Sagar_Resume_v$Version.pdf"
$filePath = "resume-versions\$fileName"

# Check if version already exists
if (Test-Path $filePath) {
    Write-Error "Version v$Version already exists!"
    exit 1
}

# Copy current resume to versioned file
Copy-Item "sagar_resume.pdf" $filePath

Write-Host "✅ Created $fileName"
Write-Host "📝 Don't forget to:"
Write-Host "   1. Update RESUME_VERSIONS.md with version details"
Write-Host "   2. Run: git add . && git commit -m '📄 Release resume v$Version - $Description'"

# Open the versions file for editing
Write-Host "Opening RESUME_VERSIONS.md for editing..."
notepad "RESUME_VERSIONS.md"
