$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

function Invoke-Step {
    param(
        [string]$Name,
        [string]$Directory,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $Directory
    try {
        & $Command
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Backend Python compile" (Join-Path $Root "server") {
    python -m compileall app
}

Invoke-Step "Worker syntax check" $Root {
    python -m py_compile scripts\platform_worker.py
}

Invoke-Step "Desktop build" (Join-Path $Root "desktop") {
    npm run build
}

Invoke-Step "Desktop lint" (Join-Path $Root "desktop") {
    npm run lint
}

$AdminDir = Join-Path $Root "admin"
if (Test-Path $AdminDir) {
    Invoke-Step "Admin build" $AdminDir {
        npm run build
    }
}
else {
    Write-Host ""
    Write-Host "==> Admin build skipped: admin directory is not present in this checkout." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All checks completed." -ForegroundColor Green
