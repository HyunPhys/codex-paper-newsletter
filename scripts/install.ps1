param(
    [string]$Python = "python",
    [string]$TaskName = "PaperNewsletterCollect",
    [switch]$SkipTaskRegistration
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Set-Location -LiteralPath $root
$version = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0) { throw "Python was not found. Install Python 3.11 or newer." }
$parts = $version.Trim().Split('.')
if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 11)) {
    throw "Python 3.11 or newer is required; found $version."
}

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) { & $Python -m venv .venv }
& $venvPython -m pip install --disable-pip-version-check -e .
if ($LASTEXITCODE -ne 0) { throw "Package installation failed." }

$examples = @{
    "config\settings.example.toml" = "config\settings.toml"
    "config\feeds.example.opml" = "config\feeds.opml"
    "config\profile.example.md" = "config\profile.md"
    "config\my_papers.example.bib" = "config\my_papers.bib"
}
foreach ($source in $examples.Keys) {
    $destination = $examples[$source]
    if (-not (Test-Path -LiteralPath $destination)) {
        Copy-Item -LiteralPath $source -Destination $destination
        Write-Host "Created $destination from example."
    }
}

if (-not $SkipTaskRegistration) {
    $time = & $venvPython -c "from pathlib import Path; from paper_newsletter.config import Settings; print(Settings.from_toml(Path('config/settings.toml')).collection_time)"
    if ($time -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { throw "Invalid collection schedule_time: $time" }
    $script = Join-Path $root "scripts\collect_daily.ps1"
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script`" -ProjectRoot `"$root`" -Python `"$venvPython`""
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $root
    $trigger = New-ScheduledTaskTrigger -Daily -At $time
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $taskSettings -Force | Out-Null
    Write-Host "Registered $TaskName at $time (runs while this user is logged in)."
}

& $venvPython -m paper_newsletter doctor --config config/settings.toml
if ($LASTEXITCODE -ne 0) { throw "Installation completed, but the health check found failures." }
Write-Host "Connect Gmail and create the Codex automation using automation\daily-paper-digest.prompt.md."
