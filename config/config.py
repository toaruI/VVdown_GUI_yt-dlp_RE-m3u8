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
        return os.path.dirname(sys.executable)
    else:
        # 当前文件: .../UniversalDownloader/config/config.py
        # 父目录: .../UniversalDownloader/config
        # 根目录: .../UniversalDownloader
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_config_path():
    """获取 config 文件夹本身的路径"""
    if getattr(sys, 'frozen', False):
        # 打包后，建议把 config 放在 exe 同级或者内部资源里
        # 这里假设打包时 config 文件夹被释放到了 tmp 或者 exe 同级
        return os.path.join(os.path.dirname(sys.executable), "config")
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
        "msg_error": "配置文件丢失",
        "label_log": "日志"
    },
    "en": {
        "title": "Universal Downloader Pro (Fallback)",
        "btn_start": "Start Download",
        "btn_stop": "Stop Download",
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
