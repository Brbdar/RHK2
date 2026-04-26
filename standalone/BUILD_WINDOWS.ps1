# Refactor v1.33: BUILD_WINDOWS.ps1 - one-command PyInstaller build (supports offline wheelhouse)
$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RootDir

$PythonBin = $env:PYTHON_BIN
if ([string]::IsNullOrWhiteSpace($PythonBin)) { $PythonBin = "python" }

$VenvDir = $env:VENV_DIR
$CleanupVenv = $false
if ([string]::IsNullOrWhiteSpace($VenvDir)) {
    $VenvDir = Join-Path ([System.IO.Path]::GetTempPath()) ("rhk_build_venv_" + [guid]::NewGuid().ToString("N"))
    $CleanupVenv = $true
}

& $PythonBin tools/release_audit.py

try {
    & $PythonBin -m venv $VenvDir

    $Py = Join-Path $VenvDir "Scripts\python.exe"
    $Pip = Join-Path $VenvDir "Scripts\pip.exe"
    $PyInstaller = Join-Path $VenvDir "Scripts\pyinstaller.exe"

    & $Py -m pip install --upgrade pip

    $Wheelhouse = "standalone\wheelhouse"
    $HasWheels = (Test-Path $Wheelhouse) -and ((Get-ChildItem $Wheelhouse -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0)

    if ($HasWheels) {
        & $Py -m pip install --no-index --find-links $Wheelhouse -r requirements.txt
        & $Py -m pip install --no-index --find-links $Wheelhouse pyinstaller
    } else {
        & $Py -m pip install -r requirements.txt
        & $Py -m pip install pyinstaller
    }

    & $PyInstaller --noconfirm --clean standalone\RHK_Befundassistent.spec

    Write-Host "OK: dist\RHK_Befundassistent"
} finally {
    if ($CleanupVenv -and (Test-Path $VenvDir)) {
        Remove-Item -Recurse -Force $VenvDir
    }
}
