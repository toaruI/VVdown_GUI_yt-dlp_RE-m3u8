# 在 ui/main_window.py 中
from config.cookie_utils import parse_cookie_file
from core.downloader import run_download_threaded

# 使用：
cookie_str = parse_cookie_file(self.cookie_file_path, url)

def start_download(self, url):
    def log_cb(msg, level=None):
        self.log(msg, level)
    def on_done(success, rc):
        # 在主线程更新 UI
        self.root.after(0, lambda: self.on_download_done(success, rc))

    th = run_download_threaded(
        url=url,
        download_dir=self.download_dir,
        engine=self.engine_var.get(),
        thread_num=int(self.thread_var.get()),
        cookie_source=self.cookie_source.get(),
        cookie_file_path=self.cookie_file_path,
        re_path=self.re_path,
        log_cb=log_cb,
        on_done=on_done,
        env=None,
        cwd=None
    )
    self.current_thread = th
