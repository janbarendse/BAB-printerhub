$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtimeDir = Join-Path $root "ui_runtime"
$pyVersion = "3.13.1"
$embedZip = "python-$pyVersion-embed-amd64.zip"
$embedUrl = "https://www.python.org/ftp/python/$pyVersion/$embedZip"
$embedZipPath = Join-Path $runtimeDir $embedZip
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getPipPath = Join-Path $runtimeDir "get-pip.py"

Write-Host "==> Preparing ui_runtime at $runtimeDir"
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

Write-Host "==> Downloading Python embeddable runtime $pyVersion"
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZipPath

Write-Host "==> Extracting runtime"
Expand-Archive -Path $embedZipPath -DestinationPath $runtimeDir -Force

$pthFile = Get-ChildItem -Path $runtimeDir -Filter "python*._pth" | Select-Object -First 1
if (-not $pthFile) {
    throw "python*.pth file not found in $runtimeDir"
}

Write-Host "==> Configuring $($pthFile.Name) to enable site-packages"
$lines = Get-Content -Path $pthFile.FullName
$updated = @()
$foundSite = $false
$foundSitePackages = $false

foreach ($line in $lines) {
    if ($line -match "^\s*#\s*import site\s*$") {
        $updated += "import site"
        $foundSite = $true
        continue
    }
    if ($line -match "^\s*import site\s*$") {
        $foundSite = $true
    }
    if ($line -match "^\s*Lib\\site-packages\s*$") {
        $foundSitePackages = $true
    }
    $updated += $line
}

if (-not $foundSitePackages) {
    $updated += "Lib\\site-packages"
}
if (-not $foundSite) {
    $updated += "import site"
}

Set-Content -Path $pthFile.FullName -Value $updated -Encoding ASCII

$pyExe = Join-Path $runtimeDir "python.exe"
if (-not (Test-Path $pyExe)) {
    throw "python.exe not found in $runtimeDir"
}

Write-Host "==> Downloading get-pip.py"
Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath

Write-Host "==> Installing pip"
& $pyExe $getPipPath --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    throw "pip installation failed"
}

Write-Host "==> Installing UI requirements"
& $pyExe -m pip install --no-cache-dir --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    throw "pip bootstrap packages failed"
}

& $pyExe -m pip install --no-cache-dir --upgrade -r (Join-Path $root "requirements-ui.txt")
if ($LASTEXITCODE -ne 0) {
    throw "UI requirements install failed"
}

Write-Host "==> Done. UI runtime ready at $runtimeDir"
