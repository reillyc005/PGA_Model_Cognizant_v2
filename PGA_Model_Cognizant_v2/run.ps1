$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT

$env:PYTHONPATH = "$ROOT\src"

# Prefer venv python if present
$PY = "python"
if (Test-Path "$ROOT\.venv\Scripts\python.exe") {
  $PY = "$ROOT\.venv\Scripts\python.exe"
}

Write-Host "ROOT: $ROOT"
Write-Host "PYTHONPATH: $env:PYTHONPATH"
Write-Host "Python: $PY"
Write-Host "Running model..."

& $PY -m pga_model --mode pretournament

if ($LASTEXITCODE -ne 0) {
  Write-Host "First run failed (exit=$LASTEXITCODE). Retrying with --refresh..."
  & $PY -m pga_model --mode pretournament --refresh
}

Write-Host "Done. ExitCode=$LASTEXITCODE"
exit $LASTEXITCODE
