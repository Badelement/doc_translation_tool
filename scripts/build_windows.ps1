$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$distRoot = Join-Path $projectRoot "dist"
$stagingDistRoot = Join-Path $projectRoot "dist_stage"
$buildRoot = Join-Path $projectRoot "build"
$releaseName = "DocTranslationTool"
$packageRealEnv = $env:DOC_TRANS_PACKAGE_REAL_ENV -eq "1"
$version = (& python -c "from doc_translation_tool import __version__; print(__version__)").Trim()
if ([string]::IsNullOrWhiteSpace($version)) {
    throw "Failed to resolve package version."
}
$versionLabel = "v$version"
$releaseDir = Join-Path $distRoot $releaseName
$stagingReleaseDir = Join-Path $stagingDistRoot $releaseName
$zipPath = Join-Path $distRoot "$releaseName-$versionLabel-win64.zip"

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
Write-Host "[build] Package version: $version"
Write-Host "[build] Package real .env: $packageRealEnv"

if (Test-Path $stagingDistRoot) {
    Write-Host "[build] Removing staging dist directory: $stagingDistRoot"
    Remove-Item -Recurse -Force $stagingDistRoot
}

if (Test-Path $buildRoot) {
    Write-Host "[build] Removing existing build directory: $buildRoot"
    Remove-Item -Recurse -Force $buildRoot
}

New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null

if (Test-Path $zipPath) {
    Write-Host "[build] Removing existing release archive: $zipPath"
    Remove-Item -Force $zipPath
}

$versionParts = New-Object System.Collections.Generic.List[int]
$version.Split(".") | ForEach-Object {
    [void]$versionParts.Add([int]$_)
}
while ($versionParts.Count -lt 4) {
    [void]$versionParts.Add(0)
}
$versionTuple = $versionParts -join ", "
$versionInfoPath = Join-Path $buildRoot "windows-version-info.txt"
$versionInfoContent = @(
    "VSVersionInfo(",
    "  ffi=FixedFileInfo(",
    "    filevers=($versionTuple),",
    "    prodvers=($versionTuple),",
    "    mask=0x3f,",
    "    flags=0x0,",
    "    OS=0x40004,",
    "    fileType=0x1,",
    "    subtype=0x0,",
    "    date=(0, 0)",
    "  ),",
    "  kids=[",
    "    StringFileInfo([",
    "      StringTable(",
    "        '040904B0',",
    "        [",
    "          StringStruct('CompanyName', 'Badelement'),",
    "          StringStruct('FileDescription', 'Document Translation Tool'),",
    "          StringStruct('FileVersion', '$version'),",
    "          StringStruct('InternalName', '$releaseName.exe'),",
    "          StringStruct('OriginalFilename', '$releaseName.exe'),",
    "          StringStruct('ProductName', 'Document Translation Tool'),",
    "          StringStruct('ProductVersion', '$version')",
    "        ]",
    "      )",
    "    ]),",
    "    VarFileInfo([VarStruct('Translation', [1033, 1200])])",
    "  ]",
    ")"
)
Set-Content -LiteralPath $versionInfoPath -Value $versionInfoContent -Encoding UTF8
Write-Host "[build] Generated Windows version resource: $versionInfoPath"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $releaseName `
    --distpath $stagingDistRoot `
    --workpath $buildRoot `
    --specpath $buildRoot `
    --version-file $versionInfoPath `
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
if ($packageRealEnv) {
    $runtimeEnvSource = Join-Path $projectRoot ".env"
}
if (-not (Test-Path -LiteralPath $runtimeEnvSource)) {
    throw "Runtime env source not found: $runtimeEnvSource"
}

Copy-Item `
    -LiteralPath $runtimeEnvSource `
    -Destination (Join-Path $stagingReleaseDir ".env") `
    -Force
Write-Host "[build] Copied runtime env template from: $runtimeEnvSource"

foreach ($fileName in $templateFiles) {
    $source = Join-Path $projectRoot $fileName
    if (Test-Path $source) {
        Copy-Item -LiteralPath $source -Destination (Join-Path $stagingReleaseDir $fileName) -Force
        Write-Host "[build] Copied $fileName"
    }
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

if (-not (Test-Path $distRoot)) {
    New-Item -ItemType Directory -Path $distRoot | Out-Null
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
