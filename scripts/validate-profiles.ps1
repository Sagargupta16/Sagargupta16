#!/usr/bin/env pwsh
# Profile Configuration Validator
# Checks consistency between profiles.yml and README.md

param(
    [switch]$Fix = $false
)

Write-Host "🔍 Validating profile configuration..." -ForegroundColor Cyan

# Check if yq is available (for YAML parsing)
$yqAvailable = Get-Command yq -ErrorAction SilentlyContinue

if (-not $yqAvailable) {
    Write-Host "⚠️  Warning: 'yq' not found. Install from: https://github.com/mikefarah/yq" -ForegroundColor Yellow
    Write-Host "   Skipping YAML validation..." -ForegroundColor Yellow
    exit 0
}

$configFile = ".github/config/profiles.yml"
$readmeFile = "README.md"

if (-not (Test-Path $configFile)) {
    Write-Host "❌ Config file not found: $configFile" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $readmeFile)) {
    Write-Host "❌ README file not found: $readmeFile" -ForegroundColor Red
    exit 1
}

# Read config values
Write-Host "`n📋 Reading configuration from $configFile..." -ForegroundColor Cyan

$githubUser = & yq '.github.username' $configFile
$leetcodeUser = & yq '.leetcode.username' $configFile
$linkedinUser = & yq '.linkedin.username' $configFile
$monkeytypeUser = & yq '.monkeytype.username' $configFile
$holopinUser = & yq '.holopin.username' $configFile
$portfolioUrl = & yq '.portfolio.url' $configFile
$credlyUser = & yq '.credly.username' $configFile

Write-Host "  GitHub: $githubUser" -ForegroundColor White
Write-Host "  LinkedIn: $linkedinUser" -ForegroundColor White
Write-Host "  LeetCode: $leetcodeUser" -ForegroundColor White
Write-Host "  MonkeyType: $monkeytypeUser" -ForegroundColor White
Write-Host "  Holopin: $holopinUser" -ForegroundColor White
Write-Host "  Credly: $credlyUser" -ForegroundColor White
Write-Host "  Portfolio: $portfolioUrl" -ForegroundColor White

# Check README for inconsistencies
Write-Host "`n🔎 Checking README for username consistency..." -ForegroundColor Cyan

$readme = Get-Content $readmeFile -Raw
$issues = @()

# --- LeetCode checks ---
# Use negative lookahead (?!10) to avoid false-positiving on 'sagargupta1610'
# (the correct LeetCode username) when matching the GitHub username 'Sagargupta16'
if ($readme -match "leetcode\.com/SAGARGUPTA16(?!10)") {
    $issues += "❌ Found GitHub username in LeetCode URL (should be '$leetcodeUser')"
}

if ($readme -match "leetcard[^\n]*SAGARGUPTA16(?!10)") {
    $issues += "❌ Found GitHub username in LeetCode card URL (should be '$leetcodeUser')"
}

# Check for consistent LeetCode usage
$leetcodeMatches = [regex]::Matches($readme, "leetcode\.com/(\w+)")
$uniqueUsernames = $leetcodeMatches | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique

if ($uniqueUsernames.Count -gt 1) {
    $issues += "⚠️  Multiple LeetCode usernames found: $($uniqueUsernames -join ', ')"
}

# --- LinkedIn checks ---
$linkedinMatches = [regex]::Matches($readme, "linkedin\.com/in/([a-zA-Z0-9-]+)")
$uniqueLinkedin = $linkedinMatches | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique

if ($uniqueLinkedin.Count -gt 0) {
    foreach ($found in $uniqueLinkedin) {
        if ($found -ne $linkedinUser) {
            $issues += "❌ Found LinkedIn username '$found' in README (should be '$linkedinUser')"
        }
    }
}

# --- GitHub username checks (case-insensitive compare for shields.io) ---
$githubShieldsMatches = [regex]::Matches($readme, "github\.com/followers/(\w+)")
foreach ($match in $githubShieldsMatches) {
    $found = $match.Groups[1].Value
    if ($found -cne $githubUser -and $found -ine $githubUser) {
        $issues += "❌ Found GitHub username '$found' in shields URL (should be '$githubUser')"
    }
}

