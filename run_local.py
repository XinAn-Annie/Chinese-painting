"""可移植的一键启动器：安装依赖、下载模型并启动全部本地服务。"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
WEB_PORT = 8000
OCR_PORT = 8004
DETECTOR_PORT = 8005
ZHIHUA_PORT = 8006
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = ROOT / "requirements-local.txt"
INSTALL_MARKER = VENV_DIR / ".installed-requirements.sha256"
MODEL_DIR = ROOT / ".models" / "Qwen2.5-VL-3B-Instruct"
LOG_DIR = ROOT / ".local_logs"
LOCK_PATH = ROOT / ".startup.lock"
CHILDREN: list[tuple[subprocess.Popen, object]] = []
LOCK_HANDLE = None

PIP_INDEX_CANDIDATES = (
    ("PyPI 官方源", "https://pypi.org/simple/"),
    ("阿里云", "https://mirrors.aliyun.com/pypi/simple/"),
    ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple/"),
)


def port_is_open(port: int) -> bool:
    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True
    except OSError:
        return False


def read_health(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=2) as response:
            return json.load(response) if response.status == 200 else None
    except Exception:
        return None


def open_browser(url: str) -> None:
    """Open the demo in the requested browser, with a safe default fallback."""
    browser = os.getenv("ZHIHUA_BROWSER", "default").strip().lower()
    if browser == "edge" and os.name == "nt":
        candidates: list[Path] = []
        command = shutil.which("msedge")
        if command:
            candidates.append(Path(command))
        for variable in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.getenv(variable)
            if base:
                candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")
        for candidate in candidates:
            if candidate.is_file():
                subprocess.Popen(
                    [str(candidate), url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                print(f"[浏览器] 已使用 Microsoft Edge 打开：{url}")
                return
        print("[提示] 未找到 Microsoft Edge，将使用系统默认浏览器。")
    webbrowser.open(url)


def requirements_hash() -> str:
    return hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()


def select_fastest_pip_index(timeout: float = 8.0, attempts: int = 2) -> str:
    """实测候选 PyPI 索引，返回当前网络下响应最快的可用源。"""
    candidates = list(PIP_INDEX_CANDIDATES)
    configured = os.getenv("PIP_INDEX_URL", "").strip()
    if configured and all(url.rstrip("/") != configured.rstrip("/") for _, url in candidates):
        candidates.append(("系统已配置源", configured.rstrip("/") + "/"))

    results: list[tuple[float, str, str]] = []
    print("[测速] 正在选择当前网络下最快的 Python 软件源……", flush=True)
    for name, base_url in candidates:
        samples: list[float] = []
        probe_url = base_url.rstrip("/") + "/pip/"
        for _ in range(attempts):
            started = time.monotonic()
            try:
                request = urllib.request.Request(
                    probe_url,
                    headers={"User-Agent": "Zhihua-Launcher/1.0"},
                )
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    if response.status != 200:
                        raise RuntimeError(f"HTTP {response.status}")
                    response.read(128 * 1024)
                samples.append(time.monotonic() - started)
            except Exception:
                samples = []
                break

        if samples:
            elapsed = median(samples)
            results.append((elapsed, name, base_url))
            print(f"[测速] {name}: {elapsed:.2f} 秒", flush=True)
        else:
            print(f"[测速] {name}: 不可用", flush=True)

    if not results:
        fallback = "https://pypi.org/simple/"
        print(f"[测速] 所有测速请求均失败，回退至：{fallback}", flush=True)
        return fallback

    elapsed, name, selected = min(results)
    print(f"[测速] 已选择 {name}：{selected}（{elapsed:.2f} 秒）", flush=True)
    return selected


def acquire_startup_lock() -> None:
    """避免重复双击后同时安装依赖或下载同一模型。"""
    global LOCK_HANDLE
    if os.name != "nt":
        return
    import msvcrt

    LOCK_HANDLE = LOCK_PATH.open("a+b")
    if LOCK_HANDLE.tell() == 0:
        LOCK_HANDLE.write(b"0")
        LOCK_HANDLE.flush()
    LOCK_HANDLE.seek(0)
    try:
        msvcrt.locking(LOCK_HANDLE.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        LOCK_HANDLE.close()
        LOCK_HANDLE = None
        raise RuntimeError("画基因启动器已经在运行，请不要重复双击。") from exc


def ensure_environment() -> None:
    if not VENV_PYTHON.exists():
        free_gb = shutil.disk_usage(ROOT).free / (1024 ** 3)
        if free_gb < 10:
            raise RuntimeError(f"磁盘剩余空间只有 {free_gb:.1f} GB，首次安装至少需要约 10 GB。")
        if free_gb < 20:
            print(f"[提醒] 当前磁盘剩余 {free_gb:.1f} GB，请留意模型与依赖所需空间。")
        print("[首次运行 1/3] 正在创建项目虚拟环境……", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    expected = requirements_hash()
    installed = INSTALL_MARKER.read_text(encoding="utf-8").strip() if INSTALL_MARKER.exists() else ""
    if installed == expected:
        print("[复用] Python 依赖已经安装。")
        return

    print("[首次运行 2/3] 正在安装题跋检测、PaddleOCR 和知画依赖；这可能需要较长时间……", flush=True)
    env = os.environ.copy()
    env.setdefault("PIP_DEFAULT_TIMEOUT", "180")
    if os.getenv("ZHIHUA_AUTO_PIP_INDEX", "").strip().lower() in {"1", "true", "yes", "on"}:
        env["PIP_INDEX_URL"] = select_fastest_pip_index()
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)],
        cwd=ROOT,
        env=env,
        check=True,
    )
    INSTALL_MARKER.write_text(expected, encoding="utf-8")


def model_is_complete(path: Path) -> bool:
    required = [
        path / "config.json",
        path / "model.safetensors.index.json",
        path / "model-00001-of-00002.safetensors",
        path / "model-00002-of-00002.safetensors",
        path / "tokenizer.json",
    ]
    return all(item.is_file() and item.stat().st_size > 0 for item in required) and not any(path.rglob("*.incomplete"))


def ensure_qwen_model() -> Path:
    configured = os.getenv("ZHIHUA_MODEL_PATH")
    if configured:
        target = Path(configured).expanduser().resolve()
        if model_is_complete(target):
            print(f"[复用] Qwen 模型：{target}")
            return target
    else:
        legacy_model = ROOT.parents[1] / "知画知识库" / "Qwen2.5-VL-3B-Instruct"
        for candidate in (MODEL_DIR, legacy_model):
            if model_is_complete(candidate):
                print(f"[复用] Qwen 模型：{candidate}")
                return candidate
        target = MODEL_DIR

    free_gb = shutil.disk_usage(target.parent if target.parent.exists() else ROOT).free / (1024 ** 3)
    if free_gb < 9:
        raise RuntimeError(f"磁盘剩余空间只有 {free_gb:.1f} GB，Qwen 模型下载至少需要约 9 GB 可用空间。")
    print("[首次运行 3/3] 正在下载 Qwen2.5-VL-3B-Instruct（约 7.5 GB，可断点续传）……", flush=True)
    subprocess.run(
        [str(VENV_PYTHON), str(ROOT / "mcp_services" / "zhihua" / "download_model.py"), "--target", str(target)],
        cwd=ROOT,
        check=True,
    )
    if not model_is_complete(target):
        raise RuntimeError(f"Qwen 模型下载后校验未通过：{target}")
    return target


def start_process(name: str, command: list[str], cwd: Path, env: dict | None = None) -> subprocess.Popen:
    LOG_DIR.mkdir(exist_ok=True)
    log = (LOG_DIR / f"{name}.log").open("w", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=creationflags)
    CHILDREN.append((process, log))
    return process


def wait_for_service(name: str, port: int, process: subprocess.Popen, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        health = read_health(port)
        if health and health.get("ok") is True:
            print(f"[就绪] {name}: http://{HOST}:{port}")
            return
        if process.poll() is not None:
            raise RuntimeError(f"{name}启动失败，请查看日志：{LOG_DIR / (name + '.log')}")
        time.sleep(0.5)
    raise TimeoutError(f"等待{name}超时，请查看日志：{LOG_DIR / (name + '.log')}")


def ensure_service(name: str, port: int, command: list[str], cwd: Path, timeout: int, env: dict | None = None) -> None:
    health = read_health(port)
    if health and health.get("ok") is True:
        print(f"[复用] {name}: http://{HOST}:{port}")
        return
    if port_is_open(port):
        raise RuntimeError(f"端口 {port} 已被其他程序占用，且不是可用的{name}服务。")
    process = start_process(name, command, cwd, env=env)
    wait_for_service(name, port, process, timeout)


def cleanup() -> None:
    global LOCK_HANDLE
    for process, log in reversed(CHILDREN):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        log.close()
    if LOCK_HANDLE is not None:
        try:
            import msvcrt
            LOCK_HANDLE.seek(0)
            msvcrt.locking(LOCK_HANDLE.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            LOCK_HANDLE.close()
            LOCK_HANDLE = None


def main() -> int:
    atexit.register(cleanup)
    acquire_startup_lock()
    if sys.version_info < (3, 10):
        raise RuntimeError("需要 Python 3.10 或更高版本，请先安装 64 位 Python。")
    ensure_environment()
    model_path = ensure_qwen_model()
    service_env = os.environ.copy()
    service_env.update({"ZHIHUA_BACKEND": "local", "ZHIHUA_USE_KB": "0", "ZHIHUA_MODEL_PATH": str(model_path)})

    ensure_service("inscription_detector", DETECTOR_PORT, [str(VENV_PYTHON), str(ROOT / "mcp_services" / "inscription_detector" / "server.py")], ROOT, 120, service_env)
    ensure_service("ocr", OCR_PORT, [str(VENV_PYTHON), str(ROOT / "mcp_services" / "ocr" / "server.py")], ROOT, 120, service_env)
    ensure_service("zhihua", ZHIHUA_PORT, [str(VENV_PYTHON), str(ROOT / "mcp_services" / "zhihua" / "server.py")], ROOT, 60, service_env)

    if port_is_open(WEB_PORT):
        print(f"[复用] 网页服务: http://{HOST}:{WEB_PORT}")
    else:
        start_process("web", [str(VENV_PYTHON), "-m", "http.server", str(WEB_PORT), "--bind", HOST], ROOT)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not port_is_open(WEB_PORT):
            time.sleep(0.2)
        if not port_is_open(WEB_PORT):
            raise RuntimeError(f"网页服务启动失败，请查看日志：{LOG_DIR / 'web.log'}")
        print(f"[就绪] 网页服务: http://{HOST}:{WEB_PORT}")

    url = f"http://{HOST}:{WEB_PORT}/web_demo/index.html"
    print(f"\n画基因已启动：{url}")
    print("请保持此窗口开启；按 Ctrl+D 可停止本次启动的服务。")
    open_browser(url)
    try:
        while True:
            if os.name == "nt":
                import msvcrt

                if msvcrt.kbhit() and msvcrt.getwch() == "\x04":
                    print("\n正在停止服务……")
                    return 0
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n正在停止服务……")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\n启动失败：{exc}", file=sys.stderr)
        print("详细日志位于项目的 .local_logs 文件夹。", file=sys.stderr)
        raise SystemExit(1)
