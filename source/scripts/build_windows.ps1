$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $projectRoot
$distRoot = Join-Path $workspaceRoot "releases"
$windowsDistDir = Join-Path $distRoot "windows"
$stagingDistRoot = Join-Path $projectRoot "dist_stage"
$buildRoot = Join-Path $projectRoot "build"
$releaseName = "DocTranslationTool"
$releaseDir = Join-Path $windowsDistDir $releaseName
$stagingReleaseDir = Join-Path $stagingDistRoot $releaseName
$zipPath = Join-Path $windowsDistDir "$releaseName-win64.zip"
$cleanScript = Join-Path $PSScriptRoot "clean_workspace.ps1"

function Remove-PackagedPath {
    param (
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    if (-not (Test-Path -LiteralPath $TargetPath)) {
        return
    }

    Remove-Item -LiteralPath $TargetPath -Recurse -Force
    Write-Host "[build] Removed unused packaged path: $TargetPath"
}

Write-Host "[build] Project root: $projectRoot"
Write-Host "[build] Workspace root: $workspaceRoot"

if (Test-Path -LiteralPath $cleanScript) {
    Write-Host "[build] Running workspace cleanup script"
    & powershell -ExecutionPolicy Bypass -File $cleanScript
}

if (Test-Path $stagingDistRoot) {
    Write-Host "[build] Removing staging dist directory: $stagingDistRoot"
    Remove-Item -Recurse -Force $stagingDistRoot
}

if (Test-Path $buildRoot) {
    Write-Host "[build] Removing existing build directory: $buildRoot"
    Remove-Item -Recurse -Force $buildRoot
}

if (Test-Path $zipPath) {
    Write-Host "[build] Removing existing release archive: $zipPath"
    Remove-Item -Force $zipPath
}

# 可以通过修改下面的路径来指定 Python 版本
# 例如: C:\Python311\python.exe 或 C:\Users\username\.pyenv\pyenv-win\versions\3.11.0\python.exe
$pythonPath = "python"

& $pythonPath -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stagingDistRoot `
    --workpath $buildRoot `
    --specpath $buildRoot `
    --hidden-import PySide6.QtCore `
    --hidden-import PySide6.QtGui `
    --hidden-import PySide6.QtWidgets `
    app.py

$templateFiles = @(
    "settings.example.json",
    "glossary.example.json",
    "CHANGELOG.md",
    "README.md",
    "PACKAGING.md"
)

$guideFileName = [string]([char]0x4F7F) + [char]0x7528 + [char]0x6307 + [char]0x5357 + ".md"

[string]$runtimeEnvSource = Join-Path $projectRoot ".env.example"
if (-not (Test-Path -LiteralPath $runtimeEnvSource)) {
    $runtimeEnvSource = Join-Path $projectRoot ".env"
}

Copy-Item `
    -LiteralPath $runtimeEnvSource `
    -Destination (Join-Path $stagingReleaseDir ".env") `
    -Force
attrib -H -R -S (Join-Path $stagingReleaseDir ".env")
Write-Host "[build] Copied .env template"

foreach ($fileName in $templateFiles) {
    $source = Join-Path $projectRoot $fileName
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stagingReleaseDir $fileName) -Force
        Write-Host "[build] Copied $fileName"
    }
}

$settingsGuideSource = Get-ChildItem -LiteralPath $projectRoot -File | Where-Object {
    $_.Name -like "settings*.md"
} | Select-Object -First 1
if ($settingsGuideSource -ne $null) {
    Copy-Item -LiteralPath $settingsGuideSource.FullName -Destination (Join-Path $stagingReleaseDir $settingsGuideSource.Name) -Force
    Write-Host "[build] Copied settings guide"
}

$guideSource = Join-Path $projectRoot $guideFileName
if (Test-Path -LiteralPath $guideSource) {
    Copy-Item -LiteralPath $guideSource -Destination (Join-Path $stagingReleaseDir $guideFileName) -Force
    Write-Host "[build] Copied user guide"
}

$translationsDir = Join-Path $stagingReleaseDir "_internal\\PySide6\\translations"
if (Test-Path -LiteralPath $translationsDir) {
    $translationKeepSet = @(
        "qt_en.qm",
        "qt_zh_CN.qm",
        "qtbase_en.qm",
        "qtbase_zh_CN.qm"
    )
    Get-ChildItem -LiteralPath $translationsDir -File | ForEach-Object {
        if ($translationKeepSet -notcontains $_.Name) {
            Remove-Item -LiteralPath $_.FullName -Force
        }
    }
    Write-Host "[build] Pruned Qt translation files"
}

Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\generic")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\networkinformation")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\platforminputcontexts")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\platforms\\qdirect2d.dll")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\platforms\\qminimal.dll")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\platforms\\qoffscreen.dll")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\plugins\\imageformats\\qpdf.dll")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\Qt6Pdf.dll")
Remove-PackagedPath (Join-Path $stagingReleaseDir "_internal\\PySide6\\Qt6VirtualKeyboard.dll")

if (-not (Test-Path $windowsDistDir)) {
    New-Item -ItemType Directory -Path $windowsDistDir | Out-Null
}

if (Test-Path $releaseDir) {
    Write-Host "[build] Clearing existing release directory: $releaseDir"
    Get-ChildItem -LiteralPath $releaseDir -Force | Remove-Item -Recurse -Force
} else {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

Get-ChildItem -LiteralPath $stagingReleaseDir -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $releaseDir -Recurse -Force
}
Write-Host "[build] Synced staged release into dist"

Compress-Archive -Path (Join-Path $releaseDir '*') -DestinationPath $zipPath -Force
Write-Host "[build] Created release archive: $zipPath"

Remove-Item -Recurse -Force $stagingDistRoot
Write-Host "[build] Removed staging dist directory"

Write-Host "[build] Build completed: $releaseDir"
