# 本地题跋区域检测器

这是使用 KnowCP 标注数据训练出的单类检测器。它只负责定位题跋区域，识字仍交给本地 PaddleOCR 服务。

## 启动

在训练环境中运行（该环境已安装 CUDA PyTorch 和 Ultralytics）：

```powershell
cd D:\codex\画基因_项目整理\public_repo
& 'D:\codex\画基因_题跋检测训练\.venv\Scripts\python.exe' .\mcp_services\inscription_detector\server.py
```

服务地址：`http://127.0.0.1:8005`。网页会把图片发送到 `/api/detect-inscriptions`，得到题跋框后再把每个区域发给 8004 端口的 PaddleOCR。

模型文件 `models/inscription_detector_best.pt` 来自本项目的训练结果；数据集来源、许可和训练指标见训练目录中的说明。

训练集 819 张中有 260 张没有题跋标注。1281 个题跋框的中心在画面上方和左右两侧较多，底部较少；靠边的题跋也很常见。服务以模型置信度至少 0.35 作为是否送入 OCR 的门槛，位置统计仅用于安排 OCR 顺序，不硬性排除画面边缘或下方。102 张独立测试图中的 33 张无题跋标注图，在该门槛下没有触发题跋框；这不保证其他画作也没有误报。
