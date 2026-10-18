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

& $python -m PyInstaller --noconfirm --onefile --console --name MoneyMaxxer-Standalone `
  --distpath 'dist\standalone' `
  --collect-submodules main `
  --collect-submodules whitenoise `
  --add-data 'main/templates;main/templates' `
  --add-data 'main/static;main/static' `
  --add-data 'data;data' `
  --add-data 'README.md;.' `
  portable_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller could not build the standalone MoneyMaxxer executable.' }

$releaseDir = Join-Path (Get-Location) 'dist\MoneyMaxxer'
Copy-Item -Force README.md (Join-Path $releaseDir 'README.md')
Compress-Archive -Path $releaseDir -DestinationPath (Join-Path (Get-Location) 'dist\MoneyMaxxer-Windows.zip') -Force
Copy-Item -Force 'dist\standalone\MoneyMaxxer-Standalone.exe' 'dist\MoneyMaxxer-Standalone.exe'
Write-Host 'Created dist\MoneyMaxxer-Windows.zip and dist\MoneyMaxxer-Standalone.exe'
