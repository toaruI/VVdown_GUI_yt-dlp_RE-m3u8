import os
import sys
import json
import platform


# =========================================
# 1. 系统与路径常量 (System & Paths)
# =========================================

def get_base_path():
    """获取程序运行的基础路径 (兼容 PyInstaller 打包后的环境)"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = get_base_path()
BIN_DIR = os.path.join(BASE_DIR, "bin")
TRANSLATION_FILE = os.path.join(BASE_DIR, "config", "translations.json")
USER_CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".univ_downloader_config.json")

SYSTEM = platform.system()  # Darwin / Windows / Linux
IS_MAC = SYSTEM == "Darwin"
IS_WIN = SYSTEM == "Windows"

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