"""Local Chinese-painting appreciation service for the ArtGenome demo.

By default Qwen2.5-VL observes the uploaded image without retrieval-augmented
generation. A deterministic, evidence-gated glossary may append conservative
technique terms after inference. The original ZhiHua_QA retrieval and an
OpenAI-compatible remote backend remain available as explicit opt-in modes.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import mimetypes
import os
import re
import threading
from collections import Counter, OrderedDict
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image, ImageOps


HOST = os.getenv("ZHIHUA_GATEWAY_HOST", "127.0.0.1")
PORT = 8000
BACKEND = os.getenv("ZHIHUA_BACKEND", "local").strip().lower()
BASE_URL = os.getenv("ZHIHUA_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("ZHIHUA_API_KEY", "")
REMOTE_MODEL = os.getenv("ZHIHUA_MODEL", "zjuqx/ZhiHua")
MAX_TOKENS = int(os.getenv("ZHIHUA_MAX_TOKENS", "512"))
FOLLOWUP_MAX_TOKENS = int(os.getenv("ZHIHUA_FOLLOWUP_MAX_TOKENS", "512"))
CONTINUATION_MAX_TOKENS = int(os.getenv("ZHIHUA_CONTINUATION_MAX_TOKENS", "192"))
MAX_IMAGE_BYTES = int(os.getenv("ZHIHUA_MAX_IMAGE_BYTES", str(15 * 1024 * 1024)))
RAG_TOP_K = max(1, int(os.getenv("ZHIHUA_RAG_TOP_K", "3")))
USE_KNOWLEDGE_BASE = os.getenv("ZHIHUA_USE_KB", "0").strip().lower() in {
    "1", "true", "yes", "on"
}

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.getenv(
    "ZHIHUA_MODEL_PATH",
    str(PROJECT_ROOT / ".models" / "Qwen2.5-VL-3B-Instruct"),
))
KB_PATH = Path(os.getenv(
    "ZHIHUA_KB_PATH",
    str(PROJECT_ROOT / "data" / "sample_qa_check.tsv"),
))
GLOSSARY_PATH = Path(os.getenv(
    "ZHIHUA_GLOSSARY_PATH",
    str(Path(__file__).resolve().parent / "terminology_glossary.json"),
))
COLOR_DB_PATH = Path(os.getenv(
    "ZHIHUA_COLOR_DB_PATH",
    str(Path(__file__).resolve().parent.parent / "color_namer" / "color_database.json"),
))
OFFLOAD_PATH = Path(os.getenv(
    "ZHIHUA_OFFLOAD_PATH",
    str(Path(__file__).resolve().parent / ".offload"),
))

DEFAULT_PROMPT = """请观察这幅中国画。请只依据画面中能够观察到的内容作答，并按以下结构输出：
1. 画面内容与构图
2. 线条、墨色和颜色的可见特征
3. 空间与物象关系
4. 仅凭当前图片无法确认的信息
请用自然语言描述可见证据，不直接命名具体技法，不解释寓意、情绪或作者意图，不臆测作者、年代、真伪或题跋原文；不确定时请明确说明。"""

TECHNIQUE_LABELS = ("白描", "工笔", "写意", "泼墨", "没骨")
TECHNIQUE_MEANING = (
    "Qwen 根据当前画面在五类技法之间分配的相对倾向，总计 100%；"
    "该数值不是识别概率，也不构成作者、年代或技法鉴定结论。"
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_IMAGE_BYTES
CORS(app, resources={r"/api/*": {"origins": "*"}})

_model = None
_processor = None
_model_device = "unloaded"
_model_quantization = "none"
_load_lock = threading.Lock()
_inference_lock = threading.Lock()
_kb_lock = threading.Lock()
_kb_rows: list[dict[str, str]] = []
_kb_vectors: list[Counter[str]] = []
_kb_idf: dict[str, float] = {}
_glossary: list[dict[str, object]] = []
_traditional_color_names: list[str] = []
_analysis_cache: OrderedDict[str, dict[str, object]] = OrderedDict()
_analysis_cache_lock = threading.Lock()
ANALYSIS_CACHE_SIZE = max(1, int(os.getenv("ZHIHUA_ANALYSIS_CACHE_SIZE", "8")))

COLOR_DEPENDENT_TERMS = {"青绿设色", "浅绛设色", "小青绿"}
TERM_FALLBACKS = {
    "工笔": "细密刻画倾向",
    "写意": "概括表现倾向",
    "白描": "线性勾勒倾向",
    "泼墨": "大面积墨色铺陈倾向",
    "没骨": "弱化轮廓线的表现倾向",
}
INCOMPLETE_CONNECTOR_PATTERN = re.compile(
    r"(?:因此|所以|此外|由此可见|由此|同时|总体而言|总的来说|综上)[，。！？；：、\s]*$"
)
ORPHAN_CONNECTOR_PATTERN = re.compile(
    r"(^|[。！？\n])(?:因此|所以|此外|由此可见|由此|同时|总体而言|总的来说|综上)[，。！？；：、\s]+"
)
GENERIC_COLOR_PATTERN = re.compile(
    r"(?:(?:浅|深|淡|浓|亮|暗|粉|米|乳|银|金|土|砖|赭|朱|绛|靛|翠|藏|天|湖|宝石|橘|橙|紫|青|蓝|红|黄|绿|黑|白|灰|褐|棕){1,4}色"
    r"|墨色|色调|用色|青绿|蓝绿|黑白"
    r"|(?:红|橙|黄|绿|青|蓝|紫|黑|白|灰|褐|棕|金|银)(?=[、，。！？；和与相间]))"
)
COLOR_QUESTION_PATTERN = re.compile(
    r"颜色|色彩|设色|着色|用色|配色|色调|色相|色温|冷暖|墨色|水墨|青绿|浅绛|综合色"
)


def question_mentions_color(text: str) -> bool:
    """Only expose recognized colors when the user's current task asks for them."""
    return bool(COLOR_QUESTION_PATTERN.search(text or ""))


