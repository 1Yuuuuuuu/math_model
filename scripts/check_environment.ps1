# 运行环境诊断：要求 .venv 已由 bootstrap.ps1 建立；透传 doctor 退出码。
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PATH = (Join-Path $Root '.superpowers\bootstrap-uv\Scripts') + ';' + $env:PATH
Set-Location -LiteralPath $Root
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Error "缺少 .venv：请先运行 scripts\bootstrap.ps1"
    exit 1
}

$env:PYTHONPATH = (Join-Path $Root 'toolkit\src') + ';' + $Root
& $VenvPython -m cumcm_toolkit.environment.doctor
exit $LASTEXITCODE
