$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$pytestRoot = Join-Path $projectRoot ".tmp\pytest"
$cacheDir = Join-Path $pytestRoot "cache"
$baseTemp = Join-Path $pytestRoot "tmp"

if (-not (Test-Path -LiteralPath $cacheDir)) {
    New-Item -ItemType Directory -Path $cacheDir -Force | Out-Null
}

if (-not (Test-Path -LiteralPath $baseTemp)) {
    New-Item -ItemType Directory -Path $baseTemp -Force | Out-Null
}

Write-Host "[test] Project root: $projectRoot"
Write-Host "[test] Pytest cache dir: $cacheDir"
Write-Host "[test] Pytest base temp: $baseTemp"

$pytestArgs = @(
    "-m",
    "pytest",
    "-o",
    "cache_dir=$cacheDir",
    "--basetemp",
    $baseTemp
)

if ($args.Count -gt 0) {
    $pytestArgs += $args
}

Push-Location $projectRoot
try {
    & python @pytestArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
