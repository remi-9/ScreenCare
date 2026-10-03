# Builds a standalone ScreenCare.exe via pyside6-deploy (Nuitka under the
# hood). Run from the repository root in an activated dev virtualenv:
#
#     .\packaging\build_windows.ps1
#
# See DEVELOPMENT.md's "Building a standalone Windows executable" section
# for prerequisites and the manual smoke-test checklist to run afterward --
# this script only builds; it does not (and cannot) verify the result runs
# correctly. That verification can only happen on a real Windows machine.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Get-Command pyside6-deploy -ErrorAction SilentlyContinue)) {
    Write-Error "pyside6-deploy not found on PATH. Run 'pip install -e `".[dev]`"' in an activated venv first."
    exit 1
}

# pyside6-deploy installs Nuitka itself into the active environment on
# first run if it's missing (see [python] packages in pysidedeploy.spec),
# but doing it explicitly up front gives a clearer failure if pip itself
# can't reach the package index.
python -m pip show nuitka > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Nuitka (required by pyside6-deploy)..."
    python -m pip install nuitka
}

Write-Host "Building ScreenCare.exe via pyside6-deploy (this can take several minutes)..."
pyside6-deploy -c pysidedeploy.spec -f

if ($LASTEXITCODE -ne 0) {
    Write-Error "pyside6-deploy failed -- see the output above."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Build complete. Look under .\dist\ for the standalone build."
Write-Host "Now run the manual smoke-test checklist in DEVELOPMENT.md before considering this build good."