def endpoint_url() -> str:
    if BASE_URL.endswith("/v1"):
        return f"{BASE_URL}/chat/completions"
    return f"{BASE_URL}/v1/chat/completions"


def extract_text(message_content: object) -> str:
    if isinstance(message_content, str):
        return message_content.strip()
    if isinstance(message_content, list):
        parts = []
        for item in message_content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"].strip())
        return "\n".join(part for part in parts if part)
    return ""


def technique_response_contract() -> str:
    labels = "、".join(TECHNIQUE_LABELS)
    return f"""输出格式要求：
- 最终只输出一个合法 JSON 对象，不要使用 Markdown 代码块，也不要在 JSON 前后添加文字。
- JSON 必须包含 `analysis`、`technique_scores`、`technique_evidence` 三个字段。
- `analysis` 是完整的中文赏析正文；正文继续遵守上面的所有边界，不直接给出技法鉴定结论。
- `technique_scores` 必须且只能包含“{labels}”五个键，值为 0 到 100 的数字，并让五项合计为 100。
- `technique_evidence` 使用相同五个键，每项用一句短语说明画面依据；看不清时写“当前画面证据不足”，不得补造细节。
- 这些分数只表示当前画面在五类技法之间的相对视觉倾向，不是识别概率或学术鉴定。"""


def normalize_technique_scores(raw_scores: object) -> dict[str, float] | None:
    if not isinstance(raw_scores, dict):
        return None
    values = []
    for label in TECHNIQUE_LABELS:
        value = raw_scores.get(label)
        if isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        values.append(max(0.0, min(100.0, number)))
    total = sum(values)
    if total <= 0:
        return None
    normalized = [round(value * 100.0 / total, 1) for value in values]
    normalized[max(range(len(normalized)), key=normalized.__getitem__)] += round(
        100.0 - sum(normalized), 1
    )
    return {
        label: max(0.0, min(100.0, round(value, 1)))
        for label, value in zip(TECHNIQUE_LABELS, normalized)
    }


def parse_model_response(raw_output: str) -> tuple[str, dict[str, object]]:
    """Extract the narrative and a validated five-technique distribution."""
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    payload = None
    try:
        candidate = json.loads(cleaned)
        if isinstance(candidate, dict):
            payload = candidate
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for match in re.finditer(r"\{", cleaned):
            try:
                candidate, _ = decoder.raw_decode(cleaned[match.start():])
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict) and isinstance(candidate.get("analysis"), str):
                payload = candidate
                break

    unavailable = {
        "available": False,
        "labels": list(TECHNIQUE_LABELS),
        "scores": {},
        "evidence": {},
        "total": 0,
        "meaning": TECHNIQUE_MEANING,
    }
    if not payload or not isinstance(payload.get("analysis"), str):
        return raw_output.strip(), unavailable

    analysis = payload["analysis"].strip()
    scores = normalize_technique_scores(payload.get("technique_scores"))
    if not scores:
        return analysis, unavailable

    raw_evidence = payload.get("technique_evidence")
    evidence = {}
    for label in TECHNIQUE_LABELS:
        value = raw_evidence.get(label) if isinstance(raw_evidence, dict) else ""
        evidence[label] = re.sub(r"\s+", " ", str(value)).strip()[:240]
    return analysis, {
        "available": True,
        "labels": list(TECHNIQUE_LABELS),
        "scores": scores,
        "evidence": evidence,
        "total": round(sum(scores.values()), 1),
        "meaning": TECHNIQUE_MEANING,
    }


