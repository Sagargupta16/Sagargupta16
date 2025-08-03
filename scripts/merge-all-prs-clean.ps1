# PowerShell script to merge all open PRs automatically across multiple repositories
# Supports processing multiple repositories in batch
#
# Usage Examples:
#   .\merge-all-prs-clean.ps1 -Owner "Sagargupta16" -Repos @("My_Journey")
#   .\merge-all-prs-clean.ps1 -Owner "Sagargupta16" -Repos @("Repo1", "Repo2", "Repo3") -MergeMethod "squash"
#   .\merge-all-prs-clean.ps1 -Owner "MyOrg" -Repos @("project-a", "project-b") -CloseUnmergeable:$false

param(
    [string]$Owner = "Sagargupta16",
    [string[]]$Repos = @("My_Journey", "MERN-TEMPLATE", "TRINIT_BugBiters_Dev", "brainstorm-verse", "ai-code-translator", "Contact-Manager-Mern", "Contact-Manager-React","tour-vibes","Authentication-System","brainstorm-verse"),  # Array of repository names
    [string]$MergeMethod = "merge",  # Options: merge, squash, rebase
    [switch]$CloseUnmergeable = $true  # Close PRs that can't be merged and delete branches
)

Write-Host "Starting automatic PR merge process for $Owner repositories: $($Repos -join ', ')" -ForegroundColor Green
Write-Host "Merge method: $MergeMethod" -ForegroundColor Yellow
Write-Host "Close unmergeable PRs: $CloseUnmergeable" -ForegroundColor Yellow
Write-Host "Total repositories to process: $($Repos.Count)" -ForegroundColor Cyan
Write-Host "=" * 80

