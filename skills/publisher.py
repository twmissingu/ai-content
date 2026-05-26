"""Publisher Agent — distribute approved articles to platform draft boxes.

Phase 1: WeChat (baoyu-post-to-wechat) + AiToEarn (小红书/抖音/视频号).
Graceful per-platform failure (one fails, others continue).
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    FAILED_DIR,
    KB_DIR,
    PLATFORM_DISPLAY,
    REVIEW_DIR,
    STATUS_DIR,
)
from skills.action import mark_processed

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_status(pct: int, detail: str, error: Optional[str] = None):
    status = {
        "agent": "publisher",
        "progress_pct": pct,
        "detail": detail,
        "started_at": RUN_TIMESTAMP,
        "error": error,
    }
    path = STATUS_DIR / "publisher.json"
    tmp = STATUS_DIR / ".publisher.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)


def find_article(target_id: str) -> tuple[Optional[Path], Optional[dict]]:
    """Find article files matching target_id in queue/review/."""
    meta_path = REVIEW_DIR / f"{target_id}.meta.json"
    article_path = REVIEW_DIR / f"{target_id}.md"

    # Try different patterns
    if not meta_path.exists():
        for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
            meta_path = f
            article_path = REVIEW_DIR / f.stem.replace(".meta", "") + ".md"
            break

    if not meta_path.exists():
        return None, None

    meta = json.loads(meta_path.read_text())
    if not article_path.exists():
        article_path = REVIEW_DIR / f"{meta_path.stem.replace('.meta', '')}.md"

    return article_path if article_path.exists() else None, meta


def _publish_wechat(article_path: Path, meta: dict) -> bool:
    """Publish to WeChat draft box via baoyu-post-to-wechat."""
    try:
        result = subprocess.run(
            ["npx", "skills", "run", "baoyu-post-to-wechat",
             "--param", f"content={article_path.read_text(encoding='utf-8')[:5000]}"],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[publisher] WeChat failed: {e}")
        return False


def _publish_aitoearn(platform: str, article_path: Path, meta: dict) -> bool:
    """Publish to AiToEarn platform draft box via MCP."""
    content = article_path.read_text(encoding="utf-8")
    tool_map = {
        "xiaohongshu": ("aitoearn_createImageTextDraft", "IMAGE_TEXT"),
        "douyin": ("aitoearn_createVideoDraft", "VIDEO"),
        "kuaishou": ("aitoearn_createVideoDraft", "VIDEO"),
    }
    tool_name, draft_type = tool_map.get(platform, (None, None))
    if not tool_name:
        return False

    try:
        params = json.dumps({
            "title": meta.get("topic", ""),
            "content": content[:3000],
            "draftType": draft_type,
            "platform": platform,
        })
        result = subprocess.run(
            ["hermes", "mcp", "call", tool_name, "--params", params],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[publisher] {platform} failed: {e}")
        return False


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    platforms = sys.argv[2:] if len(sys.argv) > 2 else ["wechat", "xiaohongshu", "douyin"]

    if not target_id:
        # Scan for latest unreviewed approved action
        print("[publisher] No target_id provided, looking for approve action...")
        return

    _write_status(10, f"开始分发: {target_id}")
    article, meta = find_article(target_id)
    if not article or not meta:
        error = f"Article not found: {target_id}"
        _write_status(0, error, error)
        print(f"[publisher] {error}")
        return

    print(f"[publisher] Distributing: {meta.get('topic', 'unknown')}")
    results: dict[str, bool] = {}

    for platform in platforms:
        display = PLATFORM_DISPLAY.get(platform, platform)
        _write_status(20 + platforms.index(platform) * 20, f"分发到{display}")

        if platform == "wechat":
            ok = _publish_wechat(article, meta)
        elif platform in ("xiaohongshu", "douyin", "kuaishou"):
            ok = _publish_aitoearn(platform, article, meta)
        else:
            ok = False

        results[platform] = ok
        if ok:
            print(f"[publisher] {display}: ✅")
        else:
            print(f"[publisher] {display}: ❌")
            # Record failure
            failed = {
                "target_id": target_id,
                "platform": platform,
                "timestamp": RUN_TIMESTAMP,
                "error": f"分发到{display}失败",
                "meta": meta,
            }
            failed_path = FAILED_DIR / f"{RUN_TIMESTAMP}-{platform}.json"
            tmp = FAILED_DIR / f".{RUN_TIMESTAMP}-{platform}.json.tmp"
            tmp.write_text(json.dumps(failed, ensure_ascii=False, indent=2))
            os.rename(tmp, failed_path)

    # Summary
    success_count = sum(1 for v in results.values() if v)
    _write_status(100, f"分发完成: {success_count}/{len(platforms)} 成功")
    print(f"[publisher] Done. {success_count}/{len(platforms)} succeeded")


if __name__ == "__main__":
    main()
