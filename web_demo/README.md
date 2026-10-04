# Web Demo

入口文件是 `index.html`。

双击打开即可运行。上传 JPG、PNG 或 GIF 图片后，页面会进行颜色提取、传统色匹配并生成三维颜色关系图。

页面引用了 Plotly、Three.js 和 Google Fonts 的 CDN 资源，因此 3D 可视化和字体加载需要联网。

直接双击 `index.html` 可运行颜色分析、印章热力图和技法倾向分析。题跋文字识别还需在本机启动下面两个服务；图片不会发送到外部识别 API。

开发模式下请先启动两个本地服务。第一个终端启动 PaddleOCR：

```bash
cd ../mcp_services/ocr
pip install -r requirements.txt
python server.py
```

服务监听 `http://127.0.0.1:8004`。网页只把检测器裁剪出的题跋区域发送到该服务。服务不可用时页面会提示错误，不会改用整张画识字。

第二个终端启动题跋区域检测器（使用训练虚拟环境中的 CUDA PyTorch）：

```powershell
cd D:\codex\画基因_项目整理\public_repo
& 'D:\codex\画基因_题跋检测训练\.venv\Scripts\python.exe' .\mcp_services\inscription_detector\server.py
```

检测器监听 `http://127.0.0.1:8005`。点击“识别题跋文字”后，网页先向 8005 请求题跋框，再将每个裁剪区域发给 8004 的 PaddleOCR，并把文字框坐标还原到原图。无可信题跋框时直接显示“未检测到”，不生成词云。


印章模块使用 `seal-detector.js`，按红色、方形或椭圆边界、内部文字状镂空三级筛选。红色越鲜艳，颜色证据分越高；外形和镂空决定候选所处阶段，鲜艳的纯红色块仍不会被当成高分印章。页面提供叠加图和 24×16 科研矩阵，可导出 PNG 或 JSON。该分数未经标注数据校准，不是统计概率；文字状镂空只检查封闭孔洞、曲折度和分布，不识读印文。朱文印、断边、旋转和很小的印章可能漏检。
