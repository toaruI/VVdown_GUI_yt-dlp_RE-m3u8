import json
import os
import platform
import sys


# =========================================
# 1. 系统与路径常量 (System & Paths)
# =========================================

def get_base_path():
    """
    获取项目根目录 (UniversalDownloader/)
    - 如果是打包后的 exe，sys.executable 位于根目录
    - 如果是脚本运行，__file__ 位于 config/config.py，需要向上退两级
    """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        # macOS app bundle: resources are under Contents/Resources
        if sys.platform == 'darwin':
            return os.path.abspath(os.path.join(exe_dir, '..', 'Resources'))
        # Windows / Linux: use executable directory
        return exe_dir
    else:
        # 当前文件: .../UniversalDownloader/config/config.py
        # 父目录: .../UniversalDownloader/config
        # 根目录: .../UniversalDownloader
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path():
    """获取 config 文件夹本身的路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller runtime:
        # macOS: Contents/Resources/config
        # Windows/Linux: <exe_dir>/config
        base = get_base_path()
        return os.path.join(base, "config")
    else:
        return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_path()
CONFIG_DIR = get_config_path()
BIN_DIR = os.path.join(BASE_DIR, "bin")
TRANSLATION_FILE = os.path.join(CONFIG_DIR, "translations.json")
USER_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".univ_downloader_config.json")

# =========================================
# Cookie parsing cache (Performance)
# =========================================

# Enable in-memory cache for matched cookies (recommended)
COOKIE_CACHE_ENABLED = True
COOKIE_PERSISTENT_CACHE_ENABLED = True
COOKIE_PERSISTENT_CACHE_FILE = "cookie_match_cache.json"

# Max number of cached (cookie_path, host) entries
# Small value keeps memory usage predictable
COOKIE_CACHE_MAX_ENTRIES = 64

# =========================================
# System detection
# =========================================
OS_DARWIN = "Darwin"
OS_WINDOWS = "Windows"
OS_LINUX = "Linux"

SUPPORTED_SYSTEMS = {"Darwin", "Windows", "Linux"}

# NOTE:
# platform.system() is only called here.
# Other modules should import SYSTEM / IS_* flags from this file.
SYSTEM = platform.system()  # Darwin / Windows / Linux
IS_MAC = SYSTEM == OS_DARWIN
IS_WIN = SYSTEM == OS_WINDOWS
IS_LINUX = SYSTEM == OS_LINUX

# Architecture detection
# NOTE:
# platform.machine() is only called here.
# Other modules should import IS_ARM / IS_X64 from this file.
MACHINE = platform.machine().lower()

IS_ARM = MACHINE in ("arm64", "aarch64")
IS_X64 = MACHINE in ("x86_64", "amd64")
SUPPORTED_SYSTEMS = {"Darwin", "Windows", "Linux"}

# =========================================
# 2. 翻译数据管理 (Translations)
# =========================================

# 内置后备翻译 (防止 json 文件丢失导致程序崩溃)
_FALLBACK_TRANSLATIONS = {
    "zh": {
        "title": "通用下载器 Pro (Fallback)",
        "btn_start": "开始下载",
        "btn_stop": "停止下载",
        "btn_open_dir": "打开目录",
        "btn_fix_dep": "修复依赖",
        "btn_fix_dep_running": "修复中",
        "engine_native": "内置",
        "engine_aria2": "aria2",
        "engine_re": "RE",
        "msg_error": "配置文件丢失",
        "label_log": "日志"
    },
    "en": {
        "title": "Universal Downloader Pro (Fallback)",
        "btn_start": "Start Download",
        "btn_stop": "Stop Download",
        "btn_open_dir": "Open Folder",
        "btn_fix_dep": "Fix Dependencies",
        "btn_fix_dep_running": "Fixing",
        "engine_native": "Native",
        "engine_aria2": "aria2",
        "engine_re": "RE",
        "msg_error": "Config Missing",
        "label_log": "Logs"
    }
}


def load_translations():
    """尝试加载外部 JSON，失败则返回内置后备数据"""
    if os.path.exists(TRANSLATION_FILE):
        try:
            with open(TRANSLATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading translations: {e}")
            return _FALLBACK_TRANSLATIONS
    print(f"Warning: Translation file not found at {TRANSLATION_FILE}")
    return _FALLBACK_TRANSLATIONS


# 全局翻译字典，其他文件可以直接 import TRANSLATIONS
TRANSLATIONS = load_translations()


# =========================================
# 3. 用户配置管理 (User Config)
# =========================================

def load_user_config():
    """读取用户配置文件，如果不存在返回默认值"""
    defaults = {
        "lang": "en",
        "download_dir": os.path.expanduser("~/Downloads"),
        "cookie_path": ""
    }

    if os.path.exists(USER_CONFIG_FILE):
        try:
            with open(USER_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)  # 使用保存的设置覆盖默认值
        except Exception:
            pass

    return defaults


def save_user_config(config_data):
    """保存用户配置到本地文件"""
    try:
        with open(USER_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Failed to save config: {e}")
