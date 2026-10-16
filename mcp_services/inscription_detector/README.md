# 本地题跋区域检测器

这是使用 KnowCP 标注数据训练出的单类检测器。它只负责定位题跋区域，识字仍交给本地 PaddleOCR 服务。

## 启动

普通用户双击项目根目录的 `启动画基因.bat`。启动器会自动安装依赖并启动此服务。首次安装完成后，也可以在项目根目录单独调试：

```powershell
& '.\.venv\Scripts\python.exe' .\mcp_services\inscription_detector\server.py
```

服务地址：`http://127.0.0.1:8000/services/inscription-detector/`。网页得到题跋框后，再通过同一个 8000 端口把每个区域交给 PaddleOCR。

模型文件 `models/inscription_detector_best.pt` 来自本项目的训练结果，仅授权用于非商业研究和评估。训练数据集不在本仓库中分发；发布和第三方许可说明见根目录 `THIRD_PARTY_NOTICES.md`。

训练集 819 张中有 260 张没有题跋标注。1281 个题跋框的中心在画面上方和左右两侧较多，底部较少；靠边的题跋也很常见。服务以模型置信度至少 0.35 作为是否送入 OCR 的门槛，位置统计仅用于安排 OCR 顺序，不硬性排除画面边缘或下方。102 张独立测试图中的 33 张无题跋标注图，在该门槛下没有触发题跋框；这不保证其他画作也没有误报。
