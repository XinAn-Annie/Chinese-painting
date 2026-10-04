# ArtGenome / 画基因：古画色彩分析交互原型

这是一个面向古画学习与传统色彩研究的交互式原型，探索从图片中提取主要颜色、匹配传统色名称，并通过三维颜色空间帮助用户理解色彩关系。

## 已实现的网页功能

- 图片上传与预览
- 基于 Canvas 的图片采样与主要颜色提取
- K-means 色彩聚类
- 传统色数据库匹配
- 中文色名、拼音、英文名、HEX 与 RGB 信息展示
- Plotly 三维颜色空间可视化
- 浏览器端题跋 OCR、文字框和词云
- 基于红色区域的印章位置热力图
- 基于明暗、边缘、饱和度和留白线索的实验性技法倾向分析；以五轴雷达图显示白描、工笔、写意、泼墨、没骨的独立指数，并结合领先倾向给出小分类参考。技法允许交叉，指数不代表画作中实际占比

## 快速运行

直接打开 `web_demo/index.html` 即可使用。网页依赖 CDN 中的 Plotly、Three.js 和 Google Fonts；如果需要完整显示 3D 图和字体，请保持网络连接。

## 目录说明

- `web_demo/`：可直接运行的静态网页
- `mcp_services/color_extractor/`：图片主色提取 MCP 服务
- `mcp_services/color_namer/`：传统色匹配 MCP 服务和数据库
- `mcp_services/html_generator/`：交互式 HTML 生成 MCP 服务
- `experiments/`：题款词云、印章热图、报告页面实验
- `mcp_services/ocr/`：PaddleOCR 题跋识别适配器，输出文字、坐标和置信度
- `data/`：传统色数据

## 题跋 OCR 试运行

直接打开 `web_demo/index.html` 即可体验颜色分析和浏览器端 OCR。OCR 首次运行需要联网下载繁体中文模型，识别在浏览器本地完成。

如果要使用精度更高、适合开发调试的 PaddleOCR 本地服务，再在独立虚拟环境中安装 `mcp_services/ocr/requirements.txt` 后运行：

```bash
python mcp_services/ocr/paddle_ocr_adapter.py path/to/painting.jpg -o ocr_result.json
```

默认优先使用繁体中文模型。识别结果中的低置信度文字应人工复核；草书、篆书、残缺题字和印章文字不能视为已经可靠识别。

## 项目边界

网页端是可直接演示的交互原型。MCP 服务、词云、印章热图和智能体编排属于分开的技术探索，运行它们需要额外依赖、数据或服务配置。项目不把实验性功能描述为已经部署的完整鉴定系统。

## 贡献说明

本项目的界面、交互流程和网页原型由作者独立完成。后续公开版本会继续补充运行说明、截图和实验边界。
