"""Feedback Agent — data recovery, analysis, and strategy feedback.

Phase 3 implementation:
1. Read publication records from kb/history/
2. Attempt data recovery via AiToEarn MCP (if available)
3. Identify top-performing content (viral detection)
4. Update kb/viral/ and kb/strategy/ with insights
5. Update Scout scoring weights based on findings

Runs daily at 22:00 via Hermes cron.

Uses AgentBase for unified status writing, logging, and metrics.
"""

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DATA_DIR, KB_DIR, STATUS_DIR
from skills.common import AgentBase, agent_main
from skills.llm import chat_structured

VIRAL_THRESHOLD_PCT = 0.20  # Top 20% by reads = viral
HISTORY_DIR = KB_DIR / "history"
VIRAL_DIR = KB_DIR / "viral"
STRATEGY_DIR = KB_DIR / "strategy"


class FeedbackAgent(AgentBase):
    """Feedback agent for data recovery and strategy analysis."""
    
    name = "feedback"
    version = "1.0.0"
    
    def __init__(self):
        super().__init__(enable_metrics=True)
        self._run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Step 1: Collect articles from history ─────────────────────
    def _collect_articles(self) -> list[dict]:
        """Read all articles from kb/history/ and extract metadata."""
        articles = []
        if not HISTORY_DIR.exists():
            return articles

        for date_dir in sorted(HISTORY_DIR.iterdir()):
            if not date_dir.is_dir():
                continue
            for f in date_dir.glob("*.md"):
                text = f.read_text(encoding="utf-8", errors="ignore")
                title = text.split("\n")[0].removeprefix("# ").strip() or f.stem
                # Try to find matching meta
                meta = {}
                meta_file = f.with_suffix(".meta.json")
                if meta_file.exists():
                    try:
                        meta = json.loads(meta_file.read_text())
                    except (json.JSONDecodeError, OSError):
                        pass

                articles.append({
                    "title": title,
                    "date": date_dir.name,
                    "path": str(f),
                    "meta": meta,
                    "word_count": meta.get("word_count", len(text)),
                    "content": text[:500],  # preview
                })

        return articles

    # ── Step 2: Attempt data recovery ─────────────────────────────
    def _query_aitoearn_analytics(self) -> list[dict]:
        """Try to get article performance data from AiToEarn MCP."""
        try:
            # AiToEarn may or may not have analytics tools
            result = subprocess.run(
                ["hermes", "mcp", "list"],
                capture_output=True, text=True, timeout=15,
            )
            tools = result.stdout
            if "analytics" in tools.lower() or "data" in tools.lower() or "stats" in tools.lower():
                # Found potential data tool — try calling it
                for tool_name in ["aitoearn_getAnalytics", "aitoearn_getData",
                                  "aitoearn_getStats", "aitoearn_dataList"]:
                    try:
                        r = subprocess.run(
                            ["hermes", "mcp", "call", tool_name],
                            capture_output=True, text=True, timeout=30,
                        )
                        if r.returncode == 0:
                            data = json.loads(r.stdout)
                            if isinstance(data, list):
                                return data
                            if isinstance(data, dict) and "data" in data:
                                return data["data"]
                    except Exception:
                        continue
            return []
        except Exception as e:
            self.logger.debug(f"Analytics query failed: {e}")
            return []

    # ── Step 3: Viral detection ───────────────────────────────────
    def _detect_viral(self, articles: list[dict], platform_data: list[dict]) -> Optional[dict]:
        """Identify viral content patterns from available data."""
        if not articles:
            return None

        # Extract title patterns
        titles = [a["title"] for a in articles]
        title_patterns = Counter()
        for t in titles:
            # Check for number patterns
            if re.search(r'\d+', t):
                title_patterns["数字型"] += 1
            if re.search(r'[？?]', t):
                title_patterns["提问型"] += 1
            if re.search(r'比|对比|vs|还是', t):
                title_patterns["对比型"] += 1
            if re.search(r'如何|怎么|怎样|指南|教程', t):
                title_patterns["教程型"] += 1

        # Extract keywords (simple frequency)
        all_words: list[str] = []
        for a in articles:
            words = re.findall(r'[\u4e00-\u9fff]{2,}', a["title"])
            all_words.extend(words)
        keyword_freq = Counter(all_words).most_common(20)

        # Group articles by direction from meta if available
        topic_directions: dict[str, int] = {}
        for a in articles:
            meta = a.get("meta", {})
            if meta.get("topic"):
                topic_directions[meta["topic"]] = topic_directions.get(meta["topic"], 0) + 1

        viral = {
            "generated_at": self._run_date,
            "article_count": len(articles),
            "title_patterns": dict(title_patterns.most_common(5)),
            "top_keywords": [{"word": w, "count": c} for w, c in keyword_freq[:10]],
            "topic_directions": topic_directions,
            "data_source": "local_only" if not platform_data else "aitoearn",
        }

        return viral

    # ── Step 4: Update knowledge base ─────────────────────────────
    def _update_viral_kb(self, viral: dict):
        """Write viral insights to kb/viral/."""
        VIRAL_DIR.mkdir(parents=True, exist_ok=True)
        path = VIRAL_DIR / f"viral_{self._run_date}.json"
        from skills.common import atomic_write_json
        atomic_write_json(path, viral)
        self.logger.info(f"Viral data written: {path}")

    def _update_strategy_kb(self, viral: dict):
        """Generate strategy recommendations based on viral data."""
        STRATEGY_DIR.mkdir(parents=True, exist_ok=True)

        # Generate strategy via LLM
        prompt = f"""你是内容策略分析师。基于以下选题数据，生成本周写作策略建议。

数据:
- 文章总数: {viral.get('article_count', 0)}
- 标题模式: {json.dumps(viral.get('title_patterns', {}), ensure_ascii=False)}
- 高频关键词: {json.dumps(viral.get('top_keywords', [])[:5], ensure_ascii=False)}
- 数据来源: {viral.get('data_source', 'local')}

请输出 JSON:
{{"recommendation": "本周策略建议",
  "focus_directions": ["方向1", "方向2"],
  "avoid_topics": ["避免的话题"],
  "title_style": "推荐的标题风格"}}
"""
        try:
            start_time = time.monotonic()
            result = chat_structured(
                system_prompt="你是一个严谨的内容策略分析师。",
                user_prompt=prompt,
                temperature=0.5,
            )
            duration = time.monotonic() - start_time
            self.record_llm_call(duration=duration, success=True)
        except Exception as e:
            self.logger.error(f"Strategy LLM call failed: {e}")
            self.record_llm_call(success=False)
            result = {
                "recommendation": "数据不足，暂无法生成策略建议",
                "focus_directions": [],
                "avoid_topics": [],
                "title_style": "保持现状",
            }

        from skills.common import atomic_write_json
        path = STRATEGY_DIR / f"strategy_{self._run_date}.json"
        atomic_write_json(path, {
            "generated_at": self._run_date,
            **result,
        })
        self.logger.info(f"Strategy written: {path}")

    # ── Main ──────────────────────────────────────────────────────
    def run(self):
        """Main feedback logic."""
        self.logger.info(f"Starting daily data recovery ({self._run_date})")
        self.write_status("采集文章", 10, "采集文章记录")

        # Step 1: Collect articles
        self.start_stage("collect")
        articles = self._collect_articles()
        self.end_stage("collect")
        self.logger.info(f"Found {len(articles)} articles in history")
        self.write_status("采集文章", 30, f"找到{len(articles)}篇文章")

        if not articles:
            self.write_completed("暂无历史数据")
            return

        # Step 2: Try data recovery
        self.write_status("数据回收", 50, "尝试数据回收")
        self.start_stage("recovery")
        platform_data = self._query_aitoearn_analytics()
        self.end_stage("recovery")
        
        if platform_data:
            self.logger.info(f"Retrieved {len(platform_data)} platform data points")
        else:
            self.logger.info("No platform analytics available (Phase 3 enhancement)")

        # Step 3: Viral detection
        self.write_status("爆款识别", 70, "爆款识别")
        self.start_stage("viral_detection")
        viral = self._detect_viral(articles, platform_data)
        self.end_stage("viral_detection")
        
        if not viral:
            self.write_completed("数据不足")
            return

        self.logger.info(f"Viral patterns: {len(viral.get('top_keywords', []))} keywords")
        self._update_viral_kb(viral)

        # Step 4: Strategy update
        self.write_status("更新策略", 85, "更新策略库")
        self.start_stage("strategy")
        self._update_strategy_kb(viral)
        self.end_stage("strategy")

        # Done
        detail = f"完成: {len(articles)}篇文章"
        if platform_data:
            detail += f", {len(platform_data)}条平台数据"
        self.write_completed(detail)
        self.logger.info("Done")


def main():
    """Entry point for backward compatibility."""
    agent = FeedbackAgent()
    agent.run()


if __name__ == "__main__":
    main()
