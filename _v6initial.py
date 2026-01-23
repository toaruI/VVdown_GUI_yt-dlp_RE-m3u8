import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import subprocess
import threading
import webbrowser
import platform
from urllib.parse import urlparse
import json, os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_config_path = os.path.join(BASE_DIR, "config", "translations.json")
try:
    with open(_config_path, "r", encoding="utf-8") as _f:
        TRANSLATIONS = json.load(_f)
except Exception:
    TRANSLATIONS = {"zh": {}, "en": {}}


class UniversalDownloader:
    def get_base_path(self):
        import sys
        if getattr(sys, 'frozen', False):
            # 如果是打包后的 exe/app，获取 exe 所在的真实目录
            return os.path.dirname(sys.executable)
        else:
            # 如果是脚本运行，获取脚本所在的目录
            return os.path.dirname(os.path.abspath(__file__))

    def __init__(self, root):
        self.root = root
        self.system = platform.system()  # 获取操作系统 (Darwin / Windows / Linux)

        # === 1. 语言包配置 ===
        self.translations = {
            "zh": {
                # 窗口与标题
                "title": "通用下载器 Pro",
                "system_ready": "已就绪 ✅",
                "system_missing": "未找到，请点击修复",
                "env_check_sys": ">>> 环境检测 (System): yt-dlp ",
                "env_check_local": ">>> 环境检测 (Local): N_m3u8DL-RE ",
                "env_warning_re": ">>> ⚠️ bin 目录未找到 RE (不影响 yt-dlp 使用)\n",

                # 顶部栏
                "btn_open_dir": "📂 打开目录",
                "btn_clear_log": "🧹 清空日志",
                "btn_fix_dep": "🛠️ 修复/安装依赖",

                # 链接区
                "frame_url": " 视频链接 (支持 URL 或 M3U8) ",

                # 权限与工具区
                "frame_tools": " 权限与工具 (Cookie / 插件) ",
                "mode_guest": "游客模式",
                "mode_local_file": "本地文件:",
                "btn_select": "选择...",
                "status_no_file": "未选择",
                "label_get_plugin": "获取插件:",
                "btn_cookie_plugin": "Cookie插件",
                "btn_catcatch": "猫抓(CatCatch)",

                # 下载控制区
                "label_engine": "下载引擎:",
                "engine_native": "yt-dlp原生(稳定)",
                "engine_aria2": "Aria2(URL多核加速)",
                "engine_re": "N_m3u8DL-RE(m3u8推荐)",
                "label_threads": "线程数:",
                "label_save_path": "保存位置:",
                "btn_change_path": "修改路径",
                "btn_start": "🚀 开始执行下载任务",
                "btn_stop": "🛑 停止下载 (点击终止)",

                # 日志区与提示语
                "label_log": "运行日志",
                "msg_input_url": "请输入链接",
                "msg_warning": "提示",
                "msg_finish": "完成",
                "msg_fix_done": "环境修复完成！\n请重启软件以确保生效。",
                "log_cookie_filter": ">>> 正在智能筛选 Cookie (目标: {host})...\n",
                "log_cookie_truncate": "⚠️ Cookie 过长，已自动截断。",
                "log_cookie_none": "⚠️ 未找到匹配 {host} 的 Cookie，将尝试直接下载。",
                "log_cookie_error": "⚠️ Cookie 解析出错",
                "log_re_not_found": "❌ 错误: bin 文件夹里未找到 N_m3u8DL-RE！",
                "log_tip_re_path": "提示: 请确保将工具放入脚本同级的 bin 文件夹中。",
                "log_re_no_browser": "⚠️ RE 引擎不支持浏览器直连，请使用 'Cookie插件' 导出txt。",
                "log_mode_browser": "模式: {} Cookie",
                "log_mode_file": "模式: Cookie 文件",
                "log_warning_guest": "警告: 未选择文件，按游客模式下载",
                "log_exec_cmd": "执行命令",
                "log_save_to": "保存至: {}",
                "log_tip_fix": "提示: 若提示 'command not found'，请点击顶部的【修复依赖】按钮。",
                "log_error_generic": "错误",
                "log_tip_install": "提示: 请检查是否已安装 yt-dlp/ffmpeg。",
                "log_start_re": ">>> 引擎: N_m3u8DL-RE (本地版)\n",
                "log_start_aria2": ">>> 引擎: Aria2 加速\n",
                "log_start_native": ">>> 引擎: Native 原生\n",
                "log_cookie_match": ">>> ✅ 成功加载 {} 条相关 Cookie\n",
                "log_load_cookie_ok": ">>> 已加载上次的 Cookie 文件\n",
                "log_download_success": "\n>>> 🎉 下载成功！\n",
                "log_download_stop": "\n>>> 🛑 下载已终止。\n",
                "log_download_fail": "\n>>> ❌ 下载失败。\n",
                "log_open_dir_error": "无法打开文件夹: {e}\n",
                "log_check_yt_ok": ">>> 环境检测 (System): yt-dlp 已就绪 ✅\n",
                "log_check_yt_fail": ">>> ❌ 环境检测 (System): 未找到 yt-dlp，请点击右上角【修复依赖】\n",
                "log_check_re_ok": ">>> 环境检测 (Local): N_m3u8DL-RE 已就绪 ✅\n",
                "log_check_re_warning": ">>> ⚠️ 环境检测 (Local): bin 目录未找到 N_m3u8DL-RE (不影响 yt-dlp 使用)\n",

                # 右键菜单
                "menu_paste": "粘贴",
                "menu_select_all": "全选"
            },
            "en": {
                # Window & Title
                "title": "Universal Downloader Pro",
                "system_ready": "Ready ✅",
                "system_missing": "Missing, click Fix",
                "env_check_sys": ">>> Env Check (System): yt-dlp ",
                "env_check_local": ">>> Env Check (Local): N_m3u8DL-RE ",
                "env_warning_re": ">>> ⚠️ RE not found in bin (yt-dlp still works)\n",

                # Top Bar
                "btn_open_dir": "📂 Open Folder",
                "btn_clear_log": "🧹 Clear Log",
                "btn_fix_dep": "🛠️ Fix Dependencies",

                # URL Area
                "frame_url": " Video Link (Supports URL or M3U8) ",

                # Cookie & Tools
                "frame_tools": " Permissions & Tools (Cookie / Plugins) ",
                "mode_guest": "Guest Mode",
                "mode_local_file": "Local File:",
                "btn_select": "Select...",
                "status_no_file": "Not Selected",
                "label_get_plugin": "Get Plugins:",
                "btn_cookie_plugin": "Cookie Plugin",
                "btn_catcatch": "CatCatch",

                # Control Area
                "label_engine": "Engine:",
                "engine_native": "yt-dlp Native (Stable)",
                "engine_aria2": "Aria2 (Multi-core)",
                "engine_re": "N_m3u8DL-RE (m3u8)",
                "label_threads": "Threads:",
                "label_save_path": "Save to:",
                "btn_change_path": "Change Path",
                "btn_start": "🚀 Start Download Task",
                "btn_stop": "🛑 Stop Download (Click to Kill)",

                # Logs & Messages
                "label_log": "Running Logs",
                "msg_input_url": "Please enter a URL",
                "msg_warning": "Warning",
                "msg_finish": "Done",
                "msg_fix_done": "Environment fixed!\nPlease restart the app.",
                "log_cookie_filter": ">>> Filtering cookies for target host: {host}...\n",
                "log_cookie_truncate": "⚠️ Cookie is too long and has been automatically truncated.",
                "log_cookie_none": "⚠️ No cookies found for {host}. Falling back to direct download.",
                "log_cookie_error": "⚠️ Failed to parse cookies",
                "log_re_not_found": "❌ Error: N_m3u8DL-RE not found in 'bin' folder!",
                "log_tip_re_path": "Tip: Ensure the tool is placed in the 'bin' folder next to the script.",
                "log_re_no_browser": "⚠️ RE engine does not support direct browser link. Please use 'Cookie Plugin' to export .txt.",
                "log_mode_browser": "Mode: {} Cookie",
                "log_mode_file": "Mode: Cookie File",
                "log_warning_guest": "Warning: No file selected, downloading in Guest Mode",
                "log_exec_cmd": "Execute Command",
                "log_save_to": "Saved to: {}",
                "log_tip_fix": "Tip: If it says 'command not found', click [Fix Dependencies] at the top.",
                "log_error_generic": "Error",
                "log_tip_install": "Tip: Please check if yt-dlp/ffmpeg is installed.",
                "log_start_re": ">>> Engine: N_m3u8DL-RE (Local)\n",
                "log_start_aria2": ">>> Engine: Aria2 Accel\n",
                "log_start_native": ">>> Engine: Native\n",
                "log_cookie_match": ">>> ✅ Successfully loaded {} Cookies\n",
                "log_load_cookie_ok": ">>> Last Cookie file loaded successfully\n",
                "log_download_success": "\n>>> 🎉 Download Success!\n",
                "log_download_stop": "\n>>> 🛑 Download Stopped.\n",
                "log_download_fail": "\n>>> ❌ Download Failed.\n",
                "log_open_dir_error": "Failed to open folder: {e}\n",
                "log_check_yt_ok": ">>> Env Check (System): yt-dlp is Ready ✅\n",
                "log_check_yt_fail": ">>> ❌ Env Check (System): yt-dlp not found. Click [Fix Dependencies].\n",
                "log_check_re_ok": ">>> Env Check (Local): N_m3u8DL-RE is Ready ✅\n",
                "log_check_re_warning": ">>> ⚠️ Env Check (Local): N_m3u8DL-RE not found in 'bin' (yt-dlp still works)\n",

                # Context Menu
                "menu_paste": "Paste",
                "menu_select_all": "Select All"
            }
        }

        # 加载配置
        self.config_file = os.path.join(os.path.expanduser("~"), ".univ_downloader_config.json")
        self.config_data = self.load_config()
        self.lang = self.config_data.get("lang", "en")  # 默认为英文

        display_name = "macOS" if self.system == "Darwin" else self.system
        self.root.title(f"{self.translations[self.lang]['title']} ({display_name})")

        # 窗口大小适配
        if self.system == "Darwin":
            self.root.geometry("740x820")
        else:
            self.root.geometry("740x780")

        self.setup_env_path()

        # === 核心路径配置 (混合管理模式) ===
        # 1. 获取app所在目录，定位 bin 文件夹
        self.base_dir = self.get_base_path()
        self.bin_dir = os.path.join(self.base_dir, "bin")  # bin 文件夹必须在 app 旁边

        # 2. 设定 RE 的本地路径 (由用户手动放入 bin)
        re_name = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
        self.re_path = os.path.join(self.bin_dir, re_name)

        # B. 通用工具：yt-dlp / ffmpeg -> 走系统命令 (不指定路径，依靠 PATH)
        self.yt_dlp_cmd = "yt-dlp"
        self.ffmpeg_cmd = "ffmpeg"

        # 如果是 Mac，自动给 bin 里的 RE 赋予权限
        if self.system == "Darwin" and os.path.exists(self.re_path):
            try:
                os.chmod(self.re_path, 0o755)
            except:
                pass

        # === 核心变量 ===
        self.current_process = None
        self.is_downloading = False

        self.config_file = os.path.join(os.path.expanduser("~"), ".univ_downloader_config.json")
        self.config_data = self.load_config()
        self.download_dir = self.config_data.get("download_dir", os.path.expanduser("~/Downloads"))
        self.cookie_file_path = self.config_data.get("cookie_path", "")

        # 样式定义
        self.setup_styles()

        # === UI 构建 ===
        self.build_ui()

        self.log_text.tag_config("info", foreground="#61afef")
        self.log_text.tag_config("success", foreground="#98c379")
        self.log_text.tag_config("error", foreground="#e06c75")
        self.log_text.tag_config("warning", foreground="#e5c07b")
        self.log_text.tag_config("tip", foreground="#E6a23c")

        self.restore_config_state()
        self.check_dependencies_silent()

    def setup_styles(self):
        if self.system == "Darwin":
            self.font_ui = ("PingFang SC", 12)
            self.font_bold = ("PingFang SC", 12, "bold")
            self.font_log = ("Menlo", 11)
            self.cmd_key = "Command"
        else:
            self.font_ui = ("Microsoft YaHei UI", 9)
            self.font_bold = ("Microsoft YaHei UI", 9, "bold")
            self.font_log = ("Consolas", 9)
            self.cmd_key = "Control"

        self.style = ttk.Style()
        self.style.configure("Big.TRadiobutton", font=self.font_ui)
        self.style.configure("TButton", font=self.font_ui)
        self.style.configure("Fix.TButton", foreground="#d9534f", font=self.font_ui)
        self.style.configure("Accent.TButton", font=self.font_bold, foreground="white", background="#007AFF")

    def build_ui(self):
        t = self.translations[self.lang]
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # === 0. 顶部栏：环境检测与工具 ===
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        self.open_dir_btn = ttk.Button(top_frame, text=t["btn_open_dir"], command=self.open_download_folder, width=12)
        self.open_dir_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.clear_btn = ttk.Button(top_frame, text=t["btn_clear_log"], command=self.clear_log, width=10)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))

        # 语言切换器
        ttk.Label(top_frame, text="🌐").pack(side=tk.LEFT, padx=(10, 2))
        self.lang_combo = ttk.Combobox(top_frame, values=["中文", "English"], width=8, state="readonly")
        self.lang_combo.set("中文" if self.lang == "zh" else "English")
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", self.change_language)

        self.install_btn = ttk.Button(top_frame, text=t["btn_fix_dep"], command=self.install_dependencies,
                                      style="Fix.TButton")
        self.install_btn.pack(side=tk.RIGHT)

        # === 1. 链接区 ===
        self.input_frame = ttk.LabelFrame(main_frame, text=t["frame_url"], padding="15 10")
        self.input_frame.pack(fill=tk.X, pady=(0, 15))
        self.url_entry = ttk.Entry(self.input_frame, font=("Arial", 11))
        self.url_entry.pack(fill=tk.X, ipady=4)
        self.setup_paste_fix(self.url_entry)

        # === 2. 权限与画质 ===
        self.cookie_frame = ttk.LabelFrame(main_frame, text=t["frame_tools"], padding="15 10")
        self.cookie_frame.pack(fill=tk.X, pady=(0, 15))
        self.cookie_source = tk.StringVar(value="none")

        # 第一排：Cookie 来源选择
        mode_frame = ttk.Frame(self.cookie_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.rb_guest = ttk.Radiobutton(mode_frame, text=t["mode_guest"], variable=self.cookie_source, value="none",
                                        style="Big.TRadiobutton")
        self.rb_guest.pack(side=tk.LEFT, padx=(0, 10))

        # 浏览器选项根据系统变化
        if self.system == "Darwin":
            ttk.Radiobutton(mode_frame, text="Safari", variable=self.cookie_source, value="safari",
                            style="Big.TRadiobutton").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(mode_frame, text="Chrome", variable=self.cookie_source, value="chrome",
                            style="Big.TRadiobutton").pack(side=tk.LEFT, padx=(0, 10))
        elif self.system == "Windows":
            ttk.Radiobutton(mode_frame, text="Edge", variable=self.cookie_source, value="edge",
                            style="Big.TRadiobutton").pack(side=tk.LEFT, padx=(0, 10))
            ttk.Radiobutton(mode_frame, text="Chrome", variable=self.cookie_source, value="chrome",
                            style="Big.TRadiobutton").pack(side=tk.LEFT, padx=(0, 10))

        # 手动文件
        self.lbl_local = ttk.Label(mode_frame, text=t["mode_local_file"], font=self.font_ui)
        self.lbl_local.pack(side=tk.LEFT, padx=(10, 0))
        self.btn_sel_cookie = ttk.Button(mode_frame, text=t["btn_select"], width=8, command=self.select_cookie_file)
        self.btn_sel_cookie.pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(mode_frame, text=t["status_no_file"], foreground="#888", width=15)
        self.file_label.pack(side=tk.LEFT)

        # 第二排：辅助插件链接
        helper_frame = ttk.Frame(self.cookie_frame)
        helper_frame.pack(fill=tk.X, pady=(5, 0))

        self.lbl_plugin = ttk.Label(helper_frame, text=t["label_get_plugin"], foreground="#666", font=self.font_ui)
        self.lbl_plugin.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_plugin = ttk.Button(helper_frame, text=t["btn_cookie_plugin"], width=12,
                                     command=lambda: self.open_plugin_url("chrome"))
        self.btn_plugin.pack(side=tk.LEFT, padx=2)

        ttk.Label(helper_frame, text="|", foreground="#ddd").pack(side=tk.LEFT, padx=8)
        ttk.Label(helper_frame, text="m3u8:", foreground="#666", font=self.font_ui).pack(side=tk.LEFT, padx=(0, 5))

        self.btn_catcatch = ttk.Button(helper_frame, text=t["btn_catcatch"], width=12,
                   command=lambda: self.open_plugin_url("catcatch"))
        self.btn_catcatch.pack(side=tk.LEFT, padx=2)

        # === 3. 下载控制区 ===
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 15))

        # 左侧：引擎选择
        opt_frame = ttk.Frame(ctrl_frame)
        opt_frame.pack(side=tk.LEFT)
        self.lbl_engine = ttk.Label(opt_frame, text=t["label_engine"], font=self.font_bold)
        self.lbl_engine.pack(anchor="w", pady=(0, 5))

        self.engine_var = tk.StringVar(value="native")
        radios_frame = ttk.Frame(opt_frame)
        radios_frame.pack(anchor="w")
        self.rb_native = ttk.Radiobutton(radios_frame, text=t["engine_native"], variable=self.engine_var,
                                         value="native", command=self.update_engine_ui)
        self.rb_native.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_aria2 = ttk.Radiobutton(radios_frame, text=t["engine_aria2"], variable=self.engine_var, value="aria2",
                                        command=self.update_engine_ui)
        self.rb_aria2.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_re = ttk.Radiobutton(radios_frame, text=t["engine_re"], variable=self.engine_var, value="re",
                                     command=self.update_engine_ui)
        self.rb_re.pack(side=tk.LEFT)

        # 线程选择
        self.thread_frame = ttk.Frame(opt_frame)
        self.thread_frame.pack(anchor="w", pady=(5, 0))
        self.lbl_thread = ttk.Label(self.thread_frame, text=t["label_threads"], font=self.font_ui, foreground="#666")
        self.lbl_thread.pack(side=tk.LEFT)
        self.thread_var = tk.StringVar(value="8")
        self.thread_combo = ttk.Combobox(self.thread_frame, textvariable=self.thread_var, width=5, state="disabled")
        self.thread_combo['values'] = ("4", "8", "16", "32")
        self.thread_combo.pack(side=tk.LEFT, padx=5)

        # 右侧：路径选择
        path_frame = ttk.Frame(ctrl_frame)
        path_frame.pack(side=tk.RIGHT, anchor="n")

        path_label_frame = ttk.Frame(path_frame)
        path_label_frame.pack(anchor="e")
        self.lbl_save = ttk.Label(path_label_frame, text=t["label_save_path"], foreground="#666", font=self.font_ui)
        self.lbl_save.pack(side=tk.LEFT)
        self.path_label = ttk.Label(path_label_frame, text=self.download_dir[-30:], foreground="#007AFF",
                                    font=self.font_ui)  # 只显示后30位防止过长
        self.path_label.pack(side=tk.LEFT, padx=5)
        self.btn_change_path = ttk.Button(path_frame, text=t["btn_change_path"], command=self.change_download_path,
                                          width=10)
        self.btn_change_path.pack(anchor="e", pady=5)

        self.download_btn = ttk.Button(main_frame, text=t["btn_start"], command=self.toggle_download_state, width=35)
        self.download_btn.pack(pady=10)

        # === 4. 日志区 ===
        self.log_header = ttk.Label(main_frame, text=t["label_log"], font=self.font_bold)
        self.log_header.pack(anchor="w", pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(main_frame, bg="#2b2b2b", fg="#cccccc", font=self.font_log, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def change_language(self, event=None):
        new_lang = "zh" if self.lang_combo.get() == "中文" else "en"
        if new_lang == self.lang: return

        self.lang = new_lang
        self.update_config("lang", self.lang)
        t = self.translations[self.lang]

        # 刷新所有UI文本
        display_name = "macOS" if self.system == "Darwin" else self.system
        self.root.title(f"{t['title']} ({display_name})")
        self.open_dir_btn.config(text=t["btn_open_dir"])
        self.clear_btn.config(text=t["btn_clear_log"])
        self.install_btn.config(text=t["btn_fix_dep"])
        self.input_frame.config(text=t["frame_url"])
        self.cookie_frame.config(text=t["frame_tools"])
        self.rb_guest.config(text=t["mode_guest"])
        self.lbl_local.config(text=t["mode_local_file"])
        self.btn_sel_cookie.config(text=t["btn_select"])
        if not self.cookie_file_path: self.file_label.config(text=t["status_no_file"])
        self.lbl_plugin.config(text=t["label_get_plugin"])
        self.btn_plugin.config(text=t["btn_cookie_plugin"])
        self.btn_catcatch.config(text=t["btn_catcatch"])
        self.lbl_engine.config(text=t["label_engine"])
        self.rb_native.config(text=t["engine_native"])
        self.rb_aria2.config(text=t["engine_aria2"])
        self.rb_re.config(text=t["engine_re"])
        self.lbl_thread.config(text=t["label_threads"])
        self.lbl_save.config(text=t["label_save_path"])
        self.btn_change_path.config(text=t["btn_change_path"])
        self.log_header.config(text=t["label_log"])

        btn_text = t["btn_stop"] if self.is_downloading else t["btn_start"]
        self.download_btn.config(text=btn_text)

        self.log(f"\n>>> Language changed to {'Chinese' if self.lang == 'zh' else 'English'}\n", "info")

    # ================= 核心逻辑 =================

    def parse_cookie_file(self, filepath, target_url):
        t = self.translations[self.lang]

        if not os.path.exists(filepath): return ""
        try:
            parsed = urlparse(target_url)
            host = parsed.netloc.split(':')[0]
            if not host: return ""
        except:
            return ""

        self.log(t['log_cookie_filter'].format(host=host), "info")
        cookie_parts = []
        count = 0
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    fields = line.split('\t')
                    if len(fields) >= 7:
                        domain_field = fields[0]
                        if domain_field in host or host in domain_field:
                            name = fields[5]
                            value = fields[6]
                            cookie_parts.append(f"{name}={value}")
                            count += 1
            final_cookie = "; ".join(cookie_parts)
            if len(final_cookie) > 6000:
                self.log(f">>> {t['log_cookie_truncate']}\n", "warning")
                final_cookie = final_cookie[:6000]
            elif len(final_cookie) == 0:
                self.log(f">>> {t['log_cookie_none'].format(host=host)}\n", "warning")
            else:
                self.log(t["log_cookie_match"].format(count=count), "success")
            return final_cookie
        except Exception as e:
            self.log(f">>> {t['log_cookie_error']}: {e}\n", "warning")
            return ""

    def run_download(self, url):
        t = self.translations[self.lang]

        engine = self.engine_var.get()
        thread_num = self.thread_var.get().split()[0]
        cmd = []
        source = self.cookie_source.get()

        # === 引擎: N_m3u8DL-RE (强制使用本地 bin) ===
        if engine == "re":
            # 检查本地工具是否存在
            if not os.path.exists(self.re_path):
                self.log(f">>> {t['log_re_not_found']}\n", "error")
                self.log(f">>> {t['log_tip_re_path']}\n", "tip")
                self.is_downloading = False
                self.root.after(0, lambda: self.download_btn.config(text=t["btn_start"], state=tk.NORMAL))
                return

            cmd = [
                self.re_path, url,  # 调用本地 bin 里的 RE
                "--save-dir", self.download_dir,
                "--thread-count", thread_num,
                "--auto-select",
                "--no-log"
            ]
            self.log(t["log_start_re"], "info")

            if source == "file" and self.cookie_file_path:
                cookie_str = self.parse_cookie_file(self.cookie_file_path, url)
                if cookie_str:
                    cmd.append("--header")
                    cmd.append(f"Cookie: {cookie_str}")
            elif source in ["chrome", "edge", "safari"]:
                self.log(f">>> {t['log_re_no_browser']}\n", "warning")

        # === 引擎: yt-dlp (Native / Aria2) ===
        else:
            cmd = [
                "yt-dlp",  # 调用系统安装的 yt-dlp
                "-P", self.download_dir,
                "--merge-output-format", "mp4",
                "--retries", "10",
                "-f", "bv+ba/b",
                url
            ]

            if engine == "aria2":
                cmd.insert(1, "--downloader")
                cmd.insert(2, "aria2c")
                cmd.insert(3, "--downloader-args")
                cmd.insert(4, f"aria2c:-x {thread_num} -k 1M")
                self.log(t["log_start_aria2"], "info")
            else:
                self.log(t["log_start_native"], "info")

            # Cookie 处理
            if source in ["chrome", "edge", "safari", "firefox"]:
                cmd.insert(1, "--cookies-from-browser")
                cmd.insert(2, source)
                mode_msg = t["log_mode_browser"].format(source.capitalize())
                self.log(f">>> {mode_msg}\n", "info")
            elif source == "file":
                if self.cookie_file_path:
                    cmd.insert(1, "--cookies")
                    cmd.insert(2, self.cookie_file_path)
                    self.log(f">>> {t['log_mode_file']}\n", "info")
                else:
                    self.log(f">>> {t['log_warning_guest']}\n", "warning")

        # 执行
        exec_msg = t["log_exec_cmd"] if "log_exec_cmd" in t else "Execute Command"
        self.log(f"{exec_msg}: {' '.join(cmd)}\n{'-' * 40}\n")

        try:
            # Windows 隐藏窗口配置
            startupinfo = None
            if self.system == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=False,
                startupinfo=startupinfo
            )

            error_detected = False

            for line in self.current_process.stdout:
                self.log(line)
                # 简单诊断
                if "403" in line or "Command not found" in line or "No video" in line:
                    error_detected = True

            self.current_process.wait()
            rc = self.current_process.returncode

            if rc == 0:
                self.play_sound(success=True)
                self.log(t["log_download_success"], "success")
                self.log(f">>> {t['log_save_to'].format(self.download_dir)}\n", "success")
            elif rc in [-9, -15, 1] and not self.is_downloading:
                self.log(t["log_download_stop"], "warning")
            else:
                self.play_sound(success=False)
                self.log(t["log_download_fail"], "error")
                if error_detected:
                    self.log(f">>> {t['log_tip_fix']}\n", "tip")

        except Exception as e:
            self.log(f"\n{t['log_error_generic']}: {e}\n", "error")
            self.log(f">>> {t['log_tip_install']}\n", "tip")

        finally:
            self.is_downloading = False
            self.current_process = None
            self.root.after(0, lambda: self.download_btn.config(text=t["btn_start"], state=tk.NORMAL))

    # ================= 辅助功能 =================

    def toggle_download_state(self):
        t = self.translations[self.lang]
        if not self.is_downloading:
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showwarning("!", t["msg_input_url"])
                return
            self.is_downloading = True
            self.download_btn.config(text=t["btn_stop"])
            self.log_text.delete(1.0, tk.END)

            thread = threading.Thread(target=self.run_download, args=(url,))
            thread.daemon = True
            thread.start()
        else:
            self.stop_download()
            self.download_btn.config(text=t["btn_start"])

    def stop_download(self):
        t = self.translations[self.lang]
        if self.current_process:
            try:
                self.log(f"\n{t['log_download_stop']}\n", "warning")
                if self.system == "Windows":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.current_process.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    self.current_process.terminate()  # Unix/Mac 较温和的方式
                self.is_downloading = False
            except Exception as e:
                err_msg = "终止失败" if self.lang == "zh" else "Terminate Failed"
                self.log(f"{err_msg}: {e}\n", "error")

    def install_dependencies(self):
        """一键修复入口：开启线程进行系统依赖和本地RE引擎的安装"""
        t = self.translations[self.lang]
        # 动态提示正在修复
        fixing_text = "正在修复..." if self.lang == "zh" else "Fixing..."
        self.install_btn.config(state=tk.DISABLED, text=fixing_text)
        threading.Thread(target=self._run_install_process, daemon=True).start()

    def _run_install_process(self):
        """实际执行安装的线程函数"""
        t = self.translations[self.lang]
        try:
            # 1. 第一步：修复系统依赖 (yt-dlp, ffmpeg)
            self.log(f"\n{t['env_check_sys']}...\n", "info")
            self._install_system_deps()

            # 2. 第二步：修复本地 RE 引擎
            self.log(f"\n{t['env_check_local']}...\n", "info")
            self._install_local_re()

            self.log(f"\n{t['log_download_success']}\n", "success")
            messagebox.showinfo(t["msg_finish"], t["msg_fix_done"])

        except Exception as e:
            error_label = "错误" if self.lang == "zh" else "Error"
            self.log(f"\n>>> ❌ {error_label}: {str(e)}\n", "error")
            self.root.after(0, lambda msg=str(e): messagebox.showerror(error_label, f"Failed: {msg}"))

        finally:
            # 恢复按钮状态
            def reset_ui():
                self.install_btn.config(state=tk.NORMAL, text=t["btn_fix_dep"])
                self.check_dependencies_silent()  # 刷新日志区显示状态

            self.root.after(0, reset_ui)

    def check_dependencies_silent(self):
        """检测：系统级 yt-dlp + 本地 bin 级 RE"""
        t = self.translations[self.lang]

        try:
            # 1. 检查系统 PATH 里的 yt-dlp
            startupinfo = None
            if self.system == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(["yt-dlp", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                           startupinfo=startupinfo)
            self.log(t["log_check_yt_ok"], "success")
        except:
            self.log(t["log_check_yt_fail"], "error")

        # 2. 检查 bin 目录里的 RE
        if os.path.exists(self.re_path):
            self.log(t["log_check_re_ok"], "success")
        else:
            self.log(t["log_check_re_warning"], "warning")

    def is_cmd_available(self, cmd):
        """辅助方法：检查命令是否存在"""
        try:
            subprocess.run([cmd, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            return False

    # === 配置与文件 ===

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def update_config(self, key, value):
        self.config_data[key] = value
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config_data, f)
        except:
            pass

    def restore_config_state(self):
        t = self.translations[self.lang]
        if self.cookie_file_path and os.path.exists(self.cookie_file_path):
            self.cookie_source.set("file")
            self.file_label.config(text=os.path.basename(self.cookie_file_path), foreground="#007AFF")
            self.log(t["log_load_cookie_ok"], "success")

    def select_cookie_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if f:
            self.cookie_file_path = f
            self.file_label.config(text=os.path.basename(f), foreground="#007AFF")
            self.cookie_source.set("file")
            self.update_config("cookie_path", f)

    def change_download_path(self):
        d = filedialog.askdirectory(initialdir=self.download_dir)
        if d:
            self.download_dir = d
            self.path_label.config(text=d[-30:])
            self.update_config("download_dir", d)

    def update_engine_ui(self):
        if self.engine_var.get() == "native":
            self.thread_combo.config(state="disabled")
        else:
            self.thread_combo.config(state="readonly")

    def open_plugin_url(self, type_):
        urls = {
            "chrome": "https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
            "catcatch": "https://chromewebstore.google.com/detail/cat-catch/jfedfbgedapdagkghmgibemcoggfppbb"
        }
        if type_ in urls: webbrowser.open(urls[type_])

    def setup_env_path(self):
        if self.system == "Darwin":
            os.environ["PATH"] += os.pathsep + "/opt/homebrew/bin"
            os.environ["PATH"] += os.pathsep + "/usr/local/bin"  # Intel Mac

    def open_download_folder(self):
        t = self.translations[self.lang]
        try:
            if self.system == "Windows":
                os.startfile(self.download_dir)
            elif self.system == "Darwin":
                subprocess.run(["open", self.download_dir])
            else:
                subprocess.run(["xdg-open", self.download_dir])
        except Exception as e:
            self.log(t["log_open_dir_error"].format(e=e), "error")

    def clear_log(self):
        self.log_text.delete(1.0, tk.END)

    def log(self, text, tag=None):
        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)

    def play_sound(self, success=True):
        if self.system == "Darwin":
            sound = "Glass" if success else "Basso"
            os.system(f'afplay /System/Library/Sounds/{sound}.aiff')
        elif self.system == "Windows":
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK if success else winsound.MB_ICONHAND)
            except:
                pass

    # === 粘贴键修复 (Mac/Windows) ===

    def setup_paste_fix(self, widget):
        t = self.translations[self.lang]

        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label=t["menu_paste"], command=lambda: self.do_paste(widget))
        menu.add_command(label=t["menu_select_all"], command=lambda: self.select_all(widget))
        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        mod = self.cmd_key
        widget.bind(f"<{mod}-v>", lambda e: self.do_paste(widget))
        widget.bind(f"<{mod}-a>", lambda e: self.select_all(widget))

    def do_paste(self, widget):
        try:
            widget.insert(tk.INSERT, widget.clipboard_get())
        except:
            pass
        return "break"

    def select_all(self, widget):
        widget.select_range(0, tk.END)
        widget.icursor(tk.END)
        return "break"


if __name__ == "__main__":
    root = tk.Tk()
    app = UniversalDownloader(root)
    root.mainloop()