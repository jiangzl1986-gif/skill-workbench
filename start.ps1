param([int]$Port=8770, [string]$Runtime='', [switch]$NoBrowser)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath=Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw '请先运行 setup.cmd 安装依赖' }
if (-not (Test-Path -LiteralPath 'apps/web/dist/index.html')) { throw '请先运行 setup.cmd 构建页面' }
if ($Runtime) { $env:SKM_RUNTIME=$Runtime }
if (-not $env:SKM_RUNTIME) { $env:SKM_RUNTIME=Join-Path $env:LOCALAPPDATA 'skill-workbench' }
$env:SKM_PORT=[string]$Port
$env:PYTHONPATH=Join-Path $PSScriptRoot 'services/local_api'
& $pythonPath -B -X utf8 launcher.py --port $Port $(if($NoBrowser){'--no-browser'})
if ($LASTEXITCODE -ne 0) { throw '工作台启动失败，请查看上面的原因' }
