

# VDown

VDown is a cross-platform video downloader focused on stability, maintainability, and modern download engine support.
It provides a GUI-based workflow and manages all required dependencies locally without relying on system-level package managers.

VDown 是一个跨平台的视频下载工具，注重稳定性、可维护性以及现代下载引擎的支持。
项目提供图形界面，并通过本地 bin 目录管理所有依赖，不依赖系统级包管理器。

---

## Features | 功能特性

### Core Features | 核心功能

- Multiple download engines
  - yt-dlp (general-purpose downloader)
  - aria2 (high-performance segmented downloader)
  - N_m3u8DL-RE (M3U8 / streaming downloader)

- Local bin-based dependency management
  - No Homebrew / apt / yum required
  - No modification to system PATH
  - Same behavior for source and packaged builds

- Threaded downloading
  - RE engine supports `--thread-count`
  - Default behavior follows engine defaults (CPU core count)

- Cookie handling with extractor-aware strategy
  - Browser cookies for sites such as Twitter / X
  - cookies.txt file support
  - Avoids guest-mode failures

---

### UI & UX | 界面与体验

- Desktop GUI built with PySide6
- Log-driven interface (no blocking dialogs)
- Runtime language switching (English / 中文)
- Clear separation between UI, core logic, installer, and network layers

---

## Quick Start | 快速开始

### Launch | 启动

```bash
python main.py
```

Or run the packaged executable if available.

或运行已打包的可执行文件（如有）。

---

### Fix Dependencies | 修复依赖

On first launch, click **Fix Dependencies**.

首次启动时，点击 **Fix Dependencies**：

- All dependencies are downloaded into the `bin/` directory
- Includes:
  - yt-dlp
  - ffmpeg
  - aria2
  - N_m3u8DL-RE

No system-level installation is required.

无需任何系统级安装。

---

### Download Workflow | 下载流程

1. Paste the video URL
2. Select a download engine
3. (Optional) Configure thread count
4. Click **Download**

下载步骤：

1. 粘贴视频链接
2. 选择下载引擎
3. （可选）设置线程数
4. 点击 **Download**

---

## Engine Notes | 引擎说明

### yt-dlp

- General-purpose downloader
- Supports a wide range of websites
- Uses browser cookies automatically for supported extractors

### aria2

- High-performance multi-connection downloader
- Suitable for large files

### N_m3u8DL-RE

- Designed for M3U8 / streaming downloads
- Supports `--thread-count`
- Default behavior uses CPU core count

---

## Project Structure | 项目结构

```text
VDown/
├─ core/
│  ├─ downloader.py
│  ├─ installer.py
├─ utils/
│  ├─ net_utils.py
│  ├─ cookie_utils.py
├─ ui/
│  ├─ app_window.py
│  ├─ widgets.py
├─ bin/              # All dependencies are stored here
├─ config/
├─ translations.json
└─ main.py
```

---

## Acknowledgements | 致谢

This project is built on top of the following open-source projects:

- yt-dlp
  https://github.com/yt-dlp/yt-dlp

- aria2
  https://github.com/aria2/aria2

- N_m3u8DL-RE
  https://github.com/nilaoda/N_m3u8DL-RE

- FFmpeg
  https://ffmpeg.org
  (static builds provided by BtbN)

- Qt / PySide6
  https://www.qt.io
  https://wiki.qt.io/Qt_for_Python

Special thanks to all contributors of these projects.

---

## Disclaimer | 免责声明

This tool is intended for educational and personal use only.
Please comply with local laws and website terms of service.

本工具仅供学习与个人使用，请遵守当地法律法规及网站服务条款。

---

## License | 许可证

MIT License (or the license specified in the LICENSE file).