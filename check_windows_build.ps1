# Chopster - Verifikasi lingkungan build Windows (diagnostik, TIDAK mengubah apa pun)
$ErrorActionPreference = 'Continue'
Write-Host ''
Write-Host '============================================'
Write-Host 'Chopster - Diagnostic Windows Build Env'
Write-Host '============================================'

Write-Host ''
Write-Host '[1] Python Launcher / runtimes'
try {
  py --list-paths
  Write-Host '--- list-paths end (exit 0) ---'
} catch { Write-Host "py --list-paths FAILED: $($_.Exception.Message)" }

Write-Host ''
Write-Host '[2] Default 'py' interpreter check'
try {
  $p = py -c "import sys; print(sys.version.split()[0]); print(sys.executable); print('64bit' if sys.maxsize > 2**32 else '32bit')"
  Write-Host $p
} catch { Write-Host "py default FAILED: $($_.Exception.Message)" }

Write-Host ''
Write-Host '[3] 'python' command check'
try {
  $q = python -c "import sys; print(sys.version.split()[0]); print(sys.executable); print('64bit' if sys.maxsize > 2**32 else '32bit')"
  Write-Host $q
} catch { Write-Host "python FAILED: $($_.Exception.Message)" }

Write-Host ''
Write-Host '[4] py -3.12 behavior (exit code + message)'
$tmp = Join-Path $env:TEMP ('py312check_' + [guid]::NewGuid().ToString('N') + '.txt')
cmd /c "py -3.12 -V > `"$tmp`" 2>&1"
$rc = $LASTEXITCODE
$out = Get-Content $tmp -Raw -ErrorAction SilentlyContinue
Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host "exit_code=$rc"
Write-Host "output=$out"

Write-Host ''
Write-Host '============================================'
Write-Host 'SELESAI. Kirim seluruh output ini kepada asisten.'
Write-Host '============================================'