def tokenize(text: str) -> Counter[str]:
    """Small dependency-free tokenizer suitable for the 717-row Chinese KB."""
    normalized = re.sub(r"\s+", "", text.lower())
    chinese = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    tokens = list(chinese)
    tokens.extend(chinese[index:index + 2] for index in range(max(0, len(chinese) - 1)))
    tokens.extend(re.findall(r"[a-z0-9]+", normalized))
    return Counter(token for token in tokens if token)


def load_knowledge_base() -> None:
    global _kb_rows, _kb_vectors, _kb_idf
    if _kb_rows:
        return
    with _kb_lock:
        if _kb_rows:
            return
        if not KB_PATH.is_file():
            raise FileNotFoundError(f"知识库文件不存在：{KB_PATH}")
        with KB_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = [row for row in csv.DictReader(handle, delimiter="\t")
                    if row.get("question") and row.get("answer")]
        vectors = [tokenize(f"{row['question']} {row['answer'][:400]}") for row in rows]
        document_frequency: Counter[str] = Counter()
        for vector in vectors:
            document_frequency.update(vector.keys())
        total = len(rows)
        _kb_idf = {
            token: math.log((total + 1) / (count + 1)) + 1.0
            for token, count in document_frequency.items()
        }
        _kb_rows = rows
        _kb_vectors = vectors


def cosine_similarity(query: Counter[str], document: Counter[str]) -> float:
    shared = query.keys() & document.keys()
    numerator = sum(query[token] * document[token] * (_kb_idf.get(token, 1.0) ** 2)
                    for token in shared)
    query_norm = math.sqrt(sum((count * _kb_idf.get(token, 1.0)) ** 2
                               for token, count in query.items()))
    document_norm = math.sqrt(sum((count * _kb_idf.get(token, 1.0)) ** 2
                                  for token, count in document.items()))
    if not query_norm or not document_norm:
        return 0.0
    return numerator / (query_norm * document_norm)


def retrieve_knowledge(query: str, top_k: int = RAG_TOP_K) -> list[dict[str, str]]:
    load_knowledge_base()
    query_vector = tokenize(query)
    ranked = sorted(
        ((cosine_similarity(query_vector, vector), index)
         for index, vector in enumerate(_kb_vectors)),
        reverse=True,
    )[:top_k]
    results = []
    for score, index in ranked:
        row = _kb_rows[index]
        results.append({
            "index": row.get("index", str(index)),
            "image_path": row.get("image_path", ""),
            "question": row["question"],
            "answer": row["answer"],
            "score": f"{score:.4f}",
        })
    return results


def color_constraint_prompt(allowed_colors: list[str]) -> str:
    if not allowed_colors:
        return "颜色约束：本次没有收到上方颜色识别结果，因此回答中不得出现任何具体颜色名称。"
    phrases = "、".join(format_color_phrase(name) for name in allowed_colors)
    return f"""颜色约束：
- 上方颜色识别只允许以下结果：{phrases}。
- 涉及颜色时，只能逐字使用上述“推测为XX色”格式，不得使用红、蓝、灰、米白、浅灰等普通色名，也不得创造清单外的传统色名。
- 不得把允许清单中的颜色强行对应到无法确认的物象；无法确认位置时可以不谈颜色。"""


def build_grounded_prompt(
    user_prompt: str, references: list[dict[str, str]], allowed_colors: list[str]
) -> str:
    excerpts = []
    for number, item in enumerate(references, 1):
        answer = re.sub(r"\s+", " ", item["answer"]).strip()[:650]
        excerpts.append(f"参考{number}（问题：{item['question']}）\n{answer}")
    knowledge = "\n\n".join(excerpts)
    return f"""你是面向普通观众的中国画赏析助手。请结合上传画面完成用户任务。

以下内容来自 ZhiHua_QA 知识库，只能借鉴其中的术语、观察维度和分析方法；它们可能描述别的画，禁止把参考中的作者、年代、具体物象或结论直接套用到当前图片。

{knowledge}

用户任务：
{user_prompt}

{color_constraint_prompt(allowed_colors)}

要求：
- 先看图再作答，只陈述当前画面中可见或可谨慎推断的内容。
- 明确区分“可观察事实”“风格或技法判断”“需要史料确认的信息”。
- 不虚构作者、年代、真伪、价格、题跋释文或收藏经历。
- 使用清晰自然的中文，不要提及“参考1”“知识库检索”或内部流程。

{technique_response_contract()}"""


