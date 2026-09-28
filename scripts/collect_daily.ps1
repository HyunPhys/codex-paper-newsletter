param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path
if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
}
Set-Location -LiteralPath $ProjectRoot
$logDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logPath = Join-Path $logDir "collect_$stamp.log"
$arguments = @("-m", "paper_newsletter", "collect", "--config", "config/settings.toml")

"[$(Get-Date -Format o)] Starting paper newsletter RSS collection" | Tee-Object -FilePath $logPath
"& $Python $($arguments -join ' ')" | Tee-Object -FilePath $logPath -Append
& $Python @arguments 2>&1 | Tee-Object -FilePath $logPath -Append
$exitCode = $LASTEXITCODE
"[$(Get-Date -Format o)] Exit code: $exitCode" | Tee-Object -FilePath $logPath -Append
exit $exitCode
