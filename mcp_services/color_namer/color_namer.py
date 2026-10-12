import pandas as pd
import os
import re
from fastmcp import FastMCP, Context
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000

# 初始化 MCP 服务
mcp = FastMCP(name="ColorNamer")

# ===== 颜色数据库加载函数 =====
def load_color_database():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'color_database.xlsx')  # ✅ 确保 Excel 文件在此路径

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"颜色数据库文件不存在: {db_path}")

    df = pd.read_excel(db_path)

    def parse_rgb(value):
        try:
            if isinstance(value, str) and value.startswith('['):
                return [int(x) for x in re.findall(r'\d+', value)[:3]]
            if isinstance(value, str) and value.startswith('#'):
                hex_val = value.lstrip('#')
                return [int(hex_val[i:i+2], 16) for i in (0, 2, 4)]
            return list(value)[:3] if hasattr(value, '__iter__') else [0, 0, 0]
        except:
            return [0, 0, 0]

    def convert_to_lab(rgb):
        try:
            return convert_color(sRGBColor(*rgb, is_upscaled=True), LabColor)
        except:
            return LabColor(0, 0, 0)

    df['RGB_parsed'] = df['RGB'].apply(parse_rgb)
    df['lab'] = df['RGB_parsed'].apply(convert_to_lab)

    return df

# ===== 初始化数据库 =====
try:
    color_db = load_color_database()
    print(f"✅ 颜色数据库加载成功，共 {len(color_db)} 条")
except Exception as e:
    print(f"❌ 数据库加载失败: {e}")
    color_db = None

# ===== 颜色匹配函数 =====
def find_closest_color(rgb):
    if color_db is None:
        return {"error": "颜色数据库未加载"}

    try:
        target = convert_color(sRGBColor(*rgb, is_upscaled=True), LabColor)
        min_distance = float('inf')
        closest = None

        for _, row in color_db.iterrows():
            distance = delta_e_cie2000(target, row['lab'])
            if distance < min_distance:
                min_distance = distance
                closest = row

        result = closest.to_dict()
        return {
            "name_zh": result.get("中文名", ""),
            "name_pinyin": result.get("拼音", ""),
            "name_en": result.get("英文译名", ""),
            "hex": result.get("HEX", ""),
            "rgb": result.get("RGB_parsed", []),
            "source": result.get("来源", ""),
            "category": result.get("色系", ""),
            "distance": round(min_distance, 2)
        }
    except Exception as e:
        return {"error": f"匹配失败: {str(e)}"}

# ===== MCP 工具函数 =====
@mcp.tool()
def name_colors(ctx: Context, colors: list) -> dict:
    ctx.logger.info(f"收到颜色列表：{colors}")

    if color_db is None:
        return {"error": "颜色数据库未加载"}

    results = []
    for rgb in colors:
        if not isinstance(rgb, list) or len(rgb) != 3:
            results.append({"error": f"无效的RGB值: {rgb}"})
            continue
        results.append(find_closest_color(rgb))

    return {"color_info": results}

# ===== 启动服务 =====
if __name__ == "__main__":
    mcp.run(transport='http', host="0.0.0.0", port=8002)

