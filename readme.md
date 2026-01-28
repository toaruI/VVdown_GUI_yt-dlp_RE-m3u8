# VDown

VDown is a cross-platform video downloader focused on stability, maintainability, and modern download engine support.
It provides a GUI-based workflow and manages all required dependencies locally without relying on system-level package managers.

VDown 是一个跨平台的视频下载工具，注重稳定性、可维护性以及现代下载引擎的支持。
项目提供图形界面，并通过本地 bin 目录管理所有依赖，不依赖系统级包管理器。

---

## Features | 功能特性

### Core Features | 核心功能

- Multiple download engines  
  支持多个下载引擎：
  - yt-dlp（通用下载引擎）
  - aria2（多连接高速下载引擎）
  - N_m3u8DL-RE（M3U8 / 流媒体下载引擎）

- Local bin-based dependency management  
  本地 bin 目录依赖管理：
  - No Homebrew / apt / yum required  
    不需要 Homebrew、apt 或 yum
  - No modification to system PATH  
    不修改系统环境变量
  - Same behavior for source and packaged builds  
    源码运行与打包运行行为一致

- Threaded downloading  
  多线程下载支持：
  - RE engine supports `--thread-count`  
    RE 引擎支持 `--thread-count` 参数
  - Default behavior follows engine defaults (CPU core count)  
    默认行为遵循引擎自身的 CPU 核心数设置

- Cookie handling with extractor-aware strategy  
  基于 extractor 行为的 Cookie 处理策略：
  - Browser cookies for sites such as Twitter / X  
    对 Twitter / X 等站点自动使用浏览器 Cookie
  - cookies.txt file support  
    支持 cookies.txt 文件
  - Avoids guest-mode failures  
    避免游客模式导致的解析失败

---

### UI & UX | 界面与体验

- Desktop GUI built with PySide6  
  基于 PySide6 构建的桌面 GUI

- Log-driven interface (no blocking dialogs)  
  基于日志的界面设计（不使用阻塞弹窗）

- Runtime language switching (English / 中文)  
  支持中英文运行时切换

- Clear separation between UI, core logic, installer, and network layers  
  UI、核心逻辑、安装器与网络层职责清晰分离

---

## Default Behavior & Project Status | 默认行为与项目状态

- This GUI currently uses the default configuration of yt-dlp, FFmpeg, and N_m3u8DL-RE.  
  当前 GUI 使用 yt-dlp、FFmpeg 以及 N_m3u8DL-RE 的默认配置。

- Advanced features (fine-grained engine options, extended post-processing, and advanced workflow customization) are still under active development.  
  高级功能（如更细粒度的引擎参数配置、扩展后处理流程以及复杂下载工作流）仍在持续开发中。

- The current focus is correctness, stability, and a clean architecture.  
  当前版本的重点是正确性、稳定性以及清晰的工程结构。

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
  所有依赖都会被下载到 `bin/` 目录中

- Includes:  
  包含以下组件：
  - yt-dlp
  - ffmpeg
  - aria2
  - N_m3u8DL-RE

No system-level installation is required.  
无需任何系统级安装。

---

### Download Workflow | 下载流程

1. Paste the video URL  
   粘贴视频链接
2. Select a download engine  
   选择下载引擎
3. (Optional) Configure thread count  
   （可选）设置线程数
4. Click **Download**  
   点击 **Download**

---

## Engine Notes | 引擎说明

### yt-dlp

- General-purpose downloader  
  通用下载引擎
- Supports a wide range of websites  
  支持大量视频网站
- Uses browser cookies automatically for supported extractors  
  对支持的 extractor 自动使用浏览器 Cookie

### aria2

- High-performance multi-connection downloader  
  高性能多连接下载引擎
- Suitable for large files  
  适合大文件下载

### N_m3u8DL-RE

- Designed for M3U8 / streaming downloads  
  专为 M3U8 / 流媒体下载设计
- Supports `--thread-count`  
  支持线程数设置
- Default behavior uses CPU core count  
  默认使用 CPU 核心数

---

## Acknowledgements | 致谢

This project is built on top of the following open-source projects:

本项目基于以下优秀的开源项目构建：

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
感谢以上项目的所有贡献者。

---

## Disclaimer | 免责声明

This tool is intended for educational and personal use only.  
Please comply with local laws and website terms of service.

本工具仅供学习与个人使用，请遵守当地法律法规及网站服务条款。

---

## License | 许可证

MIT License (see LICENSE file for details).