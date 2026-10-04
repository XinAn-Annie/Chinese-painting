"""基于 OCR JSON 的题跋词云实验。"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_ocr_result(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_word_positions(inscriptions: list[dict[str, Any]]) -> tuple[dict[str, int], dict[str, list[dict[str, Any]]]]:
    positions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in inscriptions:
        text = str(item.get("text", ""))
        x1, y1, x2, y2 = item.get("bbox", [0, 0, 0, 0])
        char_width = max(1.0, x2 - x1) / max(1, len(text))
        for index, char in enumerate(text):
            if "\u3400" <= char <= "\u9fff":
                positions[char].append({"x": x1 + index * char_width, "y": y1, "width": char_width, "height": max(1.0, y2 - y1), "conf": item.get("confidence", 0)})
    result = dict(positions)
    return {word: len(value) for word, value in result.items()}, result


def generate_word_cloud(word_freq: dict[str, int], word_positions: dict[str, list[dict[str, Any]]]) -> tuple[str, dict[str, list[dict[str, Any]]]]:
    if not word_freq:
        return "<p>未检测到题字</p>", word_positions
    data = [{"name": word, "value": count} for word, count in word_freq.items()]
    template = """
    <div id="wordcloud" style="width:100%;height:500px;"></div>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.0/dist/echarts.min.js"></script>
    <script>
      const chart = echarts.init(document.getElementById('wordcloud'));
      const wordData = ${word_data};
      chart.setOption({title:{text:'题字文字词云',left:'center',subtext:'点击文字可查看其在画作中的位置'},tooltip:{show:true},series:[{type:'wordCloud',shape:'circle',sizeRange:[20,80],rotationRange:[-45,45],gridSize:8,data:wordData}]});
      chart.on('click', p => { if (typeof highlightWord === 'function') highlightWord(p.data.name); });
      window.addEventListener('resize', () => chart.resize());
    </script>
    """
    return template.replace("${word_data}", json.dumps(data, ensure_ascii=False)), word_positions


def inscription_handler(ocr_json: str | Path) -> dict[str, Any]:
    inscriptions = load_ocr_result(ocr_json)
    word_freq, word_positions = build_word_positions(inscriptions)
    html, _ = generate_word_cloud(word_freq, word_positions)
    return {"title": "题字分析", "html": html, "text": f"检测到 {len(inscriptions)} 处题字，共 {len(word_freq)} 个不同汉字", "word_positions": word_positions, "inscriptions": inscriptions}
