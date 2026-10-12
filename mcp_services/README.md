# MCP Services

这里保存画基因项目中的实验性 MCP 服务和本地模型网关：

- `color_extractor/`：读取图片 URL，使用 OpenCV 与 K-means 提取主要颜色。
- `color_namer/`：根据颜色距离匹配传统色数据库。
- `html_generator/`：把颜色信息写入交互式 HTML 模板。
- `ocr/`：PaddleOCR 题跋识别适配器，输出文字框、置信度和横竖排方向，供词云和原图高亮使用。
- `zhihua/`：默认加载本地 Qwen2.5-VL-3B-Instruct，并检索 `ZhiHua_QA` 知识库生成国画赏析；也可切换到远程 OpenAI 兼容端点。

颜色分析和印章热力图不依赖本地服务；题跋识别和知画赏析需要本地服务。普通用户双击项目根目录的 `启动画基因_Google.bat` 或 `启动画基因_Edge.bat`，即可自动安装依赖、下载 Qwen 模型并统一启动所需服务。

不要把虚拟环境、密钥或本地 IDE 配置上传到公开仓库。

## 依赖

一键启动所需依赖统一记录在项目根目录的 `requirements-local.txt`，首次运行时安装到项目自己的 `.venv`，不会写入仓库。

## 启动提示

- `color_extractor/color_extractor.py` 当前使用 STDIO 传输启动。
- `color_namer/color_namer.py` 当前使用 HTTP 传输并监听 8002 端口，启动时会从同目录读取 `color_database.xlsx`。
- `html_generator/html_generator.py` 当前使用 SSE 传输并监听 8003 端口；启动时需要把工作目录设为 `html_generator/`，这样相对路径 `templates/color_visualization.html` 才能找到模板。
- `inscription_detector/server.py` 监听 8005 端口。
- `ocr/server.py` 监听 8004 端口。
- `zhihua/server.py` 监听 8006 端口；首次推理会把模型权重载入显存和内存，需要等待。
- 根目录的 `run_local.py` 负责下载、校验、启动和退出清理。