# --- MonkeyType checks ---
if ($readme -match "monkeytype\.com/profile/(\w+)") {
    $found = $Matches[1]
    if ($found -cne $monkeytypeUser) {
        $issues += "❌ Found MonkeyType username '$found' in README (should be '$monkeytypeUser')"
    }
}

# --- Holopin checks ---
if ($readme -match "holopin\.me/(\w+)") {
    $found = $Matches[1]
    if ($found -cne $holopinUser) {
        $issues += "❌ Found Holopin username '$found' in README (should be '$holopinUser')"
    }
}

# --- Portfolio URL check ---
if ($portfolioUrl -and $readme -notmatch [regex]::Escape($portfolioUrl)) {
    $issues += "⚠️  Portfolio URL '$portfolioUrl' not found in README"
}

# --- Credly checks ---
$credlyMatches = [regex]::Matches($readme, "credly\.com/users/([a-zA-Z0-9.\-]+)")
foreach ($match in $credlyMatches) {
    $found = $match.Groups[1].Value
    if ($found -ne $credlyUser) {
        $issues += "❌ Found Credly username '$found' in README (should be '$credlyUser')"
    }
}

# --- Role / title consistency ---
$currentRole = & yq '.career.current_role' $configFile
if ($currentRole -and $currentRole -ne "null") {
    if ($readme -notmatch [regex]::Escape($currentRole)) {
        $issues += "⚠️  Current role '$currentRole' from profiles.yml not found in README"
    }
}

# --- Experience badge check ---
$startDate = & yq '.career.start_date' $configFile
if ($startDate -and $startDate -ne "null") {
    $startYear = [int]($startDate -split "-")[0]
    $currentYear = (Get-Date).Year
    $yearsExp = $currentYear - $startYear
    # Check if the Experience badge reflects the correct range
    if ($readme -match "Experience-(\d+)\%2B\%20Years") {
        $badgeYears = [int]$Matches[1]
        if ($badgeYears -ne $yearsExp) {
            $issues += "⚠️  Experience badge says ${badgeYears}+ years but career.start_date ($startDate) suggests ${yearsExp}+ years"
        }
    }
}

# --- Industry certification count check ---
# Count badges in the Industry Certifications section (between markers)
$certSection = [regex]::Match($readme, "Industry Certifications.*?</div>", [System.Text.RegularExpressions.RegexOptions]::Singleline)
if ($certSection.Success) {
    $certBadgeCount = ([regex]::Matches($certSection.Value, '<a href="https://www.credly.com/badges/')).Count
    # Check if the shield badge in the header matches
    if ($readme -match "AWS-(\d+)\%20Industry\%20Certs") {
        $headerCertCount = [int]$Matches[1]
        if ($headerCertCount -ne $certBadgeCount) {
            $issues += "⚠️  Header badge says $headerCertCount industry certs but Credly section has $certBadgeCount"
        }
    }
}

# Display results
if ($issues.Count -eq 0) {
    Write-Host "✅ All usernames are consistent!" -ForegroundColor Green
}
else {
    Write-Host "`n⚠️  Found $($issues.Count) issue(s):" -ForegroundColor Yellow
    $issues | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }

    if ($Fix) {
        Write-Host "`n🔧 Attempting to fix issues..." -ForegroundColor Cyan

        # Fix LeetCode username (negative lookahead to not replace sagargupta1610)
        $readme = $readme -replace "leetcode\.com/SAGARGUPTA16(?!10)", "leetcode.com/$leetcodeUser"
        $readme = $readme -replace "(leetcard[^\n]*)SAGARGUPTA16(?!10)", "`$1$leetcodeUser"

        Set-Content $readmeFile -Value $readme -NoNewline
        Write-Host "✅ Fixed README.md - please review changes!" -ForegroundColor Green
    }
    else {
        Write-Host "`nℹ️  Run with -Fix flag to automatically fix these issues" -ForegroundColor Cyan
    }
}

Write-Host "`n✨ Validation complete!" -ForegroundColor Cyan
