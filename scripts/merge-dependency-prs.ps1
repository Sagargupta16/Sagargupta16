# PowerShell script to merge all open PRs from renovate/ or dependabot/ branches automatically across multiple repositories
# Simplified version that avoids hashtable issues
# Only processes PRs from dependency update bots (renovate and dependabot)

param(
    [string]$MergeMethod = "merge",  # Options: merge, squash, rebase
    [switch]$CloseUnmergeable = $true  # Close PRs that can't be merged and delete branches
)

Write-Host "Starting automatic PR merge process for renovate/dependabot PRs" -ForegroundColor Green
Write-Host "Merge method: $MergeMethod" -ForegroundColor Yellow
Write-Host "Close unmergeable PRs: $CloseUnmergeable" -ForegroundColor Yellow
Write-Host "=" * 80

# Function to get all open PRs from renovate/ or dependabot/ branches
function Get-OpenPRs {
    param($Owner, $Repo)
    
    Write-Host "Fetching open pull requests from renovate/ or dependabot/ branches..." -ForegroundColor Blue
    
    try {
        # Using GitHub CLI if available, otherwise fallback to direct API
        if (Get-Command gh -ErrorAction SilentlyContinue) {
            $prs = gh pr list --repo "$Owner/$Repo" --state open --json number,title,mergeable,createdAt,headRefName --limit 100 | ConvertFrom-Json
            
            # Filter PRs to only include those from renovate/ or dependabot/ branches
            $filteredPrs = $prs | Where-Object { 
                $_.headRefName -like "renovate/*" -or 
                $_.headRefName -like "dependabot/*" 
            }
            
            # Sort PRs by creation date (oldest first)
            $sortedPrs = $filteredPrs | Sort-Object { [DateTime]$_.createdAt }
            
            Write-Host "Found $($prs.Count) total open PR(s), $($sortedPrs.Count) from renovate/dependabot branches - sorted by creation date (oldest first)" -ForegroundColor Green
            return $sortedPrs
        } else {
            # Fallback: You would need to implement API call here
            Write-Host "ERROR: GitHub CLI not found. Please install GitHub CLI (gh) or implement API calls." -ForegroundColor Red
            return @()
        }
    }
    catch {
        Write-Host "ERROR fetching PRs: $($_.Exception.Message)" -ForegroundColor Red
        return @()
    }
}

