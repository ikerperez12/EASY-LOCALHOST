$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$exePath = Join-Path $root "dist\\EasyLocalhost.exe"

function Invoke-Step {
    param(
        [string] $Label,
        [scriptblock] $Command
    )

    Write-Host $Label
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Label"
    }
}

Invoke-Step "Installing build dependencies if needed..." {
    python -m pip install -r requirements.txt
}

Invoke-Step "Running tests..." {
    python -m unittest discover -s tests -v
}

if (Test-Path $exePath) {
    Get-Process EasyLocalhost -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -eq $exePath } |
        ForEach-Object {
            Stop-Process -Id $_.Id -Force
        }
    Start-Sleep -Milliseconds 500

    try {
        Remove-Item $exePath -Force
    } catch {
        Start-Sleep -Seconds 2
        Remove-Item $exePath -Force
    }
}

Invoke-Step "Building EasyLocalhost.exe..." {
    python -m PyInstaller --noconfirm --clean EasyLocalhost.spec
}

if (-not (Test-Path $exePath)) {
    throw "Build completed without producing $exePath"
}

Write-Host ""
Write-Host "Build completed:"
Write-Host "  $exePath"
