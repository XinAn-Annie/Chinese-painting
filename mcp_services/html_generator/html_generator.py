
from fastmcp import FastMCP


# 创建FastMCP服务
mcp = FastMCP(name="HTMLGenerator")

def generate_html(color_info):
    """生成HTML页面"""
    # 从文件读取HTML模板
    with open('templates/color_visualization.html', 'r', encoding='utf-8') as f:
        html_template = f.read()
    
    # 生成颜色数据
    color_lines = []
    for color in color_info:
        rgb_str = f"[{', '.join(map(str, color['RGB']))}]"
        line = f"{color['中文名']}\t{color['拼音']}\t{color['英文译名']}\t{color['HEX']}\t{rgb_str}\t{color['来源']}\t{color['色系']}"
        color_lines.append(line)
    
    color_text = "\n".join(color_lines)
    
    # 插入到HTML
    html_content = html_template.replace(
        '<textarea id="colorInput" placeholder="示例：', 
        f'<textarea id="colorInput" placeholder="示例：" style="display:none;">\n{color_text}</textarea>'
    )
    
    # 添加自动执行脚本
    auto_script = """
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                document.getElementById('generateBtn').click();
                document.querySelector('.input-section').style.display = 'none';
            }, 1000);
        });
    </script>
    """
    
    return html_content.replace('</body>', f'{auto_script}</body>')

@mcp.tool()
def generate_html_page(color_info: list) -> str:
    """
    生成包含颜色数据的交互式HTML页面
    
    参数:
    color_info: 颜色信息列表
    
    返回:
    完整的HTML字符串，可直接在浏览器中渲染
    """
    try:
        html_result = generate_html(color_info)
        return {"html": html_result}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("启动HTML生成服务...")
    print("访问地址: http://localhost:8003")
    mcp.run(transport='sse', host="0.0.0.0", port=8003)