# Function to get all open PRs
function Get-OpenPRs {
    param($Owner, $Repo)
    
    Write-Host "Fetching open pull requests..." -ForegroundColor Blue
    
    try {
        # Using GitHub CLI if available, otherwise fallback to direct API
        if (Get-Command gh -ErrorAction SilentlyContinue) {
            $prs = gh pr list --repo "$Owner/$Repo" --state open --json number,title,mergeable,createdAt --limit 100 | ConvertFrom-Json
            
            # Sort PRs by creation date (oldest first)
            $sortedPrs = $prs | Sort-Object { [DateTime]$_.createdAt }
            
            Write-Host "Found $($sortedPrs.Count) open PR(s) - sorted by creation date (oldest first)" -ForegroundColor Green
            return $sortedPrs
        } else {
            # Fallback: You would need to implement API call here
            Write-Host "ERROR: GitHub CLI not found. Please install GitHub CLI (gh) or implement API calls." -ForegroundColor Red
            return @()
        }
        
        Write-Host "Found $($prs.Count) open PR(s)" -ForegroundColor Green
        return $prs
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

# Main execution
try {
    # Overall statistics tracking across all repositories
    $overallStats = @{
        TotalRepos = $Repos.Count
        ProcessedRepos = 0
        TotalPRs = 0
        MergedPRs = 0
        ClosedPRs = 0
        SkippedPRs = 0
        ErrorPRs = 0
        RepoResults = @()
    }
    
    Write-Host "`nProcessing $($Repos.Count) repositories..." -ForegroundColor Blue
    
    # Process each repository
    foreach ($repo in $Repos) {
        Write-Host "`n" + "=" * 80
        Write-Host "PROCESSING REPOSITORY: $Owner/$repo" -ForegroundColor Magenta
        Write-Host "=" * 80
        
        # Repository-specific statistics
        $repoStats = @{
            Repository = "$Owner/$repo"
            TotalPRs = 0
            MergedCount = 0
            ClosedCount = 0
            SkippedCount = 0
            ErrorCount = 0
            Status = "Processing"
        }
        
        try {
            # Get all open PRs for this repository
            $openPRs = Get-OpenPRs -Owner $Owner -Repo $repo
            
            if ($openPRs.Count -eq 0) {
                Write-Host "`nNo open PRs found in $Owner/$repo!" -ForegroundColor Green
                $repoStats.Status = "No PRs"
                $overallStats.RepoResults += $repoStats
                $overallStats.ProcessedRepos++
                continue
            }
            
            $repoStats.TotalPRs = $openPRs.Count
            $overallStats.TotalPRs += $openPRs.Count
            
            Write-Host "`nStarting merge process for $($openPRs.Count) PR(s) in $Owner/$repo - processing from oldest to newest..." -ForegroundColor Blue
            
            # Display PR order for user confirmation
            Write-Host "`nPR Processing Order (oldest to newest):" -ForegroundColor Yellow
            $i = 1
            foreach ($pr in $openPRs) {
                $createdDate = [DateTime]$pr.createdAt
                Write-Host "  $i. PR #$($pr.number): $($pr.title) (Created: $($createdDate.ToString('yyyy-MM-dd')))" -ForegroundColor Gray
                $i++
            }
            Write-Host ""
            
            # Process each PR in this repository
            foreach ($pr in $openPRs) {
                $result = Merge-PR -Owner $Owner -Repo $repo -PRNumber $pr.number -Title $pr.title -MergeMethod $MergeMethod -CloseUnmergeable $CloseUnmergeable
                
                switch ($result) {
                    "merged" { 
                        $repoStats.MergedCount++
                        $overallStats.MergedPRs++
                    }
                    "closed" { 
                        $repoStats.ClosedCount++
                        $overallStats.ClosedPRs++
                    }
                    "skipped" { 
                        $repoStats.SkippedCount++
                        $overallStats.SkippedPRs++
                    }
                    "error" { 
                        $repoStats.ErrorCount++
                        $overallStats.ErrorPRs++
                    }
                }
                
                # Longer delay between operations to allow GitHub to update PR statuses
                Start-Sleep -Seconds 5
            }
            
            # Repository summary
            Write-Host "`n--- REPOSITORY SUMMARY: $Owner/$repo ---" -ForegroundColor Cyan
            Write-Host "Total PRs processed: $($repoStats.TotalPRs)" -ForegroundColor White
            Write-Host "Successfully merged: $($repoStats.MergedCount)" -ForegroundColor Green
            Write-Host "Closed (unmergeable): $($repoStats.ClosedCount)" -ForegroundColor Red
            Write-Host "Skipped: $($repoStats.SkippedCount)" -ForegroundColor Yellow
            Write-Host "Errors: $($repoStats.ErrorCount)" -ForegroundColor DarkRed
            
            if ($repoStats.MergedCount -eq $repoStats.TotalPRs) {
                $repoStats.Status = "All Merged"
                Write-Host "✅ ALL PRs in $Owner/$repo MERGED SUCCESSFULLY!" -ForegroundColor Green
            } elseif (($repoStats.MergedCount + $repoStats.ClosedCount) -eq $repoStats.TotalPRs) {
                $repoStats.Status = "Completed"
                Write-Host "✅ All PRs in $Owner/$repo processed!" -ForegroundColor Green
            } elseif ($repoStats.MergedCount -gt 0 -or $repoStats.ClosedCount -gt 0) {
                $repoStats.Status = "Partial Success"
                Write-Host "⚠️ Partial success for $Owner/$repo" -ForegroundColor Yellow
            } else {
                $repoStats.Status = "Failed"
                Write-Host "❌ No PRs were successfully processed in $Owner/$repo" -ForegroundColor Red
            }
            
        }
        catch {
            Write-Host "`nError processing repository ${Owner}/${repo}: $($_.Exception.Message)" -ForegroundColor Red
            $repoStats.Status = "Error"
            $repoStats.ErrorCount = 1
            $overallStats.ErrorPRs++
        }
        
        $overallStats.RepoResults += $repoStats
        $overallStats.ProcessedRepos++
        
        # Delay between repositories
        if ($repo -ne $Repos[-1]) {  # Don't delay after the last repository
            Write-Host "`nWaiting before processing next repository..." -ForegroundColor Gray
            Start-Sleep -Seconds 3
        }
    }
    
    # Final overall summary
    Write-Host "`n" + "=" * 80
    Write-Host "OVERALL SUMMARY - ALL REPOSITORIES" -ForegroundColor Magenta
    Write-Host "=" * 80
    Write-Host "Total repositories processed: $($overallStats.ProcessedRepos)/$($overallStats.TotalRepos)" -ForegroundColor White
    Write-Host "Total PRs across all repos: $($overallStats.TotalPRs)" -ForegroundColor White
    Write-Host "Successfully merged: $($overallStats.MergedPRs)" -ForegroundColor Green
    Write-Host "Closed (unmergeable): $($overallStats.ClosedPRs)" -ForegroundColor Red
    Write-Host "Skipped: $($overallStats.SkippedPRs)" -ForegroundColor Yellow
    Write-Host "Errors: $($overallStats.ErrorPRs)" -ForegroundColor DarkRed
    
    # Per-repository breakdown
    Write-Host "`n--- PER-REPOSITORY BREAKDOWN ---" -ForegroundColor Cyan
    foreach ($repoResult in $overallStats.RepoResults) {
        $statusColor = switch ($repoResult.Status) {
            "All Merged" { "Green" }
            "Completed" { "Green" }
            "No PRs" { "Gray" }
            "Partial Success" { "Yellow" }
            "Failed" { "Red" }
            "Error" { "DarkRed" }
            default { "White" }
        }
        Write-Host "$($repoResult.Repository): $($repoResult.Status) ($($repoResult.MergedCount)M/$($repoResult.ClosedCount)C/$($repoResult.SkippedCount)S/$($repoResult.ErrorCount)E)" -ForegroundColor $statusColor
    }
    
    # Overall result
    if ($overallStats.MergedPRs -eq $overallStats.TotalPRs -and $overallStats.TotalPRs -gt 0) {
        Write-Host "`n🎉 ALL PRs ACROSS ALL REPOSITORIES MERGED SUCCESSFULLY!" -ForegroundColor Green
    } elseif (($overallStats.MergedPRs + $overallStats.ClosedPRs) -eq $overallStats.TotalPRs -and $overallStats.TotalPRs -gt 0) {
        Write-Host "`n✅ All PRs across all repositories processed!" -ForegroundColor Green
    } elseif ($overallStats.TotalPRs -eq 0) {
        Write-Host "`n✨ No open PRs found in any repository. All repositories are clean!" -ForegroundColor Green
    } elseif ($overallStats.MergedPRs -gt 0 -or $overallStats.ClosedPRs -gt 0) {
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