# Function to merge a single PR or close if not mergeable
function Merge-PR {
    param($Owner, $Repo, $PRNumber, $Title, $MergeMethod, $CloseUnmergeable = $true)
    
    Write-Host "`nProcessing PR #$PRNumber`: $Title" -ForegroundColor Cyan
    
    try {
        if (Get-Command gh -ErrorAction SilentlyContinue) {
            # Check if PR is mergeable (with retry for fresh status)
            Write-Host "   Checking PR mergeability..." -ForegroundColor Gray
            $prDetails = gh pr view $PRNumber --repo "$Owner/$Repo" --json mergeable,mergeStateStatus,headRefName | ConvertFrom-Json
            
            # If status is not clear, wait a bit and check again (GitHub sometimes needs time to update status)
            if ($prDetails.mergeable -eq "UNKNOWN" -or $prDetails.mergeStateStatus -eq "BLOCKED") {
                Write-Host "   PR status unclear, waiting for GitHub to update status..." -ForegroundColor Yellow
                Start-Sleep -Seconds 5
                $prDetails = gh pr view $PRNumber --repo "$Owner/$Repo" --json mergeable,mergeStateStatus,headRefName | ConvertFrom-Json
            }
            
            Write-Host "   PR Status: Mergeable=$($prDetails.mergeable), State=$($prDetails.mergeStateStatus)" -ForegroundColor Gray
            
            if ($prDetails.mergeable -eq "MERGEABLE" -or $prDetails.mergeStateStatus -eq "CLEAN") {
                Write-Host "   PR is mergeable. Attempting to merge..." -ForegroundColor Green
                
                # Merge the PR
                gh pr merge $PRNumber --repo "$Owner/$Repo" --$MergeMethod --delete-branch
                
                Write-Host "   Successfully merged PR #$PRNumber" -ForegroundColor Green
                return "merged"
            }
            else {
                Write-Host "   WARNING: PR #$PRNumber is not mergeable" -ForegroundColor Yellow
                Write-Host "   Details: Mergeable=$($prDetails.mergeable), State=$($prDetails.mergeStateStatus)" -ForegroundColor Yellow
                
                # Be more specific about what constitutes "unmergeable"
                $shouldClose = $false
                
                # Only auto-close if there are clear conflicts or the PR is definitively unmergeable
                if ($prDetails.mergeStateStatus -eq "DIRTY" -or 
                    $prDetails.mergeStateStatus -eq "UNSTABLE" -or 
                    $prDetails.mergeable -eq "CONFLICTING") {
                    $shouldClose = $true
                    Write-Host "   Reason: PR has conflicts or is definitively unmergeable" -ForegroundColor Red
                } elseif ($prDetails.mergeStateStatus -eq "BLOCKED") {
                    Write-Host "   Reason: PR is blocked (may need approvals or status checks)" -ForegroundColor Yellow
                    # Don't auto-close blocked PRs as they might just need approval
                    $shouldClose = $false
                } else {
                    Write-Host "   Reason: Unknown state - being conservative, not auto-closing" -ForegroundColor Yellow
                    $shouldClose = $false
                }
                
                if ($CloseUnmergeable -and $shouldClose) {
                    Write-Host "   Closing PR #$PRNumber and deleting branch..." -ForegroundColor Red
                    
                    # Close the PR
                    gh pr close $PRNumber --repo "$Owner/$Repo" --comment "Auto-closing: PR is not mergeable (Status: $($prDetails.mergeStateStatus))"
                    
                    # Delete the branch if it's not the main/master branch
                    $branchName = $prDetails.headRefName
                    if ($branchName -and $branchName -ne "main" -and $branchName -ne "master") {
                        try {
                            gh api --method DELETE "/repos/$Owner/$Repo/git/refs/heads/$branchName"
                            Write-Host "   Deleted branch: $branchName" -ForegroundColor Red
                        }
                        catch {
                            Write-Host "   Could not delete branch $branchName`: $($_.Exception.Message)" -ForegroundColor Yellow
                        }
                    }
                    
                    Write-Host "   Closed PR #$PRNumber" -ForegroundColor Red
                    return "closed"
                } else {
                    Write-Host "   Skipping PR #$PRNumber (not auto-closing)" -ForegroundColor Yellow
                    return "skipped"
                }
            }
        } else {
            Write-Host "   ERROR: GitHub CLI not available" -ForegroundColor Red
            return "error"
        }
    }
    catch {
        Write-Host "   ERROR processing PR #$PRNumber`: $($_.Exception.Message)" -ForegroundColor Red
        return "error"
    }
}

