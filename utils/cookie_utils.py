# core/cookie_utils.py
import os
from urllib.parse import urlparse
from functools import lru_cache
from config.config import (
    SYSTEM, IS_MAC, IS_WIN, IS_LINUX,
    COOKIE_CACHE_ENABLED, COOKIE_CACHE_MAX_ENTRIES,
    COOKIE_PERSISTENT_CACHE_ENABLED, COOKIE_PERSISTENT_CACHE_FILE,
)
import json
import threading
from pathlib import Path

# ------------------------------
# Persistent cookie match cache
# ------------------------------

_persistent_lock = threading.Lock()
_persistent_cache = None


def _get_persistent_cache_path() -> Path:
    """Return path to persistent cookie cache file."""
    try:
        from config.config import USER_CONFIG_DIR
        base = Path(USER_CONFIG_DIR)
    except Exception:
        base = Path.home() / ".vdown"
    base.mkdir(parents=True, exist_ok=True)
    return base / COOKIE_PERSISTENT_CACHE_FILE


def _load_persistent_cache() -> dict:
    global _persistent_cache
    if _persistent_cache is not None:
        return _persistent_cache
    path = _get_persistent_cache_path()
    if path.exists():
        try:
            _persistent_cache = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            _persistent_cache = {}
    else:
        _persistent_cache = {}
    return _persistent_cache


def _save_persistent_cache(cache: dict):
    path = _get_persistent_cache_path()
    try:
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _make_cache_key(filepath: str, host: str, mtime: float, max_len: int) -> str:
    return f"{filepath}|{host}|{mtime}|{max_len}"


@lru_cache(maxsize=COOKIE_CACHE_MAX_ENTRIES)
def _read_cookie_cached(filepath: str, host: str, mtime: float, max_len: int) -> str:
    """
    Cached cookie reader keyed by (filepath, host, mtime, max_len).
    Auto-invalidates when file mtime changes.
    """
    cookie_parts = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                fields = line.split('\t')
                if len(fields) >= 7:
                    domain_field = fields[0]
                    name = fields[5]
                    value = fields[6]
                    if domain_field and (domain_field.strip('.') in host or host in domain_field):
                        cookie_parts.append(f"{name}={value}")
        final_cookie = "; ".join(cookie_parts)
        if len(final_cookie) > max_len:
            return final_cookie[:max_len]
        return final_cookie
    except Exception:
        return ""


def parse_cookie_file(filepath: str, target_url: str, max_len: int = 6000):
    """
    读取 Netscape 格式的 cookie txt（例如来自浏览器导出的 cookie 文件），
    返回用于 HTTP 请求的 Cookie header 字符串（"name=value; name2=value2"）。
    - 纯函数：不做日志、不抛出致命异常（调用方可根据返回值判断）。
    - target_url 用于匹配域名（只返回与目标 host 相关的 cookie 条目）。
    """
    if not os.path.exists(filepath):
        return ""

    try:
        parsed = urlparse(target_url)
        host = parsed.netloc.split(':')[0]
        if not host:
            return ""
    except Exception:
        # 解析 URL 失败时不抛出，返回空 cookie
        return ""

    # Persistent disk cache lookup (before full parse)
    if COOKIE_PERSISTENT_CACHE_ENABLED:
        try:
            mtime = os.path.getmtime(filepath)
            key = _make_cache_key(filepath, host, mtime, max_len)
            with _persistent_lock:
                cache = _load_persistent_cache()
                if key in cache:
                    return cache[key]
        except Exception:
            pass

    # Cached path (preferred)
    try:
        if COOKIE_CACHE_ENABLED:
            mtime = os.path.getmtime(filepath)
            result = _read_cookie_cached(filepath, host, mtime, max_len)
            # Save to persistent cache
            if COOKIE_PERSISTENT_CACHE_ENABLED:
                try:
                    key = _make_cache_key(filepath, host, mtime, max_len)
                    with _persistent_lock:
                        cache = _load_persistent_cache()
                        cache[key] = result
                        _save_persistent_cache(cache)
                except Exception:
                    pass
            return result
    except Exception:
        # Fall through to non-cached path
        pass

    # Non-cached path (original behavior)
    cookie_parts = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                fields = line.split('\t')
                if len(fields) >= 7:
                    domain_field = fields[0]
                    name = fields[5]
                    value = fields[6]
                    if domain_field and (domain_field.strip('.') in host or host in domain_field):
                        cookie_parts.append(f"{name}={value}")
        final_cookie = "; ".join(cookie_parts)
        if len(final_cookie) > max_len:
            final_cookie = final_cookie[:max_len]
        # Save to persistent cache
        if COOKIE_PERSISTENT_CACHE_ENABLED:
            try:
                mtime = os.path.getmtime(filepath)
                key = _make_cache_key(filepath, host, mtime, max_len)
                with _persistent_lock:
                    cache = _load_persistent_cache()
                    cache[key] = final_cookie
                    _save_persistent_cache(cache)
            except Exception:
                pass
        return final_cookie

    except Exception:
        # 读取或解析出错，返回空字符串以便调用方选择降级行为
        return ""

