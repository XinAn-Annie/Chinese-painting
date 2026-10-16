# 古画题跋 OCR

这里是画基因项目的 PaddleOCR 适配器。它把识别结果统一为文字、坐标、置信度和横竖排方向，供词云、原图高亮和人工复核使用。

## 安装

普通用户直接双击项目根目录的 `启动画基因.bat`。启动器会创建独立虚拟环境并安装依赖。OCR 权重不提交到仓库，首次启动时会从 GitHub Release 下载并分别校验 SHA256，包括书法微调识别模型、文字检测模型和文字方向模型。它们会解压到项目内的 `.models/`。

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

然后打开 `http://127.0.0.1:8000/web_demo/index.html`，上传图片并点击“识别题跋文字”。OCR 由统一服务的 `/services/ocr/` 路径提供，只接受本机网页的图片上传，不把图片提交到外部接口。

默认使用官方 `PP-OCRv5_server_rec` 负责完整题跋和多字文本行。HCSU 微调权重只会在主模型输出低于 0.60 的单个汉字时进行第二次复核，不再用于整行识别。页面保留置信度至少 0.30 的候选，0.30–0.59 会显示低置信度核对提示。

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

默认保留置信度至少 0.30 的候选，网页还要求文字框中心落在题跋检测框内。行书、草书、篆书、残缺题字和印章文字仍可能读不出或读错；低置信度结果需要人工核对。