# Function to process a single repository
function Process-Repository {
    param($Owner, $Repo, $MergeMethod, $CloseUnmergeable)
    
    Write-Host "`n" + "-" * 80
    Write-Host "PROCESSING REPOSITORY: $Owner/$Repo" -ForegroundColor Yellow
    Write-Host "-" * 80
    
    $repoStats = @{
        Repository = "$Owner/$Repo"
        TotalPRs = 0
        MergedCount = 0
        ClosedCount = 0
        SkippedCount = 0
        ErrorCount = 0
        Status = "Processing"
    }
    
    try {
        # Get all open PRs for this repository
        $openPRs = Get-OpenPRs -Owner $Owner -Repo $Repo
        
        if ($openPRs.Count -eq 0) {
            Write-Host "`nNo open PRs from renovate/dependabot branches found in $Owner/$Repo!" -ForegroundColor Green
            $repoStats.Status = "No PRs"
            return $repoStats
        }
        
        $repoStats.TotalPRs = $openPRs.Count
        
        Write-Host "`nStarting merge process for $($openPRs.Count) renovate/dependabot PR(s) in $Owner/$Repo - processing from oldest to newest..." -ForegroundColor Blue
        
        # Display PR order for user confirmation
        Write-Host "`nRenovate/Dependabot PR Processing Order (oldest to newest):" -ForegroundColor Yellow
        $i = 1
        foreach ($pr in $openPRs) {
            $createdDate = [DateTime]$pr.createdAt
            $branchType = if ($pr.headRefName -like "renovate/*") { "Renovate" } else { "Dependabot" }
            Write-Host "  $i. PR #$($pr.number): $($pr.title) [$branchType`: $($pr.headRefName)] (Created: $($createdDate.ToString('yyyy-MM-dd')))" -ForegroundColor Gray
            $i++
        }
        Write-Host ""
        
        # Process each PR in this repository
        foreach ($pr in $openPRs) {
            $result = Merge-PR -Owner $Owner -Repo $Repo -PRNumber $pr.number -Title $pr.title -MergeMethod $MergeMethod -CloseUnmergeable $CloseUnmergeable
            
            switch ($result) {
                "merged" { $repoStats.MergedCount++ }
                "closed" { $repoStats.ClosedCount++ }
                "skipped" { $repoStats.SkippedCount++ }
                "error" { $repoStats.ErrorCount++ }
            }
            
            # Delay between operations to allow GitHub to update PR statuses
            Start-Sleep -Seconds 3
        }
        
        # Repository summary
        Write-Host "`n--- REPOSITORY SUMMARY: $Owner/$Repo ---" -ForegroundColor Cyan
        Write-Host "Total PRs processed: $($repoStats.TotalPRs)" -ForegroundColor White
        Write-Host "Successfully merged: $($repoStats.MergedCount)" -ForegroundColor Green
        Write-Host "Closed (unmergeable): $($repoStats.ClosedCount)" -ForegroundColor Red
        Write-Host "Skipped: $($repoStats.SkippedCount)" -ForegroundColor Yellow
        Write-Host "Errors: $($repoStats.ErrorCount)" -ForegroundColor DarkRed
        
        if ($repoStats.MergedCount -eq $repoStats.TotalPRs) {
            $repoStats.Status = "All Merged"
            Write-Host "✅ ALL PRs in $Owner/$Repo MERGED SUCCESSFULLY!" -ForegroundColor Green
        } elseif (($repoStats.MergedCount + $repoStats.ClosedCount) -eq $repoStats.TotalPRs) {
            $repoStats.Status = "Completed"
            Write-Host "✅ All PRs in $Owner/$Repo processed!" -ForegroundColor Green
        } elseif ($repoStats.MergedCount -gt 0 -or $repoStats.ClosedCount -gt 0) {
            $repoStats.Status = "Partial Success"
            Write-Host "⚠️ Partial success for $Owner/$Repo" -ForegroundColor Yellow
        } else {
            $repoStats.Status = "Failed"
            Write-Host "❌ No PRs were successfully processed in $Owner/$Repo" -ForegroundColor Red
        }
        
    }
    catch {
        Write-Host "`nError processing repository ${Owner}/${Repo}: $($_.Exception.Message)" -ForegroundColor Red
        $repoStats.Status = "Error"
        $repoStats.ErrorCount = 1
    }
    
    return $repoStats
}

