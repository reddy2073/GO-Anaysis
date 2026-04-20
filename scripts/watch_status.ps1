# Live terminal display for LegalDebateAI status updates.
# Run this in any terminal: powershell -ExecutionPolicy Bypass -File scripts\watch_status.ps1

$logFile = "$PSScriptRoot\status_display.log"

# Create log if it doesn't exist
if (-not (Test-Path $logFile)) { "" | Out-File $logFile -Encoding utf8 }

Write-Host "=== LegalDebateAI Status Watcher ===" -ForegroundColor Cyan
Write-Host "Tailing $logFile  (Ctrl+C to stop)" -ForegroundColor DarkGray
Write-Host ""

# Print current STATUS.md immediately so user isn't staring at a blank screen
$statusFile = Join-Path (Split-Path $PSScriptRoot) "STATUS.md"
if (Test-Path $statusFile) {
    Write-Host "--- Current STATUS.md ---" -ForegroundColor Yellow
    Get-Content $statusFile | Write-Host
    Write-Host "--- Live log below (updates on each scheduled run) ---" -ForegroundColor Yellow
    Write-Host ""
}

Get-Content $logFile -Wait -Tail 0
