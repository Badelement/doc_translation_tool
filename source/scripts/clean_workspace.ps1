$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot

function Remove-WorkspacePath {
    param (
        [Parameter(Mandatory = $true)]
        [string]$TargetPath,

        [Parameter(Mandatory = $true)]
        [string]$DisplayName
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    Remove-Item -LiteralPath $TargetPath -Recurse -Force
    Write-Host "[clean] Removed $DisplayName"
}

$targets = @(
    ".doc_translation_cache",
    ".pytest_cache",
    ".tmp",
    "build",
    "dist_stage"
)

foreach ($target in $targets) {
    $path = Join-Path $projectRoot $target
    Remove-WorkspacePath -TargetPath $path -DisplayName $target
}

Get-ChildItem -LiteralPath $projectRoot -Directory -Force |
    Where-Object { $_.Name -like "pytest-cache-files-*" } |
    ForEach-Object {
        Remove-WorkspacePath -TargetPath $_.FullName -DisplayName $_.Name
    }

Get-ChildItem -LiteralPath $projectRoot -Recurse -Force -Directory |
    Where-Object { $_.Name -eq "__pycache__" } |
    ForEach-Object {
        Remove-WorkspacePath -TargetPath $_.FullName -DisplayName $_.FullName
    }

Write-Host "[clean] Workspace cleanup complete"
