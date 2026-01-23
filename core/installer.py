def _install_system_deps(self):
    """调用系统包管理器安装 yt-dlp 和 ffmpeg"""
    is_win = (self.system == "Windows")
    is_mac = (self.system == "Darwin")

    if self.system == "Darwin":
        # Mac 检测是否已安装
        if self.is_cmd_available("yt-dlp") and self.is_cmd_available("ffmpeg"):
            msg = "系统依赖已存在，跳过。\n" if self.lang == "zh" else "System deps already exist, skipping.\n"
            self.log(f">>> {msg}", "success")
            return

        # 2. 构建纯净的 Shell 命令列表
        shell_cmds = [
            'echo "=== 正在检查并安装环境 ==="',
            'if ! command -v brew &> /dev/null; then /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; (echo; echo \'eval "$(/opt/homebrew/bin/brew shellenv)"\') >> ~/.zprofile; eval "$(/opt/homebrew/bin/brew shellenv)"; fi',
            'brew install yt-dlp ffmpeg aria2',
            'echo "=== 安装完成，请关闭此窗口 ==="'
        ] if self.lang == "zh" else [
            'echo "=== Checking and installing required environment ==="',
            'if ! command -v brew &> /dev/null; then /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"; (echo; echo \'eval "$(/opt/homebrew/bin/brew shellenv)"\') >> ~/.zprofile; eval "$(/opt/homebrew/bin/brew shellenv)"; fi',
            'brew install yt-dlp ffmpeg aria2',
            'echo "=== Installation completed. You may now close this window. ==="'
        ]

        # 用分号连接命令
        full_shell_script = " ; ".join(shell_cmds)

        # 使用 AppleScript 调起终端执行，这次使用单引号包裹，避开语法冲突
        applescript = f'tell application "Terminal" to do script "{full_shell_script}"'

        try:
            self.log(
                ">>> 正在通过 AppleScript 调起终端窗口...\n" if self.lang == "zh" else ">>> Launching Terminal via AppleScript...\n",
                "warning")
            subprocess.run(["osascript", "-e", applescript, "-e", 'tell application "Terminal" to activate'])
            self.log(
                ">>> 提示: 请在弹出的终端窗口中完成安装步骤。\n" if self.lang == "zh" else ">>> Please complete the installation steps in the Terminal window that just opened.\n",
                "tip")
        except Exception as e:
            self.log(f">>> 调起终端失败: {e}\n" if self.lang == "zh" else f">>> Failed to launch Terminal: {e}\n",
                     "error")

    elif self.system == "Windows":
        # Windows 检测
        if self.is_cmd_available("yt-dlp") and self.is_cmd_available("ffmpeg"):
            msg = "系统依赖已存在，跳过。\n" if self.lang == "zh" else "System deps already exist, skipping.\n"
            self.log(f">>> {msg}", "success")
            return

        self.log(
            ">>> 正在调起 Winget 安装组件...\n" if self.lang == "zh" else ">>> Launching Winget to install required components...\n",
            "warning")
        cmd = (
            "winget install yt-dlp ffmpeg aria2; "
            "Write-Host '安装完成'; Read-Host '回车退出...'"
            if self.lang == "zh"
            else
            "winget install yt-dlp ffmpeg aria2; "
            "Write-Host 'Installation completed.'; Read-Host 'Press Enter to exit...'"
        )

        subprocess.run(["start", "powershell", "-NoExit", "-Command", cmd], shell=True)


