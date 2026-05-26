"""Knowledge Agent — archive approved articles into kb/.

Phase 1: simple file copy (no AI analysis).
Archives article + meta to kb/history/{date}/ and updates kb/topics/.
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import KB_DIR, REVIEW_DIR


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _archive_article(article_path: Path, meta: dict) -> Path:
    """Copy article to kb/history/ with date prefix."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    history_dir = KB_DIR / "history" / date_str
    _ensure_dir(history_dir)

    dest = history_dir / article_path.name
    shutil.copy2(article_path, dest)
    return dest


def _update_topics_index(topic: str, platform: str):
    """Append topic to kb/topics/INDEX.md."""
    topics_dir = KB_DIR / "topics"
    _ensure_dir(topics_dir)
    index_path = topics_dir / "INDEX.md"
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry = f"- {date_str} | {platform} | {topic}\n"
    with open(index_path, "a") as f:
        f.write(entry)


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not target_id:
        # Find latest completed article
        metas = sorted(REVIEW_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True)
        if not metas:
            print("[knowledge] No articles to archive")
            return
        meta_path = metas[0]
    else:
        meta_path = REVIEW_DIR / f"{target_id}.meta.json"
        if not meta_path.exists():
            print(f"[knowledge] Meta not found: {meta_path}")
            return

    meta = json.loads(meta_path.read_text())
    article_path = REVIEW_DIR / meta_path.stem.replace(".meta", "") + ".md"

    if not article_path.exists():
        print(f"[knowledge] Article not found: {article_path}")
        return

    print(f"[knowledge] Archiving: {meta.get('topic', 'unknown')}")

    # Copy to history
    dest = _archive_article(article_path, meta)
    print(f"[knowledge] Archived to: {dest}")

    # Update topics index
    _update_topics_index(meta.get("topic", ""), meta.get("platform_standard", "wechat"))
    print("[knowledge] Topics index updated")

    print("[knowledge] Done")


if __name__ == "__main__":
    main()