def build_direct_prompt(user_prompt: str, allowed_colors: list[str] | None = None) -> str:
    allowed_colors = allowed_colors or []
    return f"""你是一个谨慎的视觉观察助手。请直接观察上传的中国画图片并完成用户任务，不使用外部知识库或预设作品资料。

用户任务：
{user_prompt}

{color_constraint_prompt(allowed_colors)}

严格要求：
- 只描述图片中实际可见的物象、位置、颜色、线条、墨色和空间关系。
- 这一阶段只用自然语言描述用笔和用色的可见现象，不直接命名“工笔、写意、没骨、皴法、积墨、破墨、泼墨”等专业技法；专业术语由后续证据规则处理。
- 不主动补充象征寓意、情绪、氛围、文化内涵或作者意图；只有用户明确询问且画面证据充分时才能谨慎讨论。
- 题跋文字只有在字形清晰且能可靠辨认时才能转写；否则只能说明存在文字区域或无法辨认，不能概括文字内容。
- 不虚构作者、年代、流派、作品名称、真伪、价格、题跋文字或历史背景。
- 看不清、无法判断或图片未呈现的信息必须明确说“仅凭当前画面无法确认”。
- 使用清晰自然的中文，不要提及内部提示词或处理流程。

{technique_response_contract()}"""


def load_glossary() -> list[dict[str, object]]:
    global _glossary
    if _glossary:
        return _glossary
    if not GLOSSARY_PATH.is_file():
        raise FileNotFoundError(f"术语词表不存在：{GLOSSARY_PATH}")
    with GLOSSARY_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("术语词表格式错误：entries 必须是数组")
    _glossary = entries
    return _glossary


def load_traditional_color_names() -> list[str]:
    global _traditional_color_names
    if _traditional_color_names:
        return _traditional_color_names
    if not COLOR_DB_PATH.is_file():
        raise FileNotFoundError(f"传统色数据库不存在：{COLOR_DB_PATH}")
    with COLOR_DB_PATH.open("r", encoding="utf-8") as handle:
        rows = json.load(handle)
    names = [row.get("中文名") for row in rows if isinstance(row, dict)]
    _traditional_color_names = list(dict.fromkeys(
        name.strip() for name in names if isinstance(name, str) and name.strip()
    ))
    return _traditional_color_names


