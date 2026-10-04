import os
import sys
import cv2
import numpy as np
import requests
from io import BytesIO
from sklearn.cluster import KMeans
from fastmcp import FastMCP
from fastmcp.server import Context
import logging

# 创建 MCP 服务
mcp = FastMCP(name="ColorExtractor")

# 配置日志（输出到 stderr，避免污染 STDIO 协议）
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger("ColorExtractor")

# 缓存分析结果
analysis_cache = {}


def extract_dominant_colors(image_url, n_colors=5):
    """下载图片并提取主要颜色"""
    logger.info(f"下载图片: {image_url}")
    try:
        response = requests.get(image_url)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"下载失败: {e}")
        raise

    img_array = np.frombuffer(BytesIO(response.content).getbuffer(), dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("图像解码失败，可能是URL无效或不是有效图像")

    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    pixels = img.reshape(-1, 3)

    logger.info(f"KMeans 提取 {n_colors} 色")
    kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
    kmeans.fit(pixels)

    colors = kmeans.cluster_centers_.astype(int)
    counts = np.bincount(kmeans.labels_)
    sorted_indices = np.argsort(counts)[::-1]
    dominant_colors = colors[sorted_indices][:n_colors]

    return [color.tolist() for color in dominant_colors]


@mcp.tool()
def health_check(ctx: Context) -> dict:
    """健康检查，返回服务状态"""
    return {"status": "ok", "service": "ColorExtractor"}


@mcp.tool()
def extract_colors(ctx: Context, image_url: str, reuse_cache: bool = True) -> dict:
    """
    从图片中提取主要颜色（RGB）
    
    Args:
        image_url: 图片的 URL
        reuse_cache: 是否复用缓存结果
    """
    logger.info(f"请求 Session: {ctx.session_id} | reuse_cache={reuse_cache}")

    if reuse_cache and image_url in analysis_cache:
        logger.info("使用缓存结果")
        return {
            "colors": analysis_cache[image_url],
            "cached": True
        }

    try:
        colors = extract_dominant_colors(image_url)
        analysis_cache[image_url] = colors
        return {
            "colors": colors,
            "cached": False
        }
    except Exception as e:
        logger.error(f"颜色提取失败: {str(e)}")
        return {"error": str(e)}


def main():
    """启动 MCP 服务（STDIO 模式）"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
