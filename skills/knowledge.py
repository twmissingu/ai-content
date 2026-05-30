"""Knowledge Agent — archive approved articles into kb/.

Archives article + meta to kb/history/{date}/, runs LLM analysis,
and updates kb/topics/.

Uses AgentBase for unified status writing, logging, and metrics.
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import KB_DIR, REVIEW_DIR
from skills.common import AgentBase, agent_main
from skills.llm import chat_structured


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

    def _analyze_article(self, content: str, meta: dict) -> dict[str, Any]:
        """Use LLM to extract keywords, tags, and writing patterns."""
        topic = meta.get("topic", "")
        prompt = f"""分析以下文章，返回 JSON：

文章标题：{topic}
文章内容（前3000字）：{content[:3000]}

请提取：
1. keywords: 5-10 个关键词（小写）
2. tags: 2-4 个分类标签（如"AI"、"产品"、"创业"）
3. writing_patterns: 2-3 个写作特征（如"数据驱动"、"故事开头"）
4. summary: 1-2 句摘要
5. quality_score: 整体质量评分 0-100

必须返回合法 JSON，不要返回 markdown 代码块。"""

        result = chat_structured(
            system_prompt="你是一个文章分析专家。返回合法 JSON。",
            user_prompt=prompt,
            temperature=0.3,
        )
        return result

    def _save_meta(self, dest: Path, meta: dict, analysis: dict):
        """Save .meta.json alongside the archived article."""
        merged = {
            "archived_at": datetime.now().isoformat(),
            "original_meta": meta,
            "analysis": analysis,
        }
        meta_path = dest.with_suffix(".meta.json")
        tmp_path = meta_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
        tmp_path.rename(meta_path)

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

        # LLM analysis (non-blocking: failure doesn't stop archival)
        try:
            self.write_status("AI 分析中", 70, f"分析: {topic}")
            content = article_path.read_text(encoding="utf-8", errors="ignore")
            analysis = self._analyze_article(content, meta)
            self._save_meta(dest, meta, analysis)
            self.logger.info(f"Analysis saved: {dest.with_suffix('.meta.json')}")
        except Exception as e:
            self.logger.warning(f"AI analysis failed (article still archived): {e}")

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
