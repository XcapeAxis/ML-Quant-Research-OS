param(
    [switch]$InstallDeps
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if ($InstallDeps) {
    & "$root\.venv\Scripts\python.exe" -m pip install -r "$root\requirements.txt"
    Push-Location "$root\apps\web"
    npm install
    Pop-Location
}

Push-Location "$root\apps\web"
npm run build
Pop-Location

if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    pyinstaller "$root\packaging\platform_api.spec" --noconfirm
} else {
    Write-Warning "PyInstaller not installed; frontend build completed, backend packaging skipped."
}
