$ErrorActionPreference = 'Stop'
$serviceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Resolve-Path (Join-Path $serviceDir '..\..')
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$model = Join-Path $projectRoot '.models\Qwen2.5-VL-3B-Instruct'

if (-not (Test-Path -LiteralPath $python)) {
    throw "未找到项目虚拟环境。请先双击项目根目录的 启动画基因_Google.bat 或 启动画基因_Edge.bat 完成首次安装。"
}
if (-not (Test-Path -LiteralPath (Join-Path $model 'model.safetensors.index.json'))) {
    & $python (Join-Path $serviceDir 'download_model.py') --target $model
}

$env:ZHIHUA_BACKEND = 'local'
$env:ZHIHUA_USE_KB = '0'
$env:ZHIHUA_MODEL_PATH = $model
Set-Location -LiteralPath $serviceDir
& $python (Join-Path $serviceDir 'server.py')
