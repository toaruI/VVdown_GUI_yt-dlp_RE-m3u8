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

from config.config import IS_WIN

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

        if IS_WIN:
            url = _pick_asset(
                assets,
                keywords=["win", "gpl", "zip"],
                any_of=["win64", "windows"],
            )
        else:
            url = _pick_asset(
                assets,
                keywords=["gpl"],
                any_of=["mac", "osx", "darwin", "apple"],
            )

        return self._mirror(url)

    def _aria2_url(self) -> str:
        repo = "aria2/aria2"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])

        if IS_WIN:
            url = _pick_asset(
                assets,
                keywords=["win"],
                any_of=["64", "x64"],
            )
        else:
            # macOS builds are inconsistent; try multiple patterns
            url = _pick_asset(
                assets,
                keywords=[],
                any_of=["darwin", "mac", "osx"],
            )

        return self._mirror(url)

    def _re_url(self) -> str:
        repo = "nilaoda/N_m3u8DL-RE"
        data = _github_api_get(GITHUB_API.format(repo=repo))
        assets = data.get("assets", [])
        if IS_WIN:
            url = _pick_asset(assets, keywords=["exe"])
        else:
            url = _pick_asset(assets, keywords=["linux"]) or _pick_asset(assets, keywords=["mac"]) or _pick_asset(assets, keywords=["n_m3u8dl-re"])
        return self._mirror(url)

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
