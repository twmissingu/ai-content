"""Publisher Agent — distribute approved articles to platform draft boxes.

Phase 1: WeChat (baoyu-post-to-wechat) + AiToEarn (小红书/抖音/视频号).
Graceful per-platform failure (one fails, others continue).

Uses AgentBase for unified status writing, logging, and metrics.
Uses temp files instead of command-line args for content passing (security).
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config.settings import (
    FAILED_DIR,
    KB_DIR,
    PLATFORM_DISPLAY,
    REVIEW_DIR,
    STATUS_DIR,
)
from skills.agent_schemas import PublisherResult
from skills.common import AgentBase, agent_main
from skills.platform_adapters import adapt_content
from skills.publisher_webbridge import WebBridgePublisher


class PublisherAgent(AgentBase):
    """Publisher agent for distributing content to platforms."""
    
    name = "publisher"
    version = "1.0.0"
    
    def __init__(self):
        super().__init__(enable_metrics=True)
        self._run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    def find_article(self, target_id: str) -> tuple[Optional[Path], Optional[dict]]:
        """Find article files matching target_id in queue/review/."""
        meta_path = REVIEW_DIR / f"{target_id}.meta.json"
        article_path = REVIEW_DIR / f"{target_id}.md"

        # Try different patterns
        if not meta_path.exists():
            for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
                meta_path = f
                article_path = REVIEW_DIR / f"{f.stem.replace('.meta', '')}.md"
                break

        if not meta_path.exists():
            return None, None

        try:
            meta = json.loads(meta_path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to read meta file {meta_path}: {e}")
            return None, None
        if not article_path.exists():
            article_path = REVIEW_DIR / f"{meta_path.stem.replace('.meta', '')}.md"

        return article_path if article_path.exists() else None, meta

    def _publish_wechat(self, article_path: Path, meta: dict) -> bool:
        """Publish to WeChat draft box via baoyu-post-to-wechat.

        Uses temp file instead of command-line args for security.
        Passes image paths as --cover and --image arguments.
        """
        raw_content = article_path.read_text(encoding='utf-8')
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, "wechat")
        content = content[:5000]

        # Collect image paths from meta
        images = meta.get("images", [])
        cover = images[0] if images else None
        inline_images = images[1:] if len(images) > 1 else []

        # Write content to temp file (avoid command-line injection)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.md', prefix='wechat_')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                f.write(content)

            cmd = ["npx", "skills", "run", "baoyu-post-to-wechat", "--file", tmp_path]
            if cover and Path(cover).exists():
                cmd.extend(["--cover", cover])
            for img in inline_images:
                if Path(img).exists():
                    cmd.extend(["--image", img])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"WeChat publish failed: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _publish_webbridge(self, platform: str, article_path: Path, meta: dict) -> bool:
        """Publish to Xiaohongshu/Douyin via Kimi WebBridge browser automation."""
        raw_content = article_path.read_text(encoding="utf-8")
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, platform)

        images = meta.get("images", [])
        # Filter to only existing files
        valid_images = [img for img in images if Path(img).exists()]

        publisher = WebBridgePublisher(logger=self.logger)

        if platform == "xiaohongshu":
            result = publisher.publish_xiaohongshu(title, content[:3000], valid_images)
        elif platform == "douyin":
            result = publisher.publish_douyin(title, content[:3000], valid_images)
        else:
            self.logger.warning(f"WebBridge does not support platform: {platform}")
            return False

        if result["status"] == "success":
            return True
        else:
            self.logger.error(f"{platform} publish failed: {result.get('error')}")
            return False

    def _publish_aitoearn_mcp(self, platform: str, article_path: Path, meta: dict) -> bool:
        """Fallback: publish via AiToEarn MCP (for kuaishou/shipinhao)."""
        raw_content = article_path.read_text(encoding="utf-8")
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, platform)
        tool_map = {
            "kuaishou": "aitoearn_createVideoDraft",
            "shipinhao": "aitoearn_createVideoDraft",
        }
        tool_name = tool_map.get(platform)
        if not tool_name:
            self.logger.warning(f"No MCP tool for platform: {platform}")
            return False

        params = {
            "title": title or meta.get("topic", ""),
            "content": content[:3000],
            "draftType": "VIDEO",
            "platform": platform,
        }

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='aitoearn_')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False)
            result = subprocess.run(
                ["hermes", "mcp", "call", tool_name, "--params-file", tmp_path],
                capture_output=True, text=True, timeout=90,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"{platform} MCP publish failed: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _publish_video(self, platform: str, article_path: Path, meta: dict) -> bool:
        """Publish video content to video platforms (douyin/shipinhao/kuaishou/bilibili).

        Uses AiToEarn createVideoDraft MCP tool with video file.
        Video file path is read from meta.videos[0].
        """
        videos = meta.get("videos", [])
        if not videos:
            self.logger.info(f"No video found for {platform}, skipping video distribution")
            return False

        video_path = videos[0]
        if not Path(video_path).exists():
            self.logger.warning(f"Video file not found: {video_path}")
            return False

        raw_content = article_path.read_text(encoding="utf-8")
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, platform)

        tool_map = {
            "douyin": "aitoearn_createVideoDraft",
            "shipinhao": "aitoearn_createVideoDraft",
            "kuaishou": "aitoearn_createVideoDraft",
            "bilibili": "aitoearn_createVideoDraft",
        }
        tool_name = tool_map.get(platform)
        if not tool_name:
            self.logger.warning(f"No video MCP tool for platform: {platform}")
            return False

        params = {
            "title": title or meta.get("topic", ""),
            "content": content[:3000],
            "draftType": "VIDEO",
            "platform": platform,
            "videoPath": video_path,
        }

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='aitoearn_video_')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False)
            result = subprocess.run(
                ["hermes", "mcp", "call", tool_name, "--params-file", tmp_path],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                self.logger.info(f"Video published to {platform}: {video_path}")
                return True
            else:
                self.logger.warning(f"Video publish to {platform} failed: {result.stderr[:200]}")
                return False
        except Exception as e:
            self.logger.error(f"{platform} video MCP publish failed: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def run(self, target_id: Optional[str] = None, platforms: Optional[list[str]] = None):
        """Main publisher logic."""
        if target_id is None:
            target_id = sys.argv[1] if len(sys.argv) > 1 else None
        
        if platforms is None:
            platforms = sys.argv[2:] if len(sys.argv) > 2 else ["wechat", "xiaohongshu", "douyin"]

        if not target_id:
            self.logger.warning("No target_id provided, looking for approve action...")
            return

        self.write_status("开始分发", 10, f"开始分发: {target_id}")
        article, meta = self.find_article(target_id)
        if not article or not meta:
            error = f"Article not found: {target_id}"
            self.write_error(error)
            self.logger.error(error)
            return

        self.logger.info(f"Distributing: {meta.get('topic', 'unknown')}")
        results: dict[str, bool] = {}

        def _publish_one(platform: str) -> tuple[str, bool]:
            """Publish to a single platform (runs in thread pool)."""
            # Video platforms: prefer video distribution if video exists
            video_platforms = ("douyin", "shipinhao", "kuaishou", "bilibili")
            has_video = bool(meta.get("videos"))

            if platform == "wechat":
                return platform, self._publish_wechat(article, meta)
            elif platform in ("xiaohongshu",):
                return platform, self._publish_webbridge(platform, article, meta)
            elif platform in video_platforms and has_video:
                return platform, self._publish_video(platform, article, meta)
            elif platform in ("douyin",):
                return platform, self._publish_webbridge(platform, article, meta)
            elif platform in ("kuaishou", "shipinhao"):
                return platform, self._publish_aitoearn_mcp(platform, article, meta)
            return platform, False

        self.write_status("分发中", 20, f"分发到 {len(platforms)} 个平台")

        with ThreadPoolExecutor(max_workers=len(platforms)) as executor:
            futures = {executor.submit(_publish_one, p): p for p in platforms}
            for future in as_completed(futures):
                try:
                    platform, ok = future.result()
                except Exception as e:
                    platform = futures[future]
                    ok = False
                    self.logger.error(f"{PLATFORM_DISPLAY.get(platform, platform)}: unhandled exception: {e}")
                display = PLATFORM_DISPLAY.get(platform, platform)
                results[platform] = ok

                if ok:
                    self.logger.info(f"{display}: success")
                else:
                    self.logger.warning(f"{display}: failed")
                    self.write_failed_action(
                        target_id=target_id,
                        platform=platform,
                        error=f"分发到{display}失败",
                        meta=meta,
                    )

                # Validate result via schema
                try:
                    PublisherResult.model_validate({
                        "platform": platform,
                        "status": "success" if ok else "failed",
                    })
                except Exception as e:
                    self.logger.warning(f"PublisherResult validation failed for {platform}: {e}")

        # Summary
        success_count = sum(1 for v in results.values() if v)
        self.write_completed(
            detail=f"分发完成: {success_count}/{len(platforms)} 成功",
            results=results,
        )
        self.logger.info(f"Done. {success_count}/{len(platforms)} succeeded")


def main():
    """Entry point for backward compatibility."""
    agent = PublisherAgent()
    agent.run()


if __name__ == "__main__":
    main()
