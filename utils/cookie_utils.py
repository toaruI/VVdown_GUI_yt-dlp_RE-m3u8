# core/cookie_utils.py
import os
from urllib.parse import urlparse


def parse_cookie_file(filepath: str, target_url: str, max_len: int = 6000):
    """
    读取 Netscape 格式的 cookie txt（例如来自浏览器导出的 cookie 文件），
    返回用于 HTTP 请求的 Cookie header 字符串（"name=value; name2=value2"）。
    - 纯函数：不做日志、不抛出致命异常（调用方可根据返回值判断）。
    - target_url 用于匹配域名（只返回与目标 host 相关的 cookie 条目）。
    """
    if not os.path.exists(filepath):
        return ""

    try:
        parsed = urlparse(target_url)
        host = parsed.netloc.split(':')[0]
        if not host:
            return ""
    except Exception:
        # 解析 URL 失败时不抛出，返回空 cookie
        return ""

    cookie_parts = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                fields = line.split('\t')
                if len(fields) >= 7:
                    domain_field = fields[0]
                    name = fields[5]
                    value = fields[6]
                    if domain_field and (domain_field.strip('.') in host or host in domain_field):
                        cookie_parts.append(f"{name}={value}")
        final_cookie = "; ".join(cookie_parts)
        if len(final_cookie) > max_len:
            return final_cookie[:max_len]
        return final_cookie

    except Exception:
        # 读取或解析出错，返回空字符串以便调用方选择降级行为
        return ""
