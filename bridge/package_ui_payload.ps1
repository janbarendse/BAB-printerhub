param(
    [string]$OutputDir = "$(Split-Path -Parent $MyInvocation.MyCommand.Path)\\dist",
    [bool]$IncludeRuntime = $true
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$files = @(
    "src\\__init__.py",
    "src\\logger_module.py",
    "src\\assets\\logo.png",
    "src\\assets\\icons\\arrow_down.svg",
    "src\\assets\\icons\\arrow_up.svg",
    "src\\core\\__init__.py",
    "src\\core\\ui_modal_runner.py",
    "src\\core\\ipc_client.py",
    "src\\core\\config_manager.py",
    "src\\core\\fiscal_ui.py",
    "src\\core\\export_ui.py",
    "src\\core\\config_settings_ui.py",
    "src\\core\\log_viewer.py",
    "src\\core\\salesbook_exporter.py"
)

Write-Host "==> Copying UI payload to $OutputDir"

foreach ($rel in $files) {
    $src = Join-Path $root $rel
    $dst = Join-Path $OutputDir $rel
    $dstDir = Split-Path -Parent $dst
    if (-not (Test-Path $src)) {
        throw "Missing source file: $src"
    }
    if (-not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
    }
    Copy-Item -Force $src $dst
}

Write-Host "==> UI payload copied."

if ($IncludeRuntime) {
    $runtimeSrc = Join-Path $root "ui_runtime"
    $runtimeDst = Join-Path $OutputDir "ui_runtime"
    if (Test-Path $runtimeSrc) {
        Write-Host "==> Copying ui_runtime to $runtimeDst"
        Copy-Item -Recurse -Force $runtimeSrc $runtimeDst
    } else {
        Write-Host "==> ui_runtime not found, skipping runtime copy"
    }
}