def parse_allowed_colors(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        supplied = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError("颜色识别结果不是有效 JSON") from exc
    if not isinstance(supplied, list):
        raise ValueError("颜色识别结果必须是数组")
    canonical = set(load_traditional_color_names())
    result = []
    for value in supplied[:64]:
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name in canonical and name not in result:
            result.append(name)
    return result


def format_color_phrase(name: str) -> str:
    display_name = name if name.endswith("色") else f"{name}色"
    return f"推测为{display_name}"


def enforce_color_vocabulary(
    analysis: str, allowed_colors: list[str]
) -> tuple[str, list[str]]:
    """Keep only validated palette names and normalize them to 推测为XX色."""
    canonical_names = load_traditional_color_names()
    allowed_set = set(allowed_colors)
    names_pattern = re.compile(
        "(" + "|".join(re.escape(name) for name in sorted(canonical_names, key=len, reverse=True)) + ")色?"
    )
    placeholders: dict[str, str] = {}

    def protect_allowed(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in allowed_set:
            return match.group(0)
        key = f"__ALLOWED_COLOR_{len(placeholders)}__"
        placeholders[key] = format_color_phrase(name)
        return key

    protected = names_pattern.sub(protect_allowed, analysis)
    parts = re.split(r"([，。！？；\n])", protected)
    removed_claims = []
    kept_parts = []
    for part in parts:
        if part in "，。！？；\n":
            kept_parts.append(part)
            continue
        if names_pattern.search(part) or GENERIC_COLOR_PATTERN.search(part):
            if part.strip():
                removed_claims.append(part.strip())
            continue
        kept_parts.append(part)
    filtered = "".join(kept_parts)
    for key, phrase in placeholders.items():
        filtered = filtered.replace(key, phrase)
    filtered = re.sub(r"[，；]{2,}", "，", filtered).strip()
    filtered = re.sub(r"[，；]+([。！？])", r"\1", filtered)
    filtered = re.sub(r"([。！？])[，；]+", r"\1", filtered)
    filtered = re.sub(r"([。！？])(?:[。！？])+", r"\1", filtered)
    filtered = re.sub(r"^[，。！？；\s]+", "", filtered).strip()
    filtered = remove_orphan_connectors(filtered)
    if not filtered:
        filtered = "画面特征仅凭当前图片谨慎判断；具体色名以上方识别结果为准。"
    if allowed_colors:
        palette = "、".join(format_color_phrase(name) for name in allowed_colors)
        filtered = f"{filtered.rstrip()}\n\n上方颜色识别结果（不对应具体物象）：{palette}。"
    return filtered, removed_claims


def normalize_terminology(
    analysis: str, excluded_terms: set[str] | None = None,
) -> tuple[str, list[dict[str, object]], list[str]]:
    """Attach fully evidenced terms and remove unsupported controlled terms."""
    matches = []
    excluded_terms = excluded_terms or set()
    for entry in load_glossary():
        if entry["term"] in excluded_terms:
            continue
        evidence = []
        valid = True
        for group in entry.get("evidence_groups", []):
            group_match = None
            for pattern in group:
                found = re.search(pattern, analysis, flags=re.IGNORECASE)
                if found:
                    group_match = found.group(0)
                    break
            if group_match is None:
                valid = False
                break
            evidence.append(group_match)
        if valid and evidence:
            matches.append({
                "term": entry["term"],
                "label": entry.get("label", entry["term"]),
                "definition": entry["definition"],
                "evidence": evidence,
            })
    matched_terms = {item["term"] for item in matches}
    rejected_terms = [
        entry["term"] for entry in load_glossary()
        if entry["term"] not in matched_terms
        and entry["term"] in analysis
        and not entry.get("preserve_as_natural_language", False)
    ]
    if rejected_terms:
        for term in sorted(rejected_terms, key=len, reverse=True):
            replacement = TERM_FALLBACKS.get(term, "相应的视觉表现倾向")
            analysis = analysis.replace(term, replacement)
        analysis = re.sub(r"^[，。！？；\s]+", "", analysis)
        analysis = re.sub(r"([，；])([。！？])", r"\2", analysis)
        analysis = re.sub(r"[，；]{2,}", "，", analysis).strip()
        analysis = remove_orphan_connectors(analysis)
    if not matches:
        return analysis, [], rejected_terms
    lines = ["\n\n术语规范化（仅依据上文已经描述的可见特征）："]
    for match in matches:
        quoted = "、".join(f"“{item}”" for item in match["evidence"])
        lines.append(
            f"- {match['label']}：对应上文的{quoted}。{match['definition']}"
        )
    return analysis.rstrip() + "\n".join(lines), matches, rejected_terms


def load_local_model():
    global _model, _processor, _model_device, _model_quantization
    if _model is not None:
        return _model, _processor
    with _load_lock:
        if _model is not None:
            return _model, _processor
        if not MODEL_PATH.is_dir():
            raise FileNotFoundError(f"模型目录不存在：{MODEL_PATH}")
        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2_5_VLForConditionalGeneration

        OFFLOAD_PATH.mkdir(parents=True, exist_ok=True)
        kwargs = {"dtype": torch.bfloat16, "low_cpu_mem_usage": True}
        if torch.cuda.is_available():
            use_4bit = os.getenv("ZHIHUA_LOAD_IN_4BIT", "1").strip().lower() in {
                "1", "true", "yes", "on"
            }
            kwargs.update({"device_map": "auto", "max_memory": {0: "7GiB", "cpu": "16GiB"}})
            if use_4bit:
                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.bfloat16,
                )
                _model_quantization = "bitsandbytes-nf4"
            else:
                kwargs["offload_folder"] = str(OFFLOAD_PATH)
                _model_quantization = "bfloat16"
            _model_device = torch.cuda.get_device_name(0)
        else:
            kwargs["device_map"] = {"": "cpu"}
            _model_device = "cpu"
            _model_quantization = "bfloat16"
        _processor = AutoProcessor.from_pretrained(str(MODEL_PATH), local_files_only=True)
        _model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            str(MODEL_PATH), local_files_only=True, **kwargs
        )
        _model.eval()
        return _model, _processor


def local_inference(
    image: Image.Image | None, prompt: str, max_tokens: int | None = None,
) -> tuple[str, bool]:
    import torch

    model, processor = load_local_model()
    content = [{"type": "text", "text": prompt}]
    if image is not None:
        content.insert(0, {"type": "image", "image": image})
    messages = [{"role": "user", "content": content}]
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    processor_kwargs = {"text": [text], "padding": True, "return_tensors": "pt"}
    if image is not None:
        processor_kwargs["images"] = [image]
    inputs = processor(**processor_kwargs)
    input_device = next(parameter.device for parameter in model.parameters()
                        if parameter.device.type != "meta")
    inputs = inputs.to(input_device)
    token_limit = max_tokens or MAX_TOKENS
    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs, max_new_tokens=token_limit, do_sample=False, use_cache=True
        )
    trimmed = [output[len(source):] for source, output in zip(inputs.input_ids, generated_ids)]
    result = processor.batch_decode(
        trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0].strip()
    generated_token_count = max((len(output) for output in trimmed), default=0)
    return result, generated_token_count >= token_limit


