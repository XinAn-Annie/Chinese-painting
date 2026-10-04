def generate_dynamic_report(analysis_results, image_url):
    """完全动态生成报告 - 确保所有内容基于用户输入"""
    # 基本HTML结构
    html_report = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>古画动态分析报告</title>
        <style>
            body {
                font-family: 'Microsoft YaHei', sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }
            .header {
                text-align: center;
                padding: 20px 0;
                border-bottom: 2px solid #e9ecef;
                margin-bottom: 30px;
            }
            .painting-container {
                position: relative;
                max-width: 800px;
                margin: 0 auto 30px;
                box-shadow: 0 0 20px rgba(0,0,0,0.1);
                border-radius: 8px;
                overflow: hidden;
            }
            #main-painting {
                display: block;
                width: 100%;
                max-height: 70vh;
                object-fit: contain;
            }
            .highlight-box {
                position: absolute;
                border: 2px solid #dc3545;
                background-color: rgba(220, 53, 69, 0.2);
                pointer-events: none;
                z-index: 1000;
                transition: all 0.3s ease;
                border-radius: 4px;
            }
            .analysis-section {
                background: white;
                border-radius: 8px;
                padding: 25px;
                margin-bottom: 30px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.05);
            }
            .section-title {
                color: #1a56db;
                border-bottom: 2px solid #e9ecef;
                padding-bottom: 10px;
                margin-top: 0;
            }
            .chart-container {
                width: 100%;
                height: 500px;
                margin: 20px 0;
            }
            .info-message {
                text-align: center;
                padding: 15px;
                margin: 20px 0;
                background-color: #e2f0ff;
                border-radius: 8px;
                border-left: 4px solid #1a56db;
            }
            .footer {
                text-align: center;
                margin-top: 40px;
                padding-top: 20px;
                border-top: 1px solid #e9ecef;
                color: #6c757d;
                font-size: 0.9rem;
            }
            #word-highlight-msg {
                text-align: center;
                font-weight: bold;
                color: #dc3545;
                margin: 10px 0;
                min-height: 24px;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>古画动态分析报告</h1>
            <p>报告生成时间: {timestamp}</p>
        </div>
        
        <div class="painting-container">
            <img id="main-painting" src="{image_url}" alt="分析画作">
            <div id="word-highlight-msg"></div>
        </div>
        
        {sections}
        
        <div class="footer">
            <p>本报告基于AI技术动态生成，分析结果仅供参考</p>
            <p>© {year} 古画分析智能系统</p>
        </div>
        
        <script>
            // 全局存储词位置数据
            const wordPositions = {word_positions_data};
            
            // 高亮显示文字位置
            function highlightWord(word) {
                // 移除所有现有高亮
                document.querySelectorAll('.highlight-box').forEach(el => el.remove());
                
                // 更新提示信息
                const msgEl = document.getElementById('word-highlight-msg');
                
                // 获取该词的所有位置
                const positions = wordPositions[word];
                if (!positions || positions.length === 0) {
                    msgEl.textContent = `未找到"${word}"的位置信息`;
                    return;
                }
                
                const img = document.getElementById('main-painting');
                const container = document.querySelector('.painting-container');
                
                // 创建高亮框
                positions.forEach(pos => {
                    const scaleX = img.naturalWidth / img.width;
                    const scaleY = img.naturalHeight / img.height;
                    
                    const box = document.createElement('div');
                    box.className = 'highlight-box';
                    box.style.left = `${pos.x / scaleX}px`;
                    box.style.top = `${pos.y / scaleY}px`;
                    box.style.width = `${pos.width / scaleX}px`;
                    box.style.height = `${pos.height / scaleY}px`;
                    box.setAttribute('data-word', word);
                    
                    container.appendChild(box);
                });
                
                // 显示提示信息
                msgEl.textContent = `高亮显示"${word}" (共${positions.length}处位置)`;
                
                // 3秒后自动滚动到图像位置
                setTimeout(() => {
                    container.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 100);
            }
            
            // 图像加载完成后调整高亮框位置
            document.getElementById('main-painting').addEventListener('load', function() {
                // 如果页面加载时已经有高亮词，重新触发高亮
                const highlighted = document.querySelector('.highlight-box');
                if (highlighted) {
                    const word = highlighted.getAttribute('data-word');
                    highlightWord(word);
                }
            });
        </script>
    </body>
    </html>
    """
    
    # 生成报告部分
    sections_html = ""
    for agent_type, result in analysis_results.items():
        section_html = f"""
        <div class="analysis-section">
            <h2 class="section-title">{result.get('title', agent_type)}</h2>
            <div class="chart-container">
                {result['html']}
            </div>
            <div class="analysis-text">
                <p>{result['text']}</p>
            </div>
        </div>
        """
        sections_html += section_html
    
    # 获取当前年份
    current_year = datetime.now().year
    
    # 处理词位置数据
    word_positions_data = analysis_results.get('inscription', {}).get('word_positions', {})
    
    # 确保所有坐标值是数字类型
    for word, positions in word_positions_data.items():
        for pos in positions:
            for key in ['x', 'y', 'width', 'height']:
                if key in pos:
                    pos[key] = float(pos[key])
    
    # 生成最终报告
    final_report = html_report.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        image_url=image_url,
        sections=sections_html,
        word_positions_data=json.dumps(word_positions_data),
        year=current_year
    )
    
    return final_report