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
from skills.action import mark_processed
from skills.agent_schemas import PublisherResult
from skills.common import AgentBase, agent_main
from skills.platform_adapters import adapt_content


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

        meta = json.loads(meta_path.read_text())
        if not article_path.exists():
            article_path = REVIEW_DIR / f"{meta_path.stem.replace('.meta', '')}.md"

        return article_path if article_path.exists() else None, meta

    def _publish_wechat(self, article_path: Path, meta: dict) -> bool:
        """Publish to WeChat draft box via baoyu-post-to-wechat.

        Uses temp file instead of command-line args for security.
        """
        raw_content = article_path.read_text(encoding='utf-8')
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, "wechat")
        content = content[:5000]
        
        # Write content to temp file (avoid command-line injection)
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.md', prefix='wechat_')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                f.write(content)
            
            result = subprocess.run(
                ["npx", "skills", "run", "baoyu-post-to-wechat",
                 "--file", tmp_path],
                capture_output=True, text=True, timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"WeChat publish failed: {e}")
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _publish_aitoearn(self, platform: str, article_path: Path, meta: dict) -> bool:
        """Publish to AiToEarn platform draft box via MCP."""
        raw_content = article_path.read_text(encoding="utf-8")
        title = raw_content.split('\n')[0].lstrip('# ').strip() if raw_content else ""
        title, content = adapt_content(title, raw_content, platform)
        tool_map = {
            "xiaohongshu": ("aitoearn_createImageTextDraft", "IMAGE_TEXT"),
            "douyin": ("aitoearn_createVideoDraft", "VIDEO"),
            "kuaishou": ("aitoearn_createVideoDraft", "VIDEO"),
            "shipinhao": ("aitoearn_createVideoDraft", "VIDEO"),
        }
        tool_name, draft_type = tool_map.get(platform, (None, None))
        if not tool_name:
            self.logger.warning(f"No tool mapping for platform: {platform}")
            return False

        # Write params to temp file for security
        params = {
            "title": title or meta.get("topic", ""),
            "content": content[:3000],
            "draftType": draft_type,
            "platform": platform,
        }
        
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.json', prefix='aitoearn_')
        try:
            with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False)
            
            result = subprocess.run(
                ["hermes", "mcp", "call", tool_name, "--params-file", tmp_path],
                capture_output=True, text=True, timeout=60,
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"{platform} publish failed: {e}")
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

        for i, platform in enumerate(platforms):
            display = PLATFORM_DISPLAY.get(platform, platform)
            progress = 20 + i * (60 // len(platforms))
            self.write_status("分发中", progress, f"分发到{display}")

            if platform == "wechat":
                ok = self._publish_wechat(article, meta)
            elif platform in ("xiaohongshu", "douyin", "kuaishou", "shipinhao"):
                ok = self._publish_aitoearn(platform, article, meta)
            else:
                ok = False

            results[platform] = ok

            # Validate result via schema
            try:
                PublisherResult.model_validate({
                    "platform": platform,
                    "status": "success" if ok else "failed",
                })
            except Exception as e:
                self.logger.warning(f"PublisherResult validation failed for {platform}: {e}")

            if ok:
                self.logger.info(f"{display}: ✅")
            else:
                self.logger.warning(f"{display}: ❌")
                # Record failure
                self.write_failed_action(
                    target_id=target_id,
                    platform=platform,
                    error=f"分发到{display}失败",
                    meta=meta,
                )

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
