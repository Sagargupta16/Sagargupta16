# PowerShell script to merge all open PRs automatically
# Repository: MCA-NITW/mca_nitw

param(
    [string]$Owner = "Sagargupta16",
    [string]$Repo = "ai-code-translator",
    [string]$MergeMethod = "merge",  # Options: merge, squash, rebase
    [switch]$CloseUnmergeable = $true  # Close PRs that can't be merged and delete branches
)

Write-Host "Starting automatic PR merge process for $Owner/$Repo" -ForegroundColor Green
Write-Host "Merge method: $MergeMethod" -ForegroundColor Yellow
Write-Host "Close unmergeable PRs: $CloseUnmergeable" -ForegroundColor Yellow
Write-Host "=" * 60

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
    # Get all open PRs
    $openPRs = Get-OpenPRs -Owner $Owner -Repo $Repo
    
    if ($openPRs.Count -eq 0) {
        Write-Host "`nNo open PRs found! All done." -ForegroundColor Green
        exit 0
    }
    
    # Statistics tracking
    $totalPRs = $openPRs.Count
    $mergedCount = 0
    $closedCount = 0
    $skippedCount = 0
    $errorCount = 0
    
    Write-Host "`nStarting merge process for $totalPRs PR(s) - processing from oldest to newest..." -ForegroundColor Blue
    
    # Display PR order for user confirmation
    Write-Host "`nPR Processing Order (oldest to newest):" -ForegroundColor Yellow
    $i = 1
    foreach ($pr in $openPRs) {
        $createdDate = [DateTime]$pr.createdAt
        Write-Host "  $i. PR #$($pr.number): $($pr.title) (Created: $($createdDate.ToString('yyyy-MM-dd')))" -ForegroundColor Gray
        $i++
    }
    Write-Host ""
    
    # Process each PR
    foreach ($pr in $openPRs) {
        $result = Merge-PR -Owner $Owner -Repo $Repo -PRNumber $pr.number -Title $pr.title -MergeMethod $MergeMethod -CloseUnmergeable $CloseUnmergeable
        
        switch ($result) {
            "merged" { $mergedCount++ }
            "closed" { $closedCount++ }
            "skipped" { $skippedCount++ }
            "error" { $errorCount++ }
        }
        
        # Longer delay between operations to allow GitHub to update PR statuses
        Start-Sleep -Seconds 5
    }
    
    # Final summary
    Write-Host "`n" + "=" * 60
    Write-Host "MERGE SUMMARY" -ForegroundColor Magenta
    Write-Host "=" * 60
    Write-Host "Total PRs processed: $totalPRs" -ForegroundColor White
    Write-Host "Successfully merged: $mergedCount" -ForegroundColor Green
    Write-Host "Closed (unmergeable): $closedCount" -ForegroundColor Red
    Write-Host "Skipped: $skippedCount" -ForegroundColor Yellow
    Write-Host "Errors: $errorCount" -ForegroundColor DarkRed
    
    if ($mergedCount -eq $totalPRs) {
        Write-Host "`nALL PRs MERGED SUCCESSFULLY!" -ForegroundColor Green
    } elseif (($mergedCount + $closedCount) -eq $totalPRs) {
        Write-Host "`nAll PRs processed! $mergedCount merged, $closedCount closed." -ForegroundColor Green
    } elseif ($mergedCount -gt 0 -or $closedCount -gt 0) {
        Write-Host "`nPartial success. Some PRs were processed." -ForegroundColor Yellow
    } else {
        Write-Host "`nNo PRs were successfully processed." -ForegroundColor Red
    }
    
}
catch {
    Write-Host "`nScript execution failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host "`nScript completed!" -ForegroundColor Magenta