# Main execution
try {
    Write-Host "`nProcessing repositories..." -ForegroundColor Blue
    
    # Define repositories for each owner using simple arrays
    $sagarRepos = @("My_Journey", "MERN-TEMPLATE", "TRINIT_BugBiters_Dev", "brainstorm-verse", "ai-code-translator", "Contact-Manager-Mern", "Contact-Manager-React", "tour-vibes", "Authentication-System")
    $mcaRepos = @("placemento", "mca_nitw")
    
    $allResults = @()
    
    # Process Sagargupta16 repositories
    Write-Host "`n" + "=" * 100
    Write-Host "PROCESSING OWNER: Sagargupta16 ($($sagarRepos.Count) repositories)" -ForegroundColor Magenta
    Write-Host "=" * 100
    
    foreach ($repo in $sagarRepos) {
        $result = Process-Repository -Owner "Sagargupta16" -Repo $repo -MergeMethod $MergeMethod -CloseUnmergeable $CloseUnmergeable
        $allResults += $result
        
        # Delay between repositories
        if ($repo -ne $sagarRepos[-1]) {
            Write-Host "`nWaiting before processing next repository..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    }
    
    # Process MCA-NITW repositories
    Write-Host "`n" + "=" * 100
    Write-Host "PROCESSING OWNER: MCA-NITW ($($mcaRepos.Count) repositories)" -ForegroundColor Magenta
    Write-Host "=" * 100
    
    foreach ($repo in $mcaRepos) {
        $result = Process-Repository -Owner "MCA-NITW" -Repo $repo -MergeMethod $MergeMethod -CloseUnmergeable $CloseUnmergeable
        $allResults += $result
        
        # Delay between repositories
        if ($repo -ne $mcaRepos[-1]) {
            Write-Host "`nWaiting before processing next repository..." -ForegroundColor Gray
            Start-Sleep -Seconds 2
        }
    }
    
    # Final overall summary
    $totalRepos = $allResults.Count
    
    # Calculate totals using manual summation to avoid Measure-Object issues
    $totalPRs = 0
    $totalMerged = 0
    $totalClosed = 0
    $totalSkipped = 0
    $totalErrors = 0
    
    foreach ($result in $allResults) {
        $totalPRs += $result.TotalPRs
        $totalMerged += $result.MergedCount
        $totalClosed += $result.ClosedCount
        $totalSkipped += $result.SkippedCount
        $totalErrors += $result.ErrorCount
    }
    
    Write-Host "`n" + "=" * 100
    Write-Host "OVERALL SUMMARY - ALL REPOSITORIES" -ForegroundColor Magenta
    Write-Host "=" * 100
    Write-Host "Total repositories processed: $totalRepos" -ForegroundColor White
    Write-Host "Total PRs across all repos: $totalPRs" -ForegroundColor White
    Write-Host "Successfully merged: $totalMerged" -ForegroundColor Green
    Write-Host "Closed (unmergeable): $totalClosed" -ForegroundColor Red
    Write-Host "Skipped: $totalSkipped" -ForegroundColor Yellow
    Write-Host "Errors: $totalErrors" -ForegroundColor DarkRed
    
    # Per-repository breakdown
    Write-Host "`n--- PER-REPOSITORY BREAKDOWN ---" -ForegroundColor Cyan
    foreach ($result in $allResults) {
        $statusColor = switch ($result.Status) {
            "All Merged" { "Green" }
            "Completed" { "Green" }
            "No PRs" { "Gray" }
            "Partial Success" { "Yellow" }
            "Failed" { "Red" }
            "Error" { "DarkRed" }
            default { "White" }
        }
        Write-Host "$($result.Repository): $($result.Status) ($($result.MergedCount)M/$($result.ClosedCount)C/$($result.SkippedCount)S/$($result.ErrorCount)E)" -ForegroundColor $statusColor
    }
    
    # Overall result
    if ($totalMerged -eq $totalPRs -and $totalPRs -gt 0) {
        Write-Host "`n🎉 ALL PRs ACROSS ALL REPOSITORIES MERGED SUCCESSFULLY!" -ForegroundColor Green
    } elseif (($totalMerged + $totalClosed) -eq $totalPRs -and $totalPRs -gt 0) {
        Write-Host "`n✅ All PRs across all repositories processed!" -ForegroundColor Green
    } elseif ($totalPRs -eq 0) {
        Write-Host "`n✨ No open renovate/dependabot PRs found in any repository. All dependency updates are current!" -ForegroundColor Green
    } elseif ($totalMerged -gt 0 -or $totalClosed -gt 0) {
        Write-Host "`n⚠️ Partial success across repositories." -ForegroundColor Yellow
    } else {
        Write-Host "`n❌ No PRs were successfully processed in any repository." -ForegroundColor Red
    }
    
}
catch {
    Write-Host "`nScript execution failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nScript completed!" -ForegroundColor Magenta
