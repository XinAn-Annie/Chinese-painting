# ArtGenome / 画基因

画基因是一个面向中国古画学习与视觉分析的本地交互平台。用户上传图片后，页面会执行颜色分析，匹配相似的颜色、题跋区域检测与 OCR、印章候选分析，并使用本地 `Qwen2.5-VL-3B-Instruct` 生成赏析和五类技法相对倾向。
该程序无需任何付费，一次部署后可重复多次使用，为绘画临摹与修复、画面理解，印章分析，技法分析等提供参考。

> 本项目仅授权用于非商业学习、研究和评估。项目代码见 [LICENSE](LICENSE)；Qwen、HCSU、字体和其他依赖各自适用原始许可，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
> 本项目UI设计与前端交互由 https://github.com/18857994724 合作者完成，模型微调，后端搭建以及Debug均由本人完成。

## 已实现功能

- 图片上传、预览和原图定位。
- Canvas 主色提取、K-means 聚类、传统色匹配和 Plotly 三维色彩空间。
- 本地题跋区域检测、PaddleOCR、置信度、原图文字框和词云。
- 印章候选标注、位置矩阵和 PNG/JSON 导出。
- 本地 Qwen 赏析与白描、工笔、写意、泼墨、没骨五类技法相对倾向，当前程序为本地部署`Qwen2.5-VL-3B-Instruct`，完全免费且快捷，但准确率略低，用户可根据自己需求购买API获得更详细的分析材料。
- 同一幅画追问时复用已有画面分析、OCR、颜色和技法结果，不重新识图。
- 专业术语库依据可见证据进行约束；只有问题涉及颜色时才传递当前图片的传统色结果。

## Windows 一键运行

### 环境要求

- Windows 10/11 64 位。
- Windows PowerShell 5.1 或更高版本；**不要求用户预装 Python**。
- 首次运行需联网，建议预留 20 GB 空间。
- 可选 NVIDIA GPU；8 GB 显存使用 4-bit Qwen。无 NVIDIA GPU 时回退到 CPU，生成速度会明显降低。

### 推荐的手动准备（强烈建议完成）

启动器可以自动配置运行环境，但为了减少首次配置失败并便于排查问题，建议用户提前从 [Python 官网 Windows 下载页](https://www.python.org/downloads/windows/) 下载并安装 **64 位 Python 3.12.x**。

使用 NVIDIA 显卡的用户，强烈建议安装与显卡驱动兼容的 **CUDA 版 PyTorch**。双击 `启动画基因.bat` 完成基础环境，再双击 `安装NVIDIA加速.bat`；脚本显示并CUDA 版 PyTorch 和 GPU 版 PaddlePaddle 安装进本项目的 `.venv`。建议使用Edge浏览器，用 `.venv\Scripts\python.exe -m pip install <wheel文件>` 安装，会节省2小时左右的时间，只有把文件下载到电脑并不会启用 GPU。具体 CUDA 版本选择以 `安装NVIDIA加速.bat`中显示的版本为准。

没有 NVIDIA 显卡的用户不需要下载 CUDA 版 PyTorch，可以直接使用 CPU 模式。

### 启动

1. 选择 GitHub **Code → Download ZIP** 并完整解压；不要从其他电脑复制 `.venv` 或 `.models`。
2. 双击 `启动画基因.bat`。
3. 首次启动会在项目内下载 `uv` 和专用的 64 位 Python 3.12，随后创建 `.venv`、安装依赖、下载并校验 OCR/Qwen 模型，全部完成后才启动本地网页。
4. 保持启动窗口开启。页面地址为 `http://127.0.0.1:8000/web_demo/index.html`。
5. 按 `Ctrl+D` 停止本次服务。

可用启动器：

- `启动画基因.bat`：使用系统默认浏览器。
- `修复安装.bat`：保留已下载模型，重新检查 Python 依赖。
- `安装NVIDIA加速.bat`：显式安装 CUDA 版 PyTorch 和 GPU 版 PaddlePaddle。普通启动不自动下载数 GB 的 CUDA 组件。

用户电脑原有的 Python 可以是其他版本，也可以完全没有 Python。启动器只使用项目目录中的 `.bootstrap/` 和 `.venv/`，不会修改系统 Python、系统 `PATH` 或其他项目环境；后续启动会直接复用。若 `.venv` 不是可用的 64 位 Python 3.12，启动器会自动重建该虚拟环境。

已删除功能重复的 Google、Edge 和“加速版”启动脚本；浏览器选择统一交给系统默认设置，下载复用、校验和断点续传仍由 `run_local.py` 管理。

## 本地模型

- Qwen 默认从 ModelScope 下载；失败后自动切换到 GitHub Release 分卷，逐卷校验 SHA256 后合并。
- OCR 启动器会下载文字检测、文字方向和 HCSU 低置信度单字备用模型。
- 官方 `PP-OCRv5_server_rec` 负责完整题跋和多字文本行；HCSU 不作为唯一识别模型。
- 模型保存在 `.models/`，Python 引导文件保存在 `.bootstrap/`，本机环境保存在 `.venv/`；三者都不提交到 Git。
- 项目不调用远程推理 API；上传图片只发送到本机 `127.0.0.1:8000`。

已完成首次安装后，后续启动会复用依赖和模型。首次 OCR 或 Qwen 请求仍需要将模型加载到内存/显存，因此比后续请求慢。

## 服务架构

`run_local.py` 只启动一个 `local_gateway.py` 进程和一个对外端口 `8000`：

```text
127.0.0.1:8000
├─ /web_demo/                         网页与本地静态资源
├─ /services/inscription-detector/   题跋区域检测
├─ /services/ocr/                    PaddleOCR
└─ /services/zhihua/                 本地 Qwen 赏析
```

颜色提取、传统色匹配和印章启发式分析在浏览器内执行，不再依赖 8002/8003/8004/8005/8006 等独立端口。

## 目录

- `web_demo/`：前端页面、本地 Plotly、字体和示例资源。
- `mcp_services/inscription_detector/`：题跋区域检测服务和项目模型。
- `mcp_services/ocr/`：PaddleOCR 适配器与 HTTP 路由。
- `mcp_services/zhihua/`：Qwen 本地推理、分析缓存、术语约束与可选检索。
- `mcp_services/color_namer/color_database.json`：后端允许的传统色名称集。
- `evaluation/`：OCR 评估脚本，不参与普通用户运行。
- `experiments/`：历史实验脚本，不参与普通用户运行。

## 局限

- OCR 对草书、篆书、残损题字和印文仍可能误识，低置信度结果必须人工核对。
- 印章矩阵数值是启发式证据分，不是概率或识别准确率。
- 技法数值是模型对当前画面特征的相对倾向，不是作者、年代、技法或真伪鉴定。
- Qwen 输出只供学习参考，不用于价格评估或真伪鉴定。

## 开发者调试

依赖统一由 `requirements-local.txt` 和 `run_local.py` 管理。单独调试 OCR：

```powershell
& '.\.venv\Scripts\python.exe' .\mcp_services\ocr\paddle_ocr_adapter.py path\to\painting.jpg -o ocr_result.json
```

对外发布前，应在全新 Windows 环境中验证 ZIP 解压、依赖安装、模型下载、单端口启动和真实 OCR/Qwen 推理。
