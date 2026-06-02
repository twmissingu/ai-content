"""Kimi WebBridge publisher — browser automation for Xiaohongshu and Douyin.

Uses Kimi WebBridge (http://127.0.0.1:10086) to control the user's real Chrome
browser and publish content with images to social media platforms.

Requires:
  - Kimi WebBridge daemon running on localhost:10086
  - Chrome extension installed and connected
  - User logged into target platforms in Chrome
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import httpx

WEBBRIDGE_URL = os.environ.get("WEBBRIDGE_URL", "http://127.0.0.1:10086/command")
DEFAULT_TIMEOUT = 30


class WebBridgeError(Exception):
    """WebBridge operation failed."""
    pass


class WebBridgePublisher:
    """Publish content to social media via Kimi WebBridge."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)

    _VALID_ACTIONS = frozenset({
        "navigate", "click", "fill", "upload", "snapshot",
        "evaluate", "close_tab",
    })

    def _call(self, action: str, args: dict, session: str = "publish") -> dict:
        """Call Kimi WebBridge HTTP API."""
        if action not in self._VALID_ACTIONS:
            raise WebBridgeError(f"Unknown WebBridge action: {action!r}")
        if not isinstance(args, dict):
            raise WebBridgeError(f"args must be a dict, got {type(args).__name__}")
        payload = {"action": action, "args": args, "session": session}
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                resp = client.post(WEBBRIDGE_URL, json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            raise WebBridgeError(
                "Kimi WebBridge not running. Start it at http://127.0.0.1:10086"
            )
        except Exception as e:
            raise WebBridgeError(f"WebBridge call failed: {e}")

    def _wait_for_element(self, selector: str, session: str = "publish",
                          timeout: int = 10) -> bool:
        """Wait for an element to appear on the page."""
        for _ in range(timeout * 2):
            result = self._call("snapshot", {}, session)
            tree = result.get("result", result.get("data", ""))
            if selector in str(tree):
                return True
            time.sleep(0.5)
        return False

    def _wait_for_page_ready(self, session: str = "publish", timeout: int = 10) -> bool:
        """Wait for page to finish loading via snapshot checks."""
        for _ in range(timeout * 2):
            result = self._call("snapshot", {}, session)
            tree = str(result.get("result", result.get("data", "")))
            # Page is ready if snapshot returns non-empty content
            if tree and len(tree) > 50:
                return True
            time.sleep(0.5)
        return False

    def _wait_for_settle(self, session: str = "publish", timeout: int = 5) -> bool:
        """Wait for page DOM to stabilize (two consecutive similar snapshots)."""
        prev = ""
        for _ in range(timeout * 2):
            result = self._call("snapshot", {}, session)
            curr = str(result.get("result", result.get("data", "")))
            if curr and curr == prev:
                return True
            prev = curr
            time.sleep(0.5)
        return False

    def _inject_files(self, selector: str, files: list[str],
                      session: str = "publish") -> bool:
        """Upload files to a file input element."""
        result = self._call("upload", {"selector": selector, "files": files}, session)
        success = result.get("success", False) or result.get("result", {}).get("success", False)
        if success:
            self.logger.info(f"Uploaded {len(files)} files to {selector}")
        else:
            self.logger.warning(f"Upload failed: {result}")
        return success

    def publish_xiaohongshu(self, title: str, content: str,
                            images: list[str]) -> dict:
        """Publish to Xiaohongshu web creator.

        Args:
            title: Post title
            content: Post body text
            images: List of local image file paths

        Returns: {"status": "success"|"failed", "error": str|None}
        """
        session = "xhs-publish"
        try:
            # Step 1: Navigate to creator page
            self._call("navigate", {
                "url": "https://creator.xiaohongshu.com/publish/publish",
                "newTab": True,
            }, session)
            self._wait_for_page_ready(session)

            # Step 2: Find and upload images
            if images:
                # Try common file input selectors for XHS
                uploaded = False
                for selector in ['input[type="file"]', 'input[accept*="image"]']:
                    try:
                        if self._inject_files(selector, images, session):
                            uploaded = True
                            break
                    except Exception:
                        continue

                if not uploaded:
                    # Fallback: use evaluate to find file inputs
                    result = self._call("evaluate", {
                        "code": """
                        const inputs = document.querySelectorAll('input[type="file"]');
                        inputs.length > 0 ? inputs[0].className || 'found' : 'none';
                        """
                    }, session)
                    self.logger.warning(f"File input search result: {result}")

                self._wait_for_settle(session)

            # Step 3: Fill title
            # XHS title input is usually a contenteditable or input element
            for title_selector in [
                'input[placeholder*="标题"]',
                '[contenteditable][class*="title"]',
                '#title',
                '.title-input',
            ]:
                try:
                    self._call("fill", {"selector": title_selector, "value": title}, session)
                    break
                except Exception:
                    continue

            # Step 4: Fill content
            for content_selector in [
                '[contenteditable][class*="content"]',
                '.ql-editor',
                '[contenteditable]',
                '#content',
            ]:
                try:
                    self._call("fill", {"selector": content_selector, "value": content}, session)
                    break
                except Exception:
                    continue

            self._wait_for_settle(session)

            # Step 5: Click publish button
            for btn_selector in [
                'button:has-text("发布")',
                'button:has-text("Publish")',
                '.publishBtn',
                'button[class*="publish"]',
            ]:
                try:
                    self._call("click", {"selector": btn_selector}, session)
                    break
                except Exception:
                    continue

            self._wait_for_settle(session)
            self.logger.info("Xiaohongshu publish completed")
            return {"status": "success", "error": None}

        except WebBridgeError as e:
            self.logger.error(f"Xiaohongshu publish failed: {e}")
            return {"status": "failed", "error": str(e)}
        except Exception as e:
            self.logger.error(f"Xiaohongshu publish error: {e}")
            return {"status": "failed", "error": str(e)}
        finally:
            try:
                self._call("close_tab", {}, session)
            except Exception:
                pass

    def publish_douyin(self, title: str, content: str,
                       images: list[str]) -> dict:
        """Publish to Douyin web creator.

        Args:
            title: Post title
            content: Post body text
            images: List of local image file paths

        Returns: {"status": "success"|"failed", "error": str|None}
        """
        session = "douyin-publish"
        try:
            # Step 1: Navigate to creator page
            self._call("navigate", {
                "url": "https://creator.douyin.com/creator-micro/content/upload",
                "newTab": True,
            }, session)
            self._wait_for_page_ready(session)

            # Step 2: Upload images
            if images:
                for selector in ['input[type="file"]', 'input[accept*="image"]']:
                    try:
                        if self._inject_files(selector, images, session):
                            break
                    except Exception:
                        continue
                self._wait_for_settle(session)

            # Step 3: Fill title and content
            for title_selector in [
                'input[placeholder*="标题"]',
                '[contenteditable][class*="title"]',
                '.title-input',
            ]:
                try:
                    self._call("fill", {"selector": title_selector, "value": title}, session)
                    break
                except Exception:
                    continue

            for content_selector in [
                '[contenteditable][class*="content"]',
                '.ql-editor',
                '[contenteditable]',
            ]:
                try:
                    self._call("fill", {"selector": content_selector, "value": content}, session)
                    break
                except Exception:
                    continue

            self._wait_for_settle(session)

            # Step 4: Click publish
            for btn_selector in [
                'button:has-text("发布")',
                'button:has-text("Publish")',
                'button[class*="publish"]',
            ]:
                try:
                    self._call("click", {"selector": btn_selector}, session)
                    break
                except Exception:
                    continue

            self._wait_for_settle(session)
            self.logger.info("Douyin publish completed")
            return {"status": "success", "error": None}

        except WebBridgeError as e:
            self.logger.error(f"Douyin publish failed: {e}")
            return {"status": "failed", "error": str(e)}
        except Exception as e:
            self.logger.error(f"Douyin publish error: {e}")
            return {"status": "failed", "error": str(e)}
        finally:
            try:
                self._call("close_tab", {}, session)
            except Exception:
                pass


def check_webbridge_available() -> bool:
    """Check if Kimi WebBridge is running."""
    try:
        with httpx.Client(timeout=3) as client:
            resp = client.get("http://127.0.0.1:10086")
            return resp.status_code < 500
    except Exception:
        return False
