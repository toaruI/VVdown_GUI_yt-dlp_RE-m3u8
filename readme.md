# VVDown

VVDown is a cross-platform video downloader focused on stability, maintainability, and modern download engine support.
It provides a GUI-based workflow and manages all required dependencies locally without relying on system-level package
managers.

VVDown 是一个跨平台的视频下载工具，注重稳定性、可维护性以及现代下载引擎的支持。
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
    - No mandatory Homebrew / apt / yum dependency  
      不强制依赖 Homebrew、apt 或 yum
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

## Browser Integration | 浏览器集成

### Built-in Helper for Browser Plugins | 内置浏览器插件辅助功能

VVDown provides built-in helpers to guide users in obtaining browser-side data required for advanced downloads.
The application itself does **not** embed or inject browser extensions, but offers clear entry points and workflows
for using existing open-source browser plugins.

VVDown 内置了浏览器插件辅助入口，用于引导用户获取高级下载所需的数据。
程序本身**不会嵌入或注入任何浏览器扩展**，而是基于现有的开源浏览器插件提供清晰、可控的使用流程。

Supported use cases include:

支持的使用场景包括：

- Exporting browser cookies as `cookies.txt`  
  导出浏览器 Cookies 为 `cookies.txt`

- Capturing M3U8 / stream URLs from web pages  
  捕获网页中的 M3U8 / 流媒体链接

These helpers are optional and are only needed for certain websites or advanced workflows.

这些辅助功能是可选的，仅在特定网站或高级使用场景下需要。

---

### Recommended Browser Plugins | 推荐使用的浏览器插件

VVDown acknowledges and recommends the following open-source browser plugins:

VVDown 对以下开源浏览器插件表示感谢，并推荐用户使用：

- **Get cookies.txt (locally)**  
  Used to export browser cookies into `cookies.txt` files.  
  用于将浏览器 Cookies 导出为 `cookies.txt` 文件。

  GitHub: https://github.com/kairi003/Get-cookies.txt-LOCALLY

- **Cat Catch**  
  Used to capture M3U8 and streaming media URLs from web pages.  
  用于捕获网页中的 M3U8 及流媒体资源链接。

  GitHub: https://github.com/xifangczy/cat-catch

VVDown does not modify, redistribute, or bundle these plugins.
All rights and licenses remain with their respective authors.

VVDown 不会修改、分发或打包上述插件，其版权及许可证均归插件作者所有。

---

### Platform Notes | 平台说明

- **Windows**  
  On Windows, an external `cookies.txt` file is required for authenticated downloads.  
  Browser cookies cannot be accessed directly by external tools.

  在 Windows 平台上，进行登录态下载时**必须提供外置的 `cookies.txt` 文件**，
  外部程序无法直接读取浏览器 Cookies。

- **macOS / Linux**  
  Browser cookies may be used directly for supported engines and extractors.

  在 macOS / Linux 平台上，部分引擎和 extractor 支持直接使用浏览器 Cookies。

- **FFmpeg on macOS**  
  On macOS, FFmpeg is provided via standalone builds from the `ffmpeg-static` project.

  在 macOS 平台上，FFmpeg 使用 `ffmpeg-static` 项目提供的独立可执行文件。

- **aria2 on macOS**  
  On macOS, aria2 is treated as an optional dependency. The GUI can detect an existing `aria2c` binary
  (commonly installed via Homebrew), but will not automatically install aria2 on macOS.

  在 macOS 平台上，aria2 被视为可选依赖。GUI 可以识别系统中已有的 `aria2c`
  （例如通过 Homebrew 安装），但不会在 macOS 下自动安装 aria2。

  Recommended installation via Homebrew:  
  推荐使用 Homebrew 安装：

  ```bash
  brew install aria2
  ```

- This GUI currently uses the default configuration of yt-dlp, FFmpeg, and N_m3u8DL-RE.  
  当前 GUI 使用 yt-dlp、FFmpeg 以及 N_m3u8DL-RE 的默认配置。

- Advanced features (fine-grained engine options, extended post-processing, and advanced workflow customization) are
  still under active development.  
  高级功能（如更细粒度的引擎参数配置、扩展后处理流程以及复杂下载工作流）仍在持续开发中。

- The current focus is correctness, stability, and a clean architecture.  
  当前版本的重点是正确性、稳定性以及清晰的工程结构。

Note:
While VVDown does not require Homebrew to function, Homebrew is a convenient and recommended way to install
optional tools such as `aria2` on macOS.

说明：
VVDown 本身不依赖 Homebrew 才能运行，但在 macOS 平台上，Homebrew 是安装如 `aria2` 等可选工具的推荐方式。

---

## Running from Source | 从源码运行

### Requirements | 环境要求

- Python 3.10 or newer
- pip

### Install Python Dependencies | 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### Launch | 启动

## Quick Start | 快速开始

```bash
python main.py
```

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

No mandatory system-level installation is required.  
在 macOS 平台上，不强制要求系统级安装。

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
- On macOS, aria2 is optional and typically installed via Homebrew rather than bundled automatically.  
  在 macOS 平台上，aria2 为可选组件，通常通过 Homebrew 安装，而不是由程序自动安装。

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

- ffmpeg-static (macOS standalone builds)  
  https://github.com/eugeneware/ffmpeg-static

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