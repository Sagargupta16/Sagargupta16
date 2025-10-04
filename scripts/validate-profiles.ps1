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

$leetcodeUser = & yq '.leetcode.username' $configFile
$githubUser = & yq '.github.username' $configFile
$linkedinUser = & yq '.linkedin.username' $configFile

Write-Host "  GitHub: $githubUser" -ForegroundColor White
Write-Host "  LinkedIn: $linkedinUser" -ForegroundColor White
Write-Host "  LeetCode: $leetcodeUser" -ForegroundColor White

# Check README for inconsistencies
Write-Host "`n🔎 Checking README for username consistency..." -ForegroundColor Cyan

$readme = Get-Content $readmeFile -Raw
$issues = @()

# Check for wrong LeetCode username
if ($readme -match "leetcode\.com/SAGARGUPTA16") {
    $issues += "❌ Found 'SAGARGUPTA16' in LeetCode URL (should be '$leetcodeUser')"
}

if ($readme -match "SAGARGUPTA16.*theme=") {
    $issues += "❌ Found 'SAGARGUPTA16' in LeetCode card (should be '$leetcodeUser')"
}

# Check for consistent LeetCode usage
$leetcodeMatches = [regex]::Matches($readme, "leetcode\.com/(\w+)")
$uniqueUsernames = $leetcodeMatches | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique

if ($uniqueUsernames.Count -gt 1) {
    $issues += "⚠️  Multiple LeetCode usernames found: $($uniqueUsernames -join ', ')"
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
        
        # Fix LeetCode username
        $readme = $readme -replace "leetcode\.com/SAGARGUPTA16", "leetcode.com/$leetcodeUser"
        $readme = $readme -replace "SAGARGUPTA16\?theme=", "$leetcodeUser?theme="
        
        Set-Content $readmeFile -Value $readme -NoNewline
        Write-Host "✅ Fixed README.md - please review changes!" -ForegroundColor Green
    }
    else {
        Write-Host "`nℹ️  Run with -Fix flag to automatically fix these issues" -ForegroundColor Cyan
    }
}

Write-Host "`n✨ Validation complete!" -ForegroundColor Cyan
