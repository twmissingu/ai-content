"""Knowledge Agent — archive approved articles into kb/.

Phase 1: simple file copy (no AI analysis).
Archives article + meta to kb/history/{date}/ and updates kb/topics/.

Uses AgentBase for unified status writing, logging, and metrics.
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import KB_DIR, REVIEW_DIR
from skills.common import AgentBase, agent_main


class KnowledgeAgent(AgentBase):
    """Knowledge agent for archiving approved articles."""

    name = "knowledge"
    version = "1.0.0"

    def __init__(self):
        super().__init__(enable_metrics=False)

    def _ensure_dir(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)

    def _archive_article(self, article_path: Path, meta: dict) -> Path:
        """Copy article to kb/history/ with date prefix."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        history_dir = KB_DIR / "history" / date_str
        self._ensure_dir(history_dir)

        dest = history_dir / article_path.name
        shutil.copy2(article_path, dest)
        return dest

    def _update_topics_index(self, topic: str, platform: str):
        """Append topic to kb/topics/INDEX.md."""
        topics_dir = KB_DIR / "topics"
        self._ensure_dir(topics_dir)
        index_path = topics_dir / "INDEX.md"
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry = f"- {date_str} | {platform} | {topic}\n"
        with open(index_path, "a") as f:
            f.write(entry)

    def run(self, target_id: str = None):
        """Main knowledge archival logic."""
        if target_id is None:
            target_id = sys.argv[1] if len(sys.argv) > 1 else None

        if not target_id:
            # Find latest completed article
            metas = sorted(REVIEW_DIR.glob("*.meta.json"), key=os.path.getmtime, reverse=True)
            if not metas:
                self.logger.info("No articles to archive")
                return
            meta_path = metas[0]
        else:
            meta_path = REVIEW_DIR / f"{target_id}.meta.json"
            if not meta_path.exists():
                self.write_error(f"Meta not found: {meta_path}")
                return

        meta = json.loads(meta_path.read_text())
        article_path = REVIEW_DIR / (meta_path.stem.replace(".meta", "") + ".md")

        if not article_path.exists():
            self.write_error(f"Article not found: {article_path}")
            return

        topic = meta.get('topic', 'unknown')
        self.write_status("归档中", 50, f"归档: {topic}")
        self.logger.info(f"Archiving: {topic}")

        # Copy to history
        dest = self._archive_article(article_path, meta)
        self.logger.info(f"Archived to: {dest}")

        # Update topics index
        self._update_topics_index(topic, meta.get("platform_standard", "wechat"))

        self.write_completed(f"归档完成: {topic}")
        self.logger.info("Done")


def main():
    """Entry point for backward compatibility."""
    agent = KnowledgeAgent()
    agent.run()


if __name__ == "__main__":
    main()
