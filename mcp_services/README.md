# MCP Services

这里保存画基因项目中的三个实验性 MCP 服务：

- `color_extractor/`：读取图片 URL，使用 OpenCV 与 K-means 提取主要颜色。
- `color_namer/`：根据颜色距离匹配传统色数据库。
- `html_generator/`：把颜色信息写入交互式 HTML 模板。
- `ocr/`：PaddleOCR 题跋识别适配器，输出文字框、置信度和横竖排方向，供词云和原图高亮使用。

这些服务不是静态网页运行所必需的。它们需要单独安装 Python 依赖、启动 MCP 服务，并按各自代码中的工具接口调用。

不要把虚拟环境、密钥或本地 IDE 配置上传到公开仓库。

## 依赖

可以按服务分别安装：

```text
fastmcp
opencv-python
numpy
scikit-learn
requests
pandas
openpyxl
colormath
paddleocr
paddlepaddle
```

## 启动提示

- `color_extractor/color_extractor.py` 当前使用 STDIO 传输启动。
- `color_namer/color_namer.py` 当前使用 HTTP 传输并监听 8002 端口，启动时会从同目录读取 `color_database.xlsx`。
- `html_generator/html_generator.py` 当前使用 SSE 传输并监听 8003 端口；启动时需要把工作目录设为 `html_generator/`，这样相对路径 `templates/color_visualization.html` 才能找到模板。

这些是根据现有代码整理出的运行条件，尚未把三个服务重新部署成一个统一应用。
