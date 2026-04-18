$repo = "C:\Users\vemul\LegalDebateAI"
$logFile = "$repo\scripts\hourly_push.log"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

Set-Location $repo

$status = git status --porcelain 2>&1
if ($status) {
    git add -A
    git commit -m "chore: auto-sync at $timestamp"
    git push origin master
    "$timestamp [PUSHED] $($status.Count) changes" | Add-Content $logFile
} else {
    "$timestamp [SKIP] nothing to commit" | Add-Content $logFile
}
