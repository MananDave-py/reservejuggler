$ErrorActionPreference = 'Stop'

$python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
  throw 'Create the project .venv first; see the Run from source section in README.md.'
}
& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Could not install build requirements.' }
& $python -m PyInstaller --noconfirm --onedir --console --name MoneyMaxxer `
  --collect-submodules main `
  --collect-submodules whitenoise `
  --add-data 'main/templates;main/templates' `
  --add-data 'main/static;main/static' `
  --add-data 'data;data' `
  --add-data 'README.md;.' `
  portable_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller could not build MoneyMaxxer.' }

$releaseDir = Join-Path (Get-Location) 'dist\MoneyMaxxer'
Copy-Item -Force README.md (Join-Path $releaseDir 'README.md')
Compress-Archive -Path $releaseDir -DestinationPath (Join-Path (Get-Location) 'dist\MoneyMaxxer-Windows.zip') -Force
Write-Host 'Created dist\MoneyMaxxer-Windows.zip'
