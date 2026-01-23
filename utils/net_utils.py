# utils/net_utils.py

class ResourceProvider:
    """
    资源提供者：根据是否为中国大陆模式，返回不同的下载/访问链接
    """

    def __init__(self, is_cn_mode=False):
        self.is_cn = is_cn_mode

    def get_plugin_url(self, plugin_name):
        """获取浏览器插件下载地址"""
        urls = {
            "cookie_editor": {
                "global": "https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc",
                # CN模式下，可以使用极简插件或Crx4Chrome等第三方镜像，或者引导用户去国内扩展商店
                "cn": "https://www.crx4chrome.com/crx/32289/"
            },
            "cat_catch": {
                "global": "https://chromewebstore.google.com/detail/cat-catch/jfedfbgedapdagkghmgibemcoggfppbb",
                "cn": "https://www.crx4chrome.com/crx/164024/"
            }
        }

        target = urls.get(plugin_name, {})
        return target.get("cn" if self.is_cn else "global", "")

    def get_dependency_url(self, tool_name):
        """获取 yt-dlp 或 ffmpeg 的下载地址"""
        # 这是一个示例，你可以换成你自己的 OSS 地址或者 Gitee 发行版链接
        urls = {
            "yt-dlp": {
                "global": "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe",
                "cn": "https://ghproxy.net/https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            },
            "ffmpeg": {
                "global": "https://github.com/BtbN/FFmpeg-Builds/releases",
                "cn": "https://ghproxy.net/https://github.com/BtbN/FFmpeg-Builds/releases"
            }
        }
        return urls.get(tool_name, {}).get("cn" if self.is_cn else "global", "")

    @staticmethod
    def auto_detect_region():
        """(可选) 简单的网络探测，判断是否需要开启 CN 模式"""
        import socket
        try:
            # 尝试连接 Google DNS，超时则认为在国内
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return False
        except OSError:
            return True
