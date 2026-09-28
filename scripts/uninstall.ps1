param(
    [string]$TaskName = "PaperNewsletterCollect",
    [switch]$RemoveVirtualEnv
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task $TaskName."
}
if ($RemoveVirtualEnv) {
    $venv = Join-Path $root ".venv"
    if (Test-Path -LiteralPath $venv) { Remove-Item -LiteralPath $venv -Recurse -Force }
}
Write-Host "Configuration, state, output, logs, and backups were preserved."
