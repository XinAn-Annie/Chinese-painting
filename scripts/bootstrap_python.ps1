param(
    [ValidateSet("Normal", "Repair", "Nvidia")]
    [string]$Mode = "Normal"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$BootstrapDir = Join-Path $ProjectRoot ".bootstrap"
$UvExe = Join-Path $BootstrapDir "uv.exe"
$VenvDir = Join-Path $ProjectRoot ".venv"
$ProjectPython = Join-Path $VenvDir "Scripts\python.exe"
$InstallMarker = Join-Path $VenvDir ".installed-requirements.sha256"
$RunLocal = Join-Path $ProjectRoot "run_local.py"

function Test-ProjectPython {
    if (-not (Test-Path -LiteralPath $ProjectPython -PathType Leaf)) {
        return $false
    }
    & $ProjectPython -c "import struct,sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') * 8 == 64 else 1)" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Install-LocalUv {
    if (Test-Path -LiteralPath $UvExe -PathType Leaf) {
        return
    }

    Write-Host "[首次配置] 正在下载项目专用环境管理器 uv……"
    New-Item -ItemType Directory -Path $BootstrapDir -Force | Out-Null
    $env:UV_UNMANAGED_INSTALL = $BootstrapDir
    $env:UV_NO_MODIFY_PATH = "1"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $Installer = Invoke-RestMethod -Uri "https://astral.sh/uv/install.ps1" -UseBasicParsing
        & ([scriptblock]::Create($Installer))
    }
    catch {
        throw "uv 下载失败。请检查网络或代理后重试。原始错误：$($_.Exception.Message)"
    }
    finally {
        Remove-Item Env:UV_UNMANAGED_INSTALL -ErrorAction SilentlyContinue
        Remove-Item Env:UV_NO_MODIFY_PATH -ErrorAction SilentlyContinue
    }

    if (-not (Test-Path -LiteralPath $UvExe -PathType Leaf)) {
        throw "uv 安装完成后未找到 $UvExe"
    }
}

try {
    Set-Location -LiteralPath $ProjectRoot

    if (-not (Test-ProjectPython)) {
        if (Test-Path -LiteralPath $VenvDir) {
            Write-Host "[修复] 现有 .venv 不是可用的 64 位 Python 3.12，正在重建……"
            Remove-Item -LiteralPath $VenvDir -Recurse -Force
        }

        Install-LocalUv
        $env:UV_PYTHON_INSTALL_DIR = Join-Path $BootstrapDir "python"
        $env:UV_CACHE_DIR = Join-Path $BootstrapDir "cache"
        $env:UV_PYTHON_INSTALL_BIN = "0"
        $env:UV_MANAGED_PYTHON = "1"

        Write-Host "[首次配置] 正在下载项目专用 Python 3.12（不修改系统 Python）……"
        & $UvExe python install 3.12 --managed-python --no-bin
        if ($LASTEXITCODE -ne 0) {
            throw "项目专用 Python 3.12 下载失败，uv 退出代码：$LASTEXITCODE"
        }

        Write-Host "[首次配置] 正在创建项目虚拟环境 .venv……"
        & $UvExe venv --python 3.12 --managed-python --seed $VenvDir
        if ($LASTEXITCODE -ne 0 -or -not (Test-ProjectPython)) {
            throw "项目虚拟环境创建失败。"
        }
    }
    else {
        Write-Host "[复用] 项目专用 Python 3.12 已就绪。"
    }

    if ($Mode -eq "Repair") {
        $env:ZHIHUA_AUTO_CUDA_INSTALL = "0"
        Remove-Item -LiteralPath $InstallMarker -Force -ErrorAction SilentlyContinue
        Write-Host "[修复] 将重新检查并安装项目依赖；已下载模型会继续复用。"
    }
    elseif ($Mode -eq "Nvidia") {
        $env:ZHIHUA_AUTO_CUDA_INSTALL = "1"
        Write-Host "[NVIDIA] 将安装 CUDA 版 PyTorch 与 GPU 版 PaddlePaddle，首次下载可能达到数 GB。"
    }
    elseif (-not $env:ZHIHUA_AUTO_CUDA_INSTALL) {
        $env:ZHIHUA_AUTO_CUDA_INSTALL = "0"
    }

    & $ProjectPython $RunLocal
    exit $LASTEXITCODE
}
catch {
    Write-Host ""
    Write-Host "启动失败：$($_.Exception.Message)" -ForegroundColor Red
    Write-Host "项目不会修改系统 Python 或系统 PATH。"
    exit 1
}
