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
    python -m pip install -r requirements-dev.txt
}

Invoke-Step "Running tests..." {
    python -m unittest discover -s tests -v
}

Invoke-Step "Running static security scan..." {
    python -m bandit -r src -q
}

Invoke-Step "Auditing Python dependencies..." {
    python -m pip_audit -r requirements.txt
}

if (Test-Path $exePath) {
    Get-Process EasyLocalhost -ErrorAction SilentlyContinue |
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

$hashPath = "$exePath.sha256"
$hash = Get-FileHash $exePath -Algorithm SHA256
"$($hash.Hash)  EasyLocalhost.exe" | Out-File -Encoding ascii $hashPath

Write-Host ""
Write-Host "Build completed:"
Write-Host "  $exePath"
Write-Host "  $hashPath"
Write-Host "SHA256:"
Write-Host "  $($hash.Hash)"
