"""Reader routes — proxy fetch external URLs, return cleaned content."""

import logging
import re

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

logger = logging.getLogger("gaoding.dashboard")

router = APIRouter(prefix="/api/reader", tags=["reader"])


def _strip_html_tags(html: str) -> str:
    """Basic HTML to text conversion."""
    # Remove script/style
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Block elements → newlines
    html = re.sub(r'<(br|p|div|h[1-6]|li|tr|blockquote)[^>]*/?>', '\n', html, flags=re.IGNORECASE)
    # Strip all remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    # Decode common entities
    for entity, char in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&quot;', '"'), ('&#39;', "'"), ('&nbsp;', ' ')]:
        html = html.replace(entity, char)
    # Collapse whitespace
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()


@router.get("/fetch")
async def fetch_url(url: str = Query(..., min_length=1)):
    """Fetch external URL and return cleaned text content.

    Only allows http/https URLs. Returns first ~10000 chars.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "仅支持 http/https URL")

    # SSRF protection: block private/internal IPs
    try:
        from urllib.parse import urlparse
        import ipaddress
        import socket

        parsed = urlparse(url)
        hostname = parsed.hostname
        if hostname:
            # Block localhost variants
            if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
                raise HTTPException(403, "禁止访问本地地址")
            # Resolve and check IP
            try:
                resolved = socket.getaddrinfo(hostname, None)
                for family, _, _, _, sockaddr in resolved:
                    ip = ipaddress.ip_address(sockaddr[0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        raise HTTPException(403, f"禁止访问内网地址: {ip}")
            except socket.gaierror:
                pass  # DNS resolution failed, let httpx handle it
    except HTTPException:
        raise
    except Exception:
        pass  # URL parsing failed, let httpx handle it

    try:
        import httpx
    except ImportError:
        raise HTTPException(500, "httpx 未安装，无法代理抓取")

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AIContentBot/1.0)"})
            resp.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(504, "抓取超时")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"目标网站返回 {e.response.status_code}")
    except Exception as e:
        logger.error(f"Fetch failed for {url}: {e}")
        raise HTTPException(502, f"抓取失败: {e}")

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        text = _strip_html_tags(resp.text)
    else:
        text = resp.text

    return {"url": url, "content": text[:10000], "truncated": len(text) > 10000}
