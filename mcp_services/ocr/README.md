# 古画题跋 OCR

这里是画基因项目的 PaddleOCR 适配器。它把识别结果统一为文字、坐标、置信度和横竖排方向，供词云、原图高亮和人工复核使用。

## 安装

普通用户直接双击项目根目录的 `启动画基因_Google.bat` 或 `启动画基因_Edge.bat`；启动器会创建独立虚拟环境并安装依赖。书法 OCR 微调权重不提交到仓库，首次启动时会从 GitHub Release 下载、校验 SHA256，并解压到 `.models/PP-OCRv5_server_rec_hcsu_stage1/`。

默认资产名为 `PP-OCRv5_server_rec_hcsu_stage1.zip`。如果发布到其他仓库，可用环境变量 `OCR_MODEL_URL` 覆盖下载直链；私有 Release 可额外设置具有读取权限的 `GITHUB_TOKEN`。也可以通过 `OCR_TEXT_RECOGNITION_MODEL_DIR` 指向已下载的模型目录。

```bash
pip install -r requirements.txt
```

## 使用

```bash
python paddle_ocr_adapter.py path/to/painting.jpg -o ocr_result.json
```

网页联调时启动本地服务：

```bash
python server.py
```

然后打开 `web_demo/index.html`，上传图片并点击“识别题跋文字”。服务监听 `http://127.0.0.1:8004`，只接受本机网页的图片上传，不把图片提交到外部接口。

默认明确使用 `PP-OCRv5_server_rec` 文字识别模型，兼顾简体、繁体、手写、竖排和生僻字等场景。第一次识别时 PaddleOCR 会自动下载模型权重。若需临时指定其他 3.x 识别模型，可使用 `--rec-model 模型名称`，或为本地服务设置 `OCR_TEXT_RECOGNITION_MODEL` 环境变量。结果示例：

```json
[
  {
    "text": "溪山行旅",
    "bbox": [120.0, 80.0, 300.0, 145.0],
    "confidence": 0.91,
    "orientation": "horizontal"
  }
]
```

## 项目边界

默认只返回置信度至少 0.60 的候选，网页还要求文字框中心落在题跋检测框内。行书、草书、篆书、残缺题字和印章文字仍可能读不出或读错；识别结果需要人工核对，未识出时页面不生成词云。
