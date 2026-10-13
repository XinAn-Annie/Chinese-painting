# 古画题跋 OCR

这里是画基因项目的 PaddleOCR 适配器。它把识别结果统一为文字、坐标、置信度和横竖排方向，供词云、原图高亮和人工复核使用。

## 安装

普通用户直接双击项目根目录的 `启动画基因_Google.bat` 或 `启动画基因_Edge.bat`；启动器会创建独立虚拟环境并安装依赖。OCR 权重不提交到仓库，首次启动时会从 GitHub Release 下载并分别校验 SHA256，包括书法微调识别模型、文字检测模型和文字方向模型。它们会解压到项目内的 `.models/`，第一次识别不再临时下载这三套权重。

Release 资产为 `PP-OCRv5_server_rec_hcsu_stage1.zip`、`PP-OCRv6_medium_det.zip` 和 `PP-LCNet_x1_0_textline_ori.zip`。如果发布到其他仓库，可分别使用 `OCR_MODEL_URL`、`OCR_DETECTION_MODEL_URL`、`OCR_ORIENTATION_MODEL_URL` 覆盖下载直链；也可以通过 `OCR_TEXT_RECOGNITION_MODEL_DIR`、`OCR_TEXT_DETECTION_MODEL_DIR`、`OCR_TEXTLINE_ORIENTATION_MODEL_DIR` 指向已下载的模型目录。

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

默认明确使用 HCSU 微调的 `PP-OCRv5_server_rec` 文字识别模型、`PP-OCRv6_medium_det` 文字检测模型和 `PP-LCNet_x1_0_textline_ori` 文字方向模型。若需临时指定其他 3.x 识别模型，可使用 `--rec-model 模型名称`，或为本地服务设置 `OCR_TEXT_RECOGNITION_MODEL` 环境变量。结果示例：

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
