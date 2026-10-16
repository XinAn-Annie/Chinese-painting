# Local services

普通用户不需要单独启动本目录下的服务。项目根目录的 `run_local.py` 会启动 `local_gateway.py`，将三个 Flask 应用挂载到同一个进程和 `127.0.0.1:8000`。

- `inscription_detector/`：定位题跋区域，不识别文字内容。
- `ocr/`：使用 PaddleOCR 识别题跋区域，输出文字、坐标和置信度。
- `zhihua/`：使用本地 Qwen2.5-VL-3B-Instruct 生成赏析和五类技法相对倾向，并执行术语和传统色约束。
- `color_namer/color_database.json`：为后处理提供受控传统色名称；它不是独立 HTTP 服务。

路由：

```text
/services/inscription-detector/api/...
/services/ocr/api/...
/services/zhihua/api/...
```

颜色提取、传统色距离匹配和印章启发式分析已改为浏览器端执行，不再使用历史的 8002/8003 服务。

依赖统一记录在项目根目录 `requirements-local.txt`。不要提交 `.venv`、`.models`、`.offload`、日志、密钥或本地 IDE 配置。