def _install_local_re(self):
    t = self.translations[self.lang]

    """自动下载并部署 N_m3u8DL-RE"""
    # 如果文件已存在且能运行，跳过
    if os.path.exists(self.re_path):
        msg = "RE 引擎已存在，跳过。\n" if self.lang == "zh" else "RE engine already exists.\n"
        self.log(f">>> {msg}", "success")
        return

    # 确保 bin 目录存在
    if not os.path.exists(self.bin_dir):
        os.makedirs(self.bin_dir, exist_ok=True)

    self.log(">>> 正在从 GitHub 获取最新版本信息...\n" if self.lang == "zh" else "Fetching latest version info...",
             "info")

    # 1. 确定当前系统的架构关键词
    arch_map = {
        ("Windows", "AMD64"): "win-x64",
        ("Windows", "x86"): "win-NT6.0-x86",
        ("Darwin", "x86_64"): "osx-x64",  # Intel Mac
        ("Darwin", "arm64"): "osx-arm64"  # M1/M2 Mac
    }
    key = (self.system, platform.machine())
    search_str = arch_map.get(key)

    if not search_str:
        # 兜底：如果识别不出架构，默认尝试 x64
        search_str = "win-x64" if self.system == "Windows" else "darwin-x64"

    try:
        # 2. 访问 GitHub API 获取 Latest Release JSON
        api_url = "https://api.github.com/repos/nilaoda/N_m3u8DL-RE/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Python Downloader"})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())

        # 3. 筛选对应架构的下载链接
        download_url = None
        asset_name = ""
        for asset in data["assets"]:
            name = asset["name"].lower()
            # 排除 sha256 文件，只找压缩包
            if search_str in name and not name.endswith(".sha256"):
                download_url = asset["browser_download_url"]
                asset_name = asset["name"]
                break

        if not download_url:
            raise Exception(f"未找到适配当前系统 ({search_str}) 的发布文件"
                            if self.lang == "zh"
                            else f"No release asset found for the current system ({search_str})"
                            )

        # 4. 下载文件
        self.log(f">>> 找到目标: {asset_name}\n" if self.lang == "zh" else f">>> Target found: {asset_name}\n",
                 "info")
        self.log(">>> 正在下载，请稍候...\n" if self.lang == "zh" else ">>> Downloading, please wait...\n",
                 "warning")

        with tempfile.TemporaryDirectory() as temp_dir:
            local_zip = os.path.join(temp_dir, asset_name)

            # 带有进度的下载
            def progress(count, block_size, total_size):
                percent = int(count * block_size * 100 / total_size)
                if percent % 10 == 0:  # 减少刷新频率
                    # 这里可以更新UI进度条，或者简单打印
                    pass

            urllib.request.urlretrieve(download_url, local_zip, progress)

            # 5. 解压并提取
            self.log(
                ">>> 下载完成，正在解压...\n" if self.lang == "zh" else ">>> Download completed. Extracting files...\n",
                "info")

            # 目标文件名
            target_name = "N_m3u8DL-RE.exe" if self.system == "Windows" else "N_m3u8DL-RE"
            found_binary = False

            if asset_name.endswith(".zip"):
                with zipfile.ZipFile(local_zip, 'r') as z:
                    for info in z.infolist():
                        if info.filename.split('/')[-1] == target_name:
                            # 读取二进制数据并写入 bin
                            with z.open(info) as source, open(self.re_path, "wb") as dest:
                                shutil.copyfileobj(source, dest)
                            found_binary = True
                            break
            elif asset_name.endswith(".tar.gz"):
                with tarfile.open(local_zip, "r:gz") as t:
                    for member in t.getmembers():
                        if member.name.split('/')[-1] == target_name:
                            f = t.extractfile(member)
                            if f:
                                with open(self.re_path, "wb") as dest:
                                    shutil.copyfileobj(f, dest)
                                found_binary = True
                                break

            if found_binary:
                # 6. 最后的处理：赋权
                if self.system == "Darwin":
                    os.chmod(self.re_path, 0o755)
                self.log(f">>> N_m3u8DL-RE 部署成功！({self.re_path})\n"
                         if self.lang == "zh"
                         else f">>> N_m3u8DL-RE deployed successfully! ({self.re_path})\n",
                         "success"
                         )
            else:
                raise Exception(
                    "解压失败，未在压缩包中找到执行文件" if self.lang == "zh" else "Extraction failed: executable file not found in the archive")

    except Exception as e:
        raise Exception(f"RE引擎安装失败: {str(e)}"
                        if self.lang == "zh"
                        else f"RE engine installation failed: {str(e)}"
                        )