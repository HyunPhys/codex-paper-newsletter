param(
    [string]$OutputDirectory = "dist",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Split-Path -Parent $PSScriptRoot)).Path
Set-Location -LiteralPath $root
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
& $Python scripts\check_public_tree.py .
if ($LASTEXITCODE -ne 0) { throw "Release builds are allowed only from a sanitized public tree." }
& $Python -m build --sdist --wheel --outdir $OutputDirectory
if ($LASTEXITCODE -ne 0) { throw "Package build failed." }
$zip = Join-Path $OutputDirectory "codex-paper-newsletter-v0.1.0.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
$items = @("paper_newsletter", "automation", "config", "docs", "scripts", "README.md", "LICENSE", "pyproject.toml")
Compress-Archive -Path $items -DestinationPath $zip
Write-Host "Release ZIP: $zip"
