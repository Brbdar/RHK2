$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projRoot = Resolve-Path (Join-Path $scriptDir "..")
$distRoot = Join-Path $scriptDir "dist\RHK_OFFLINE_WIN64"

$pythonBin = $env:PYTHON_BIN
if ([string]::IsNullOrWhiteSpace($pythonBin)) {
  $pythonBin = "python"
}

& $pythonBin (Join-Path $projRoot "tools\build_windows_offline_kit.py") --output-dir $distRoot --force
