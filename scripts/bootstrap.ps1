# 幂等恢复锁定环境：引导 uv（如缺）→ uv sync --frozen --dev → 报告 Python 版本。
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $Root
$Bootstrap = Join-Path $Root '.superpowers\bootstrap-uv'
$UV = Join-Path $Bootstrap 'Scripts\uv.exe'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$env:UV_CACHE_DIR = Join-Path $Root '.superpowers\uv-cache'

if (-not (Test-Path $UV)) {
    Write-Host "bootstrapping uv..."
    python -m venv $Bootstrap
    & (Join-Path $Bootstrap 'Scripts\python.exe') -m pip install --quiet uv==0.12.5
    if ($LASTEXITCODE -ne 0) { throw "uv bootstrap failed" }
}

Write-Host "syncing locked environment..."
& $UV sync --frozen --dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

& $VenvPython --version
if ($LASTEXITCODE -ne 0) { throw ".venv python check failed" }
