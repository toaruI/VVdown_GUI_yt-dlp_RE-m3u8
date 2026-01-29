# utils/net_utils.py
"""
Network / resource utilities (GitHub API–based).

Responsibilities:
- Detect CN (China mainland) network environment
- Resolve latest binary download URLs via GitHub Releases API

This module is PURE backend logic:
- No Qt
- No UI dialogs
- Safe to call from worker threads
"""

from __future__ import annotations

import json
import socket
import sys
import urllib.request
from dataclasses import dataclass
from typing import Dict, Optional

from config.config import IS_WIN, IS_MAC, IS_LINUX, IS_ARM

# ------------------------------
# Region detection
# ------------------------------

def detect_cn_region(timeout: float = 2.0) -> bool:
    """
    Best-effort detection of whether the current network is likely inside
    mainland China.
    """
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=timeout)
        return False
    except OSError:
        return True


# ------------------------------
# GitHub helpers
# ------------------------------

GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"


def _github_api_get(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VDown-Installer",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_asset(
    assets: list[dict],
    *,
    keywords: list[str],
    any_of: list[str] | None = None
) -> Optional[str]:
    # strict match: all keywords present
    for a in assets:
        name = a.get("name", "").lower()
        if all(k in name for k in keywords):
            return a.get("browser_download_url")

    # relaxed match: any keyword in any_of
    if any_of:
        for a in assets:
            name = a.get("name", "").lower()
            if any(k in name for k in any_of):
                return a.get("browser_download_url")

    return None


# ------------------------------
# Browser plugin pages (static)
# ------------------------------

@dataclass(frozen=True)
class ResourceEntry:
    global_url: str
    cn_url: str


PLUGIN_RESOURCES: Dict[str, ResourceEntry] = {
    "cookies_txt": ResourceEntry(
        global_url="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
        cn_url="https://www.crx4chrome.com/crx/32289/",
    ),
    "catcatch": ResourceEntry(
        global_url="https://chromewebstore.google.com/detail/cat-catch/jfedfbgedapdagkghmgibemcoggfppbb",
        cn_url="https://www.crx4chrome.com/crx/164024/",
    ),
}


# ------------------------------
# Dependency resolution via GitHub API
# ------------------------------