# ==============================
# Browser cookie / capture plugins (v6multi helpers)
# ==============================

COOKIE_PLUGIN_URLS = {
    # Export cookies.txt for downloader / RE usage
    "cookies_txt": {
        "chrome": "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
        "edge": "https://microsoftedge.microsoft.com/addons/detail/get-cookies-txt/ebbdheafhjncoeidpdijmfmkicnejelp",
        "firefox": "https://addons.mozilla.org/firefox/addon/get-cookies-txt-locally/",
        # Safari has no reliable cookies.txt exporter
        "fallback": "https://github.com/kairi003/Get-cookies.txt-Locally",
    },
    # Network capture helper (alternative path)
    "catcatch": {
        "chrome": "https://chromewebstore.google.com/webstore/detail/cat-catch/jfedfbgedapdagkghmgibemcoggfppbb",
        "edge": "https://microsoftedge.microsoft.com/addons/detail/oohmdefbjalncfplafanlagojlakmjci",
        "firefox": "https://addons.mozilla.org/firefox/addon/cat-catch/",
        "fallback": "https://github.com/xifangczy/cat-catch",
    },
}


def get_supported_browsers(system: str | None = None):
    """
    Return browsers that realistically support cookie plugins on the given OS.
    If `system` is None, fall back to config.config SYSTEM.
    """
    sys_name = system or SYSTEM

    if sys_name == "Darwin":
        # macOS: Safari / Chrome / Firefox
        return {"safari", "chrome", "firefox"}
    elif sys_name == "Windows":
        # Windows: Chrome / Edge / Firefox
        return {"chrome", "edge", "firefox"}
    elif sys_name == "Linux":
        # Linux: Chrome / Firefox
        return {"chrome", "firefox"}
    else:
        # Unknown system: be conservative
        return {"chrome", "firefox"}


def get_plugin_url(plugin: str, browser: str, system: str) -> str:
    """
    Resolve the best browser plugin URL for exporting cookies.txt or capturing requests.
    This is intended for RE / downloader usage, not cookie editing.

    :param plugin: "cookies_txt" | "catcatch"
    :param browser: chrome / edge / firefox / safari / none
    :param system: platform.system() result
    """
    plugin_map = COOKIE_PLUGIN_URLS.get(plugin)
    if not plugin_map:
        return ""

    supported = get_supported_browsers(system)
    if browser not in supported:
        return plugin_map.get("fallback", "")

    return plugin_map.get(browser, plugin_map.get("fallback", ""))


def resolve_cookie_plugin_url(browser: str, system: str, prefer: str = "cookies_txt") -> str:
    """
    High-level helper for UI layer.
    Prefer exporting cookies.txt for RE usage by default.
    OS detection is centralized via config.config.
    """
    return get_plugin_url(prefer, browser, system)
