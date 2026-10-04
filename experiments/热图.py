def detect_seals(image_url):
    """完全动态检测印章位置 - 仅基于用户上传的图像"""
    try:
        # 下载图像
        response = requests.get(image_url)
        if response.status_code != 200:
            return [], f"无法下载图像: HTTP {response.status_code}"
        
        # 转换为OpenCV格式
        img_array = np.frombuffer(response.content, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            return [], "无法解码图像"
        
        # 印章检测 - 使用红色范围检测
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # 红色范围1 (0-10)
        lower_red1 = np.array([0, 100, 100])
        upper_red1 = np.array([10, 255, 255])
        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        
        # 红色范围2 (160-180)
        lower_red2 = np.array([160, 100, 100])
        upper_red2 = np.array([180, 255, 255])
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        
        # 合并红色区域
        mask = cv2.bitwise_or(mask1, mask2)
        
        # 形态学操作增强印章区域
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        
        # 查找轮廓
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        seals = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 100:  # 过滤小区域
                x, y, w, h = cv2.boundingRect(cnt)
                seals.append({
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "img_width": img.shape[1],
                    "img_height": img.shape[0],
                    "area": area
                })
        
        return seals, "成功检测印章"
    
    except Exception as e:
        return [], f"印章检测失败: {str(e)}"

def query_painter_seals(painter_id):
    """从知识库动态查询画家印章位置"""
    try:
        conn = pymysql.connect(
            host=os.getenv('DB_HOST'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            database='ancient_paintings'
        )
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT seal_positions FROM painters WHERE id = %s", (painter_id,))
            result = cursor.fetchone()
            if result and result['seal_positions']:
                return json.loads(result['seal_positions'])
        return []
    except Exception as e:
        print(f"查询画家印章位置失败: {str(e)}")
        return []

def generate_seal_heatmap(seals, painter_seals):
    """完全动态生成印章热图 - 基于检测结果和知识库数据"""
    # 准备热图数据 (归一化坐标)
    heatmap_data = []
    
    # 当前画作印章位置 (归一化到0-100)
    for seal in seals:
        norm_x = seal['x'] / seal['img_width'] * 100
        norm_y = seal['y'] / seal['img_height'] * 100
        heatmap_data.append([norm_x, norm_y, 1])  # 当前印章权重为1
    
    # 画家其他作品印章位置 (知识库数据已经是归一化)
    for seal in painter_seals:
        heatmap_data.append([seal['x'], seal['y'], 0.5])  # 其他印章权重为0.5
    
    # 如果没有检测到任何印章，返回空图表提示
    if not heatmap_data:
        return "<p>未检测到印章</p>", "未检测到印章"
    
    # 动态生成热图HTML
    html_template = """
    <div id="seal-heatmap" style="width:100%;height:500px;"></div>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.0/dist/echarts.min.js"></script>
    <script>
        const chart = echarts.init(document.getElementById('seal-heatmap'));
        const heatData = ${heat_data};
        
        // 热图配置
        const option = {
            title: {
                text: '印章位置热力图',
                left: 'center',
                subtext: '红色区域表示印章出现频率较高'
            },
            tooltip: {
                position: 'top',
                formatter: function(params) {
                    return `位置: (${params.value[0].toFixed(1)}%, ${params.value[1].toFixed(1)}%)<br>密度: ${params.value[2]}`;
                }
            },
            grid: {
                left: '3%',
                right: '7%',
                bottom: '10%',
                containLabel: true
            },
            xAxis: {
                type: 'value',
                name: '水平位置 (%)',
                min: 0,
                max: 100,
                splitLine: { show: false }
            },
            yAxis: {
                type: 'value',
                name: '垂直位置 (%)',
                min: 0,
                max: 100,
                splitLine: { show: false },
                inverse: true  // 图像坐标系 (0,0在左上角)
            },
            visualMap: {
                min: 0,
                max: ${max_value},
                calculable: true,
                orient: 'horizontal',
                left: 'center',
                bottom: 0,
                inRange: {
                    color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
                }
            },
            series: [{
                name: '印章密度',
                type: 'heatmap',
                data: heatData,
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            }]
        };
        
        chart.setOption(option);
        
        // 响应窗口大小变化
        window.addEventListener('resize', function() {
            chart.resize();
        });
    </script>
    """
    
    # 计算最大热度值
    max_value = max([d[2] for d in heatmap_data]) if heatmap_data else 1
    
    # 替换模板中的动态数据
    html_output = (
        html_template
        .replace("${heat_data}", json.dumps(heatmap_data))
        .replace("${max_value}", str(max_value))
    )
    
    return html_output, f"检测到 {len(seals)} 个印章，参考 {len(painter_seals)} 个历史印章位置"

def seal_handler(image_url, knowledge_data):
    """印章分析处理函数 - 完全动态"""
    # 动态检测当前画作印章
    seals, seal_msg = detect_seals(image_url)
    
    # 从知识库获取画家印章位置
    painter_seals = []
    painter_name = "未知画家"
    if knowledge_data:
        painter = knowledge_data[0]  # 取第一个匹配的画家
        painter_name = painter['name']
        painter_seals = query_painter_seals(painter['id'])
    
    # 动态生成热图
    html_chart, chart_msg = generate_seal_heatmap(seals, painter_seals)
    
    # 分析文本
    analysis_text = f"{seal_msg}\n{chart_msg}\n对比画家: {painter_name}"
    
    return {
        "title": "印章位置分析",
        "html": html_chart,
        "text": analysis_text
    }