class ResourceProvider:
    """
    Resolve dependency download URLs dynamically via GitHub API.
    """

    def __init__(self, is_cn_mode: bool | None = None):
        if is_cn_mode is None:
            is_cn_mode = detect_cn_region()
        self.is_cn = bool(is_cn_mode)

    # ---- plugin URLs ----

    def get_plugin_url(self, plugin_name: str) -> str:
        entry = PLUGIN_RESOURCES.get(plugin_name)
        if not entry:
            return ""
        return entry.cn_url if self.is_cn else entry.global_url

    # ---- dependency URLs ----

    def get_dependency_url(self, tool_name: str) -> str:
        try:
            if tool_name == "yt-dlp":
                return self._yt_dlp_url()
            if tool_name == "ffmpeg":
                return self._ffmpeg_url()
            if tool_name == "aria2":
                return self._aria2_url()
            if tool_name == "N_m3u8DL-RE":
                return self._re_url()
        except Exception:
            return ""
        return ""

    # --------------------------
    # Individual resolvers
    # --------------------------

    def _yt_dlp_url(self) -> str:
        repo = "yt-dlp/yt-dlp"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])
        if IS_WIN:
            url = _pick_asset(assets, keywords=["yt-dlp", "exe"])
        else:
            url = _pick_asset(assets, keywords=["yt-dlp"])
        return self._mirror(url)

    def _ffmpeg_url(self) -> str:
        repo = "BtbN/FFmpeg-Builds"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])

        is_arm = IS_ARM

        def name(a: dict) -> str:
            return a.get("name", "").lower()

        # Windows
        if IS_WIN:
            for a in assets:
                n = name(a)
                if "win" in n and "gpl" in n and n.endswith(".zip"):
                    return self._mirror(a.get("browser_download_url"))

        # Deleted BtbN macOS blocks per instructions

        # macOS fallback: ffmpeg-static (single-file darwin binaries ONLY)
        if IS_MAC:
            repo = "eugeneware/ffmpeg-static"
            try:
                data = _github_api_get(GITHUB_API.format(repo=repo))
                assets = data.get("assets", [])

                def is_valid_macos_ffmpeg(a: dict) -> bool:
                    name = a.get("name", "").lower()
                    size = a.get("size", 0)
                    return (
                            name.startswith("ffmpeg-darwin-")
                            and "." not in name
                            and size > 5_000_000
                    )

                # Prefer exact architecture
                if IS_ARM:
                    for a in assets:
                        if is_valid_macos_ffmpeg(a) and "arm64" in a.get("name", "").lower():
                            return self._mirror(a.get("browser_download_url"))
                else:
                    for a in assets:
                        n = a.get("name", "").lower()
                        if is_valid_macos_ffmpeg(a) and ("x64" in n or "x86_64" in n):
                            return self._mirror(a.get("browser_download_url"))

                # Fallback: any valid macOS ffmpeg binary
                for a in assets:
                    if is_valid_macos_ffmpeg(a):
                        return self._mirror(a.get("browser_download_url"))
            except Exception:
                pass

        return ""

    def _aria2_url(self) -> str:
        repo = "aria2/aria2"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])

        # macOS: aria2 is optional (no stable official binary)
        if IS_MAC:
            return ""

        is_arm = IS_ARM

        def _name(a: dict) -> str:
            return a.get("name", "").lower()

        # Windows: prefer win64 zip
        if IS_WIN:
            for a in assets:
                n = _name(a)
                if ("win" in n and ("64" in n or "x64" in n) and n.endswith('.zip')):
                    return self._mirror(a.get('browser_download_url'))

        # macOS Apple Silicon (arm64)
        if IS_MAC:
            if is_arm:
                for a in assets:
                    n = _name(a)
                    if (
                        ("darwin" in n or "mac" in n or "osx" in n)
                        and ("arm64" in n or "aarch64" in n)
                        and "linux" not in n
                    ):
                        return self._mirror(a.get('browser_download_url'))

            # macOS Intel (x86_64)
            for a in assets:
                n = _name(a)
                if (
                    ("darwin" in n or "mac" in n or "osx" in n)
                    and ("x86_64" in n or "amd64" in n or "intel" in n or not is_arm)
                    and "linux" not in n
                ):
                    return self._mirror(a.get('browser_download_url'))

        # Linux fallback
        if IS_LINUX:
            for a in assets:
                n = _name(a)
                if "linux" in n and not n.endswith('.exe'):
                    return self._mirror(a.get('browser_download_url'))

        return ""

    def _re_url(self) -> str:
        repo = "nilaoda/N_m3u8DL-RE"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])

        def _name(a: dict) -> str:
            return a.get("name", "").lower()

        # Windows: only .exe
        if IS_WIN:
            for a in assets:
                n = _name(a)
                if IS_ARM and n.endswith('win-arm64.zip'):
                    return self._mirror(a.get('browser_download_url'))
                if not IS_ARM and n.endswith('win-x64.zip'):
                    return self._mirror(a.get('browser_download_url'))

        # macOS: prefer mac/darwin/osx, explicitly exclude linux
        for a in assets:
            n = _name(a)
            if (
                ('mac' in n or 'darwin' in n or 'osx' in n)
                and 'linux' not in n
                and not n.endswith('.exe')
            ):
                return self._mirror(a.get('browser_download_url'))

        # Linux fallback
        # Do NOT auto-download on Linux: upstream releases are source/build archives
        # Users should install via system package manager or provide binaries manually

        return ""

    # --------------------------
    # Helpers
    # --------------------------

    def _mirror(self, url: Optional[str]) -> str:
        if not url:
            return ""
        if self.is_cn:
            return "https://ghproxy.net/" + url
        return url

    def as_dict(self) -> dict:
        return {
            "is_cn": self.is_cn,
            "dependencies": ["yt-dlp", "ffmpeg", "aria2", "N_m3u8DL-RE"],
        }