def merge_continuation(partial: str, continuation: str) -> str:
    partial = partial.rstrip()
    continuation = continuation.strip()
    if not continuation:
        return partial
    try:
        candidate = json.loads(continuation)
        if isinstance(candidate, dict) and isinstance(candidate.get("analysis"), str):
            return continuation
    except json.JSONDecodeError:
        pass
    max_overlap = min(len(partial), len(continuation), 240)
    for size in range(max_overlap, 7, -1):
        if partial[-size:] == continuation[:size]:
            return partial + continuation[size:]
    return partial + continuation


def continuation_prompt(original_prompt: str, partial: str) -> str:
    return f"""请继续完成下面被长度上限截断的回答。只从中断处继续，不重复已有内容；补全当前句子并自然收束。继续遵守原任务中的事实边界和术语约束。

原任务：
{original_prompt}

已经生成的内容：
{partial}

只输出需要接在后面的文字。"""


def needs_completion(text: str) -> bool:
    return bool(INCOMPLETE_CONNECTOR_PATTERN.search(text or ""))


def remove_incomplete_ending(text: str) -> str:
    cleaned = INCOMPLETE_CONNECTOR_PATTERN.sub("", text or "").rstrip("，；：、 \n")
    if cleaned and cleaned[-1] not in "。！？":
        cleaned += "。"
    return cleaned


def remove_orphan_connectors(text: str) -> str:
    return ORPHAN_CONNECTOR_PATTERN.sub(r"\1", text or "").strip()


def remote_inference(image_bytes: bytes, mime_type: str, prompt: str) -> tuple[str, str, object]:
    if not BASE_URL:
        raise RuntimeError("尚未配置知画远程推理端点 ZHIHUA_BASE_URL")
    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    payload = {
        "model": REMOTE_MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": prompt},
        ]}],
        "temperature": 0.2,
        "max_tokens": MAX_TOKENS,
    }
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    upstream_request = Request(
        endpoint_url(), data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST",
    )
    with urlopen(upstream_request, timeout=180) as response:
        result = json.loads(response.read().decode("utf-8"))
    content = result["choices"][0]["message"]["content"]
    return extract_text(content), result.get("model", REMOTE_MODEL), result.get("usage")


def get_cached_analysis(analysis_id: str) -> dict[str, object] | None:
    if not analysis_id:
        return None
    with _analysis_cache_lock:
        cached = _analysis_cache.get(analysis_id)
        if cached is not None:
            _analysis_cache.move_to_end(analysis_id)
        return cached


def store_cached_analysis(analysis_id: str, payload: dict[str, object]) -> None:
    with _analysis_cache_lock:
        _analysis_cache[analysis_id] = payload
        _analysis_cache.move_to_end(analysis_id)
        while len(_analysis_cache) > ANALYSIS_CACHE_SIZE:
            _analysis_cache.popitem(last=False)


def build_followup_prompt(
    user_prompt: str,
    cached: dict[str, object],
    ocr_text: str,
    allowed_colors: list[str],
) -> str:
    history = cached.get("history") or []
    history_text = "\n".join(
        f"用户：{item.get('question', '')}\n回答：{item.get('answer', '')}"
        for item in history[-4:]
        if isinstance(item, dict)
    )
    return f"""你正在继续回答同一幅中国画的问题。不得重新读取图片；只能使用以下已完成结果和术语库约束。

已有画面赏析：
{cached.get('analysis', '')}

已有五类技法相对倾向：
{json.dumps(cached.get('techniques') or {}, ensure_ascii=False)}

已有 OCR 文本（可能含误识别，必须保守表述）：
{ocr_text or cached.get('ocr_text', '') or '无'}

已有传统色名称：
{'、'.join(allowed_colors) or '本次问题不涉及颜色，不提供颜色信息'}

此前追问记录：
{history_text or '无'}

本次问题：{user_prompt}

请直接给出本次问题的赏析正文；不要声称重新观察了图片，不要重复生成完整的五类评分。
如果用户询问技法，可以直接引用“已有五类技法相对倾向”中的分数与画面依据进行解释；不得重新读取图片或改写这些缓存结果。"""


@app.get("/api/health")
def health():
    kb_error = None
    if USE_KNOWLEDGE_BASE:
        try:
            load_knowledge_base()
        except Exception as exc:
            kb_error = str(exc)
    try:
        glossary_entries = len(load_glossary())
        glossary_error = None
    except Exception as exc:
        glossary_entries = 0
        glossary_error = str(exc)
    try:
        color_vocabulary_entries = len(load_traditional_color_names())
        color_vocabulary_error = None
    except Exception as exc:
        color_vocabulary_entries = 0
        color_vocabulary_error = str(exc)
    return jsonify({
        "ok": kb_error is None and glossary_error is None and color_vocabulary_error is None and (
            BACKEND == "remote" or MODEL_PATH.is_dir()
        ),
        "service": "zhihua-gateway",
        "backend": BACKEND,
        "model": REMOTE_MODEL if BACKEND == "remote" else str(MODEL_PATH),
        "model_loaded": _model is not None,
        "device": _model_device,
        "quantization": _model_quantization,
        "analysis_cache_entries": len(_analysis_cache),
        "knowledge_enabled": USE_KNOWLEDGE_BASE,
        "knowledge_base": str(KB_PATH),
        "knowledge_entries": len(_kb_rows),
        "knowledge_error": kb_error,
        "terminology_glossary": str(GLOSSARY_PATH),
        "terminology_entries": glossary_entries,
        "terminology_error": glossary_error,
        "color_vocabulary": str(COLOR_DB_PATH),
        "color_vocabulary_entries": color_vocabulary_entries,
        "color_vocabulary_error": color_vocabulary_error,
    })


@app.post("/api/appreciate")
def appreciate():
    requested_analysis_id = (request.form.get("analysis_id") or "").strip()
    cached = get_cached_analysis(requested_analysis_id)
    uploaded = request.files.get("image")
    image_bytes = b""
    image = None
    mime_type = ""
    if cached is None:
        if uploaded is None or not uploaded.filename:
            return jsonify({"error": "首次分析必须上传画作图片；后续提问请提供 analysis_id"}), 400
        image_bytes = uploaded.read(MAX_IMAGE_BYTES + 1)
        if not image_bytes:
            return jsonify({"error": "图片内容为空"}), 400
        if len(image_bytes) > MAX_IMAGE_BYTES:
            return jsonify({"error": "图片超过服务允许的大小"}), 413
        mime_type = uploaded.mimetype or ""
        if not mime_type.startswith("image/"):
            mime_type = mimetypes.guess_type(uploaded.filename)[0] or ""
        if not mime_type.startswith("image/"):
            return jsonify({"error": "文件不是受支持的图片"}), 400
    raw_user_prompt = (request.form.get("prompt") or "").strip()
    user_prompt = raw_user_prompt or DEFAULT_PROMPT
    if len(user_prompt) > 2000:
        return jsonify({"error": "问题过长，请控制在 2000 字以内"}), 400
    ocr_text = (request.form.get("ocr_text") or "").strip()[:4000]
    try:
        supplied_colors = parse_allowed_colors(request.form.get("allowed_colors"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    color_requested = question_mentions_color(user_prompt)
    allowed_colors = supplied_colors if color_requested else []

    try:
        if cached is None:
            image = ImageOps.exif_transpose(Image.open(BytesIO(image_bytes))).convert("RGB")
            image.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
        references = retrieve_knowledge(user_prompt) if USE_KNOWLEDGE_BASE else []
        if cached is not None:
            model_prompt = build_followup_prompt(
                user_prompt, cached, ocr_text, allowed_colors
            )
        else:
            model_prompt = (
                build_grounded_prompt(user_prompt, references, allowed_colors)
                if USE_KNOWLEDGE_BASE else build_direct_prompt(user_prompt, allowed_colors)
            )
            if ocr_text:
                model_prompt += f"\n\nOCR 已识别文本（可能含误识别，仅作辅助）：{ocr_text}"
        generation_truncated = False
        continuation_attempted = False
        with _inference_lock:
            if BACKEND == "remote":
                if cached is not None:
                    return jsonify({"error": "远程后端暂不支持无图缓存追问"}), 400
                raw_output, model_name, usage = remote_inference(
                    image_bytes, mime_type, model_prompt
                )
            else:
                inference_result = local_inference(
                    image, model_prompt,
                    FOLLOWUP_MAX_TOKENS if cached is not None else MAX_TOKENS,
                )
                if isinstance(inference_result, tuple):
                    raw_output, generation_truncated = inference_result
                else:
                    raw_output, generation_truncated = inference_result, False
                if generation_truncated:
                    continuation_attempted = True
                    continuation_result = local_inference(
                        image,
                        continuation_prompt(model_prompt, raw_output),
                        CONTINUATION_MAX_TOKENS,
                    )
                    if isinstance(continuation_result, tuple):
                        continuation, continuation_truncated = continuation_result
                    else:
                        continuation, continuation_truncated = continuation_result, False
                    raw_output = merge_continuation(raw_output, continuation)
                    generation_truncated = generation_truncated or continuation_truncated
                model_name = MODEL_PATH.name
                usage = None
    except FileNotFoundError as exc:
        return jsonify({"error": str(exc)}), 503
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        return jsonify({"error": f"远程推理端点返回 HTTP {exc.code}", "detail": detail}), 502
    except (URLError, TimeoutError) as exc:
        return jsonify({"error": f"无法连接远程推理端点：{exc}"}), 502
    except Exception as exc:
        app.logger.exception("appreciation failed")
        return jsonify({"error": f"本地知画赏析失败：{exc}"}), 500

    if not raw_output:
        return jsonify({"error": "模型没有返回可显示的赏析文本"}), 502
    analysis, techniques = parse_model_response(raw_output)
    if not analysis:
        return jsonify({"error": "模型返回的赏析正文为空"}), 502
    if cached is not None and isinstance(cached.get("techniques"), dict):
        techniques = cached["techniques"]
    analysis, removed_color_claims = enforce_color_vocabulary(analysis, allowed_colors)
    incomplete_repaired = False
    if needs_completion(analysis):
        if BACKEND == "local":
            continuation_attempted = True
            with _inference_lock:
                completion_result = local_inference(
                    image,
                    continuation_prompt(model_prompt, analysis),
                    CONTINUATION_MAX_TOKENS,
                )
            if isinstance(completion_result, tuple):
                completion_text, completion_truncated = completion_result
            else:
                completion_text, completion_truncated = completion_result, False
            generation_truncated = generation_truncated or completion_truncated
            completion_analysis, _ = parse_model_response(completion_text)
            if completion_analysis:
                combined = merge_continuation(analysis, completion_analysis)
                analysis, extra_removed_claims = enforce_color_vocabulary(
                    combined, allowed_colors
                )
                removed_color_claims.extend(extra_removed_claims)
        if needs_completion(analysis):
            analysis = remove_incomplete_ending(analysis)
        incomplete_repaired = True
    analysis, terminology_matches, rejected_terms = normalize_terminology(
        analysis, excluded_terms=COLOR_DEPENDENT_TERMS
    )
    if needs_completion(analysis):
        analysis = remove_incomplete_ending(analysis)
        incomplete_repaired = True
    if cached is None:
        analysis_id = hashlib.sha256(image_bytes).hexdigest()[:24]
        store_cached_analysis(analysis_id, {
            "analysis": analysis,
            "techniques": techniques,
            "ocr_text": ocr_text,
            "recognized_colors": supplied_colors,
            "history": [],
        })
        reused_analysis = False
    else:
        analysis_id = requested_analysis_id
        history = cached.setdefault("history", [])
        if isinstance(history, list):
            history.append({"question": user_prompt, "answer": analysis})
            del history[:-6]
        if ocr_text:
            cached["ocr_text"] = ocr_text
        if supplied_colors:
            cached["recognized_colors"] = supplied_colors
        store_cached_analysis(analysis_id, cached)
        reused_analysis = True
    return jsonify({
        "analysis": analysis,
        "analysis_id": analysis_id,
        "reused_analysis": reused_analysis,
        "truncated": generation_truncated,
        "continuation_attempted": continuation_attempted,
        "incomplete_repaired": incomplete_repaired,
        "model": model_name,
        "backend": BACKEND,
        "usage": usage,
        "techniques": techniques,
        "knowledge": {
            "enabled": USE_KNOWLEDGE_BASE,
            "path": str(KB_PATH),
            "entries": len(_kb_rows),
            "retrieved": len(references),
            "reference_ids": [item["index"] for item in references],
        },
        "terminology": {
            "path": str(GLOSSARY_PATH),
            "entries": len(_glossary),
            "matches": terminology_matches,
            "rejected_terms": rejected_terms,
        },
        "colors": {
            "requested": color_requested,
            "required_format": "推测为XX色",
            "allowed_names": allowed_colors,
            "allowed_phrases": [format_color_phrase(name) for name in allowed_colors],
            "removed_claims": removed_color_claims,
        },
    })


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "图片超过服务允许的大小"}), 413


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
