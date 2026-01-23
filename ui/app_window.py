import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import webbrowser
import platform
import os

# === 配置与工具导入 ===
from config.config import (
    TRANSLATIONS,
    SYSTEM,
    BIN_DIR,
    load_user_config,
    save_user_config
)
from utils import setup_env_path, open_download_folder
from .widgets import setup_styles, setup_paste_fix

# === 核心逻辑导入 (适配新版接口) ===
# 注意：downloader，installer 是类
from core.downloader import DownloaderEngine
from core.installer import DependencyInstaller


class MainWindow:
    def __init__(self, root):
        self.root = root
        self.system = SYSTEM

        # 1. 加载配置
        self.config_data = load_user_config()
        self.lang = self.config_data.get("lang", "zh")
        self.download_dir = self.config_data.get("download_dir", os.path.expanduser("~/Downloads"))
        self.cookie_file_path = self.config_data.get("cookie_path", "")

        # 2. 初始化环境
        setup_env_path()
        self.font_ui, self.font_bold, self.font_log = setup_styles(self.system)
        self.cmd_key = "Command" if self.system == "Darwin" else "Control"

        # 3. 核心对象初始化
        # 下载控制器：下载开始时会被赋值，下载结束或停止时置空
        self.download_controller = None

        # 初始化 DownloaderEngine 实例（传入线程安全的日志回调）
        # 这样我们后面可以通过 self.downloader.run_threaded(...) 启动任务
        self.downloader = DownloaderEngine(self.log_thread_safe)

        # 安装器：初始化时传入日志回调
        # 注意：这里假设 Installer 内部会自动判断 CN 模式，或者你需要根据配置传入
        # 如果你的 installer.__init__ 需要 is_cn_mode，请在这里修改，例如: is_cn_mode=True
        self.installer = DependencyInstaller(self.log_thread_safe)

        # 4. 构建界面
        self.setup_window()
        self.build_ui()
        self.setup_tags()

        # 5. 启动后操作
        self.restore_config_state()
        self.check_deps_on_start()

    # --- 基础辅助 ---

    def get_current_trans(self):
        return TRANSLATIONS.get(self.lang, TRANSLATIONS["en"])

    def update_config(self, key, value):
        self.config_data[key] = value
        save_user_config(self.config_data)

    def log(self, text, tag=None):
        """主线程日志写入"""
        self.log_text.insert(tk.END, text, tag)
        self.log_text.see(tk.END)

    def log_thread_safe(self, text, tag=None):
        """跨线程日志调用 (传给 Core 使用)"""
        self.root.after(0, lambda: self.log(text, tag))

    # --- 界面构建 ---

    def setup_window(self):
        t = self.get_current_trans()
        display_name = "macOS" if self.system == "Darwin" else self.system
        self.root.title(f"{t['title']} ({display_name})")
        if self.system == "Darwin":
            self.root.geometry("740x820")
        else:
            self.root.geometry("740x780")

    def build_ui(self):
        t = self.get_current_trans()
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top Bar
        top = ttk.Frame(main_frame)
        top.pack(fill=tk.X, pady=(0, 15))

        self.btn_open = ttk.Button(top, text=t["btn_open_dir"], command=lambda: open_download_folder(self.download_dir),
                                   width=12)
        self.btn_open.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_clear = ttk.Button(top, text=t["btn_clear_log"], command=lambda: self.log_text.delete(1.0, tk.END),
                                    width=10)
        self.btn_clear.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(top, text="🌐").pack(side=tk.LEFT, padx=(10, 2))
        self.lang_combo = ttk.Combobox(top, values=["中文", "English"], width=8, state="readonly")
        self.lang_combo.set("中文" if self.lang == "zh" else "English")
        self.lang_combo.pack(side=tk.LEFT)
        self.lang_combo.bind("<<ComboboxSelected>>", self.change_language)

        self.install_btn = ttk.Button(top, text=t["btn_fix_dep"], command=self.run_install, style="Fix.TButton")
        self.install_btn.pack(side=tk.RIGHT)

        # Input
        self.input_frame = ttk.LabelFrame(main_frame, text=t["frame_url"], padding="15 10")
        self.input_frame.pack(fill=tk.X, pady=(0, 15))
        self.url_entry = ttk.Entry(self.input_frame, font=("Arial", 11))
        self.url_entry.pack(fill=tk.X, ipady=4)
        setup_paste_fix(self.url_entry, self.cmd_key, t)

        # Tools
        self.cookie_frame = ttk.LabelFrame(main_frame, text=t["frame_tools"], padding="15 10")
        self.cookie_frame.pack(fill=tk.X, pady=(0, 15))
        self.cookie_source = tk.StringVar(value="none")

        mode_frame = ttk.Frame(self.cookie_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.rb_guest = ttk.Radiobutton(mode_frame, text=t["mode_guest"], variable=self.cookie_source, value="none",
                                        style="Big.TRadiobutton")
        self.rb_guest.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_local = ttk.Label(mode_frame, text=t["mode_local_file"], font=self.font_ui)
        self.lbl_local.pack(side=tk.LEFT, padx=(10, 0))
        self.btn_sel_cookie = ttk.Button(mode_frame, text=t["btn_select"], width=8, command=self.select_cookie_file)
        self.btn_sel_cookie.pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(mode_frame, text=t["status_no_file"], foreground="#888", width=15)
        self.file_label.pack(side=tk.LEFT)

        helper_frame = ttk.Frame(self.cookie_frame)
        helper_frame.pack(fill=tk.X, pady=(5, 0))
        self.lbl_plugin = ttk.Label(helper_frame, text=t["label_get_plugin"], foreground="#666", font=self.font_ui)
        self.lbl_plugin.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_plugin = ttk.Button(helper_frame, text=t["btn_cookie_plugin"], width=12,
                                     command=lambda: webbrowser.open("https://github.com/Wait4MyDriver"))
        self.btn_plugin.pack(side=tk.LEFT, padx=2)

        # Controls
        ctrl_frame = ttk.Frame(main_frame)
        ctrl_frame.pack(fill=tk.X, pady=(0, 15))

        opt_frame = ttk.Frame(ctrl_frame)
        opt_frame.pack(side=tk.LEFT)
        self.lbl_engine = ttk.Label(opt_frame, text=t["label_engine"], font=self.font_bold)
        self.lbl_engine.pack(anchor="w", pady=(0, 5))

        self.engine_var = tk.StringVar(value="native")
        rf = ttk.Frame(opt_frame)
        rf.pack(anchor="w")
        self.rb_native = ttk.Radiobutton(rf, text=t["engine_native"], variable=self.engine_var, value="native",
                                         command=self.toggle_engine_ui)
        self.rb_native.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_aria = ttk.Radiobutton(rf, text=t["engine_aria2"], variable=self.engine_var, value="aria2",
                                       command=self.toggle_engine_ui)
        self.rb_aria.pack(side=tk.LEFT, padx=(0, 8))
        self.rb_re = ttk.Radiobutton(rf, text=t["engine_re"], variable=self.engine_var, value="re",
                                     command=self.toggle_engine_ui)
        self.rb_re.pack(side=tk.LEFT)

        tf = ttk.Frame(opt_frame)
        tf.pack(anchor="w", pady=(5, 0))
        self.lbl_thread = ttk.Label(tf, text=t.get("label_threads", "Threads:"), font=self.font_ui, foreground="#666")
        self.lbl_thread.pack(side=tk.LEFT)
        self.thread_var = tk.StringVar(value="8")
        self.thread_combo = ttk.Combobox(tf, textvariable=self.thread_var, width=5, state="disabled",
                                         values=("4", "8", "16", "32"))
        self.thread_combo.pack(side=tk.LEFT, padx=5)

        pf = ttk.Frame(ctrl_frame)
        pf.pack(side=tk.RIGHT, anchor="n")
        plf = ttk.Frame(pf)
        plf.pack(anchor="e")
        self.lbl_save = ttk.Label(plf, text=t["label_save_path"], foreground="#666", font=self.font_ui)
        self.lbl_save.pack(side=tk.LEFT)
        self.path_label = ttk.Label(plf, text=self.download_dir[-30:], foreground="#007AFF", font=self.font_ui)
        self.path_label.pack(side=tk.LEFT, padx=5)
        self.btn_path = ttk.Button(pf, text=t["btn_change_path"], command=self.change_download_path, width=10)
        self.btn_path.pack(anchor="e", pady=5)

        self.download_btn = ttk.Button(main_frame, text=t["btn_start"], command=self.toggle_download, width=35)
        self.download_btn.pack(pady=10)

        # Log
        self.lbl_log = ttk.Label(main_frame, text=t["label_log"], font=self.font_bold)
        self.lbl_log.pack(anchor="w", pady=(0, 5))
        self.log_text = scrolledtext.ScrolledText(main_frame, bg="#2b2b2b", fg="#cccccc", font=self.font_log, height=12)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def setup_tags(self):
        self.log_text.tag_config("info", foreground="#61afef")
        self.log_text.tag_config("success", foreground="#98c379")
        self.log_text.tag_config("error", foreground="#e06c75")
        self.log_text.tag_config("warning", foreground="#e5c07b")
        self.log_text.tag_config("tip", foreground="#E6a23c")

    # --- 逻辑交互 ---

    def toggle_download(self):
        t = self.get_current_trans()

        # 1. 如果正在下载 -> 执行停止逻辑
        if self.download_controller:
            self.log(f"\n>>> {t.get('log_download_stop', 'Stopping...')}\n", "warning")
            try:
                self.download_controller.stop()
            except Exception:
                pass
            # 按钮状态会在 on_download_done 回调中恢复
            return

        # 2. 如果未下载 -> 开始新任务
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Tip", t.get("msg_input_url", "URL cannot be empty"))
            return

        # 清日志并把按钮切为 Stop
        self.log_text.delete(1.0, tk.END)
        self.download_btn.config(text=t["btn_stop"], state=tk.NORMAL)

        # 收集 options，保持和 core/downloader.py 里 run_threaded 的参数一致
        options = {
            "engine": self.engine_var.get(),
            "download_dir": self.download_dir,
            "threads": int(self.thread_var.get()) if self.thread_var.get().isdigit() else 4,
            "cookie_source": self.cookie_source.get(),
            "cookie_path": self.cookie_file_path,
        }

        # 启动下载：使用实例方法 run_threaded 返回一个 controller
        try:
            self.download_controller = self.downloader.run_threaded(url, options)
        except Exception as e:
            self.log_thread_safe(f"❌ 无法启动下载: {e}\n", "error")
            # 恢复按钮
            self.download_btn.config(text=t["btn_start"])
            self.download_controller = None
            return

        # 可选：在 UI 上禁用一些控件以防止重复操作
        self.install_btn.config(state=tk.DISABLED)
        self.btn_path.config(state=tk.DISABLED)
        self.btn_sel_cookie.config(state=tk.DISABLED)

    def on_download_done(self, success, rc=None):
        """下载结束回调 (由 Core 线程调用，需要切回 UI 线程)"""
        # 直接安排 UI 线程执行最终处理
        self.root.after(0, lambda: self._handle_download_done(success, rc))

    def _handle_download_done(self, success, rc=None):
        """UI 线程处理下载结束"""
        t = self.get_current_trans()
        # 播放完成提示
        try:
            self.play_sound(success)
        except Exception:
            pass
        # 清理 controller 并恢复按钮及控件
        self.download_controller = None
        self.download_btn.config(text=t["btn_start"])
        self.install_btn.config(state=tk.NORMAL)
        self.btn_path.config(state=tk.NORMAL)
        self.btn_sel_cookie.config(state=tk.NORMAL)

        # 可选：弹窗提示（如果你希望）
        if success:
            self.log("\n>>> 下载成功。\n", "success")
        else:
            self.log("\n>>> 下载失败，请查看日志以获得更多信息。\n", "error")

    def run_install(self):
        """运行依赖修复（线程化）"""
        t = self.get_current_trans()
        self.install_btn.config(state=tk.DISABLED, text=t.get("btn_fix_dep_running", "Fixing..."))

        try:
            # 如果 installer 提供了非阻塞接口
            controller = self.installer.install_all_threaded()
        except AttributeError:
            # 向后兼容：如果没有线程化接口，则用线程包装同步函数
            def _task_sync():
                try:
                    self.installer.install_all()
                except Exception as e:
                    self.log_thread_safe(f"Error during install: {e}\n", "error")
                finally:
                    self.root.after(0, lambda: messagebox.showinfo("Done", t.get("msg_fix_done", "Check finished.")))
                    self.root.after(0, lambda: self.install_btn.config(state=tk.NORMAL, text=t["btn_fix_dep"]))

            threading.Thread(target=_task_sync, daemon=True).start()
            return

        # 如果得到了 controller，就在后台等待其完成以恢复 UI（轻量方法）
        def _watch():
            # 简单地轮询 controller 状态
            while controller.is_alive():
                self.root.after(200, lambda: None)  # 保持 UI 响应
                controller._thread.join(0.2)  # 非阻塞 join
            # 安装结束，恢复按钮
            self.root.after(0, lambda: messagebox.showinfo("Done", t.get("msg_fix_done", "Check finished.")))
            self.root.after(0, lambda: self.install_btn.config(state=tk.NORMAL, text=t["btn_fix_dep"]))

        threading.Thread(target=_watch, daemon=True).start()

    def check_deps_on_start(self):
        """启动时静默检测"""

        def _check():
            try:
                status = self.installer.check_status()
                # 根据状态更新 UI（例如在 log 显示或颜色）
                if not status.get("yt-dlp"):
                    self.log_thread_safe("⚠️ 未检测到 yt-dlp，某些功能可能不可用。\n", "warning")
                if not status.get("ffmpeg"):
                    self.log_thread_safe("⚠️ 未检测到 ffmpeg，视频合并可能失败。\n", "warning")
                # 你可以在这里把状态展示成图标、按钮颜色等
            except Exception as e:
                # 不让启动日志抛出
                pass

        threading.Thread(target=_check, daemon=True).start()

    # --- 其他辅助 ---

    def change_language(self, event=None):
        new_lang = "zh" if self.lang_combo.get() == "中文" else "en"
        if new_lang == self.lang: return
        self.lang = new_lang
        self.update_config("lang", self.lang)
        self.refresh_text()

    def refresh_text(self):
        t = self.get_current_trans()
        self.root.title(f"{t['title']} ({self.system})")
        self.btn_open.config(text=t["btn_open_dir"])
        self.install_btn.config(text=t["btn_fix_dep"])
        self.lbl_engine.config(text=t["label_engine"])
        if self.download_controller:
            self.download_btn.config(text=t["btn_stop"])
        else:
            self.download_btn.config(text=t["btn_start"])
        self.log(f"\n>>> Language switched to {self.lang}\n", "info")

    def toggle_engine_ui(self):
        if self.engine_var.get() == "native":
            self.thread_combo.config(state="disabled")
        else:
            self.thread_combo.config(state="readonly")

    def select_cookie_file(self):
        f = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if f:
            self.cookie_file_path = f
            self.file_label.config(text=os.path.basename(f), foreground="#007AFF")
            self.cookie_source.set("file")
            self.update_config("cookie_path", f)

    def change_download_path(self):
        d = filedialog.askdirectory()
        if d:
            self.download_dir = d
            self.path_label.config(text=d[-30:])
            self.update_config("download_dir", d)

    def restore_config_state(self):
        t = self.get_current_trans()
        if self.cookie_file_path and os.path.exists(self.cookie_file_path):
            self.cookie_source.set("file")
            self.file_label.config(text=os.path.basename(self.cookie_file_path), foreground="#007AFF")
            self.log(t["log_load_cookie_ok"], "success")

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