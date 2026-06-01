"""Reader routes — proxy fetch external URLs, return cleaned content."""

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query

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


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private/loopback/link-local/reserved."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
    except ValueError:
        return True  # Invalid IP — block it


def _resolve_and_check(hostname: str) -> str:
    """Resolve hostname, verify all IPs are public. Returns first IP or raises."""
    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise HTTPException(400, f"DNS 解析失败: {hostname}") from e

    if not resolved:
        raise HTTPException(400, f"无法解析域名: {hostname}")

    for _, _, _, _, sockaddr in resolved:
        ip = sockaddr[0]
        if _is_private_ip(ip):
            raise HTTPException(403, f"禁止访问内网地址: {ip}")
    return resolved[0][4][0]  # Return first resolved IP


def _validate_redirect_url(url: str) -> None:
    """Validate a redirect target URL for SSRF."""
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise HTTPException(403, f"无效的重定向 URL") from e

    if parsed.scheme not in ("http", "https"):
        raise HTTPException(403, f"禁止的重定向协议: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(403, "重定向 URL 缺少主机名")

    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise HTTPException(403, "禁止访问本地地址")

    _resolve_and_check(hostname)


class _SSRFSafeTransport:
    """Wraps httpx transport to validate redirect targets against SSRF."""

    def __init__(self, original_transport):
        self._transport = original_transport

    async def handle_async_request(self, request):
        # Validate the redirect target URL before each request
        _validate_redirect_url(str(request.url))
        return await self._transport.handle_async_request(request)

    async def aclose(self):
        await self._transport.aclose()


@router.get("/fetch")
async def fetch_url(url: str = Query(..., min_length=1)):
    """Fetch external URL and return cleaned text content.

    Only allows http/https URLs. Returns first ~10000 chars.
    SSRF protection: resolves DNS once, checks IPs, then fetches directly.
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "仅支持 http/https URL")

    # Phase 1: Validate initial URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(400, "无效的 URL")

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(400, "URL 缺少主机名")

    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise HTTPException(403, "禁止访问本地地址")

    # Phase 2: Resolve DNS and check — single resolve, then fetch via IP
    resolved_ip = _resolve_and_check(hostname)

    try:
        import httpx
    except ImportError:
        raise HTTPException(500, "httpx 未安装，无法代理抓取")

    # Phase 3: Build URL with resolved IP, set Host header for virtual hosting
    parsed = urlparse(url)
    ip_url = f"{parsed.scheme}://{resolved_ip}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}{parsed.path}"
    if parsed.query:
        ip_url += f"?{parsed.query}"

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; AIContentBot/1.0)",
        "Host": hostname,
    }

    # Phase 4: Fetch with redirect validation
    # We handle redirects manually to validate each target
    try:
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=15,
            verify=True,  # Still verify TLS certs using SNI
        ) as client:
            current_url = ip_url
            current_headers = dict(headers)
            max_redirects = 5

            for _ in range(max_redirects):
                resp = await client.get(current_url, headers=current_headers)

                if resp.status_code in (301, 302, 303, 307, 308):
                    redirect_url = resp.headers.get("location", "")
                    if not redirect_url:
                        break

                    # Resolve relative redirects
                    if redirect_url.startswith("/"):
                        redirect_url = f"{parsed.scheme}://{hostname}{redirect_url}"

                    # Validate redirect target (checks DNS + private IP)
                    _validate_redirect_url(redirect_url)

                    # Update URL for next hop (resolve to IP again)
                    redir_parsed = urlparse(redirect_url)
                    redir_ip = _resolve_and_check(redir_parsed.hostname)
                    current_url = (
                        f"{redir_parsed.scheme}://{redir_ip}:"
                        f"{redir_parsed.port or (443 if redir_parsed.scheme == 'https' else 80)}"
                        f"{redir_parsed.path}"
                    )
                    if redir_parsed.query:
                        current_url += f"?{redir_parsed.query}"
                    current_headers["Host"] = redir_parsed.hostname

                    # Change method to GET on 303 (See Other)
                    if resp.status_code == 303:
                        continue
                    continue

                # Not a redirect — this is the final response
                resp.raise_for_status()
                break
            else:
                raise HTTPException(502, "重定向次数过多")

    except httpx.TimeoutException:
        raise HTTPException(504, "抓取超时")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"目标网站返回 {e.response.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fetch failed for {url}: {e}")
        raise HTTPException(502, "抓取失败")

    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        text = _strip_html_tags(resp.text)
    else:
        text = resp.text

    return {"url": url, "content": text[:10000], "truncated": len(text) > 10000}
