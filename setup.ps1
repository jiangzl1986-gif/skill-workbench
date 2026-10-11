param([switch]$SkipFrontend)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.11 -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv .venv }
    else { throw '请先安装 Python 3.11 或更新版本（提供 venv）' }
    if ($LASTEXITCODE -ne 0) { throw 'Python 环境创建失败' }
}
& '.\.venv\Scripts\python.exe' -X utf8 -m pip install -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Python 依赖安装失败' }
if (-not $SkipFrontend) {
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npmCommand) { throw '请先安装 Node.js 22 LTS（包含 npm）' }
    & '.\.venv\Scripts\python.exe' -B -X utf8 tools/build_frontend.py --npm $npmCommand.Source
    if ($LASTEXITCODE -ne 0) { throw '前端依赖安装或构建失败' }
}
Write-Host '准备完成。运行 start.cmd 打开工作台。'
