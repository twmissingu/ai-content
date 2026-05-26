"""Writer Worker — Xiaohongshu standard (300-800 chars, emoji, carousel).

Phase 3: called by writer_router.py as a parallel Worker.
Accepts --topic-file <path> and --work-dir <path> arguments.
Outputs <work_dir>/{timestamp}-xhs.md + .meta.json.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DOMAIN
from skills.llm import chat, chat_structured

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
TYPE = "xiaohongshu"


def _parse_args() -> tuple[dict, Path]:
    """Parse --topic-file and --work-dir args."""
    topic_file = work_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--topic-file" and i + 1 < len(sys.argv):
            topic_file = Path(sys.argv[i + 1])
        elif arg == "--work-dir" and i + 1 < len(sys.argv):
            work_dir = Path(sys.argv[i + 1])
    if not topic_file or not work_dir:
        # Fallback: read first pending topic
        from config.settings import PENDING_DIR
        files = sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True)
        if not files:
            raise SystemExit("No topic file found")
        topic_file = files[0]
        work_dir = Path("queue/tmp") / RUN_TIMESTAMP
        work_dir.mkdir(parents=True, exist_ok=True)
    return json.loads(topic_file.read_text()), work_dir


def _draft(topic: dict) -> str:
    """Generate a Xiaohongshu-style post (300-800 chars, emoji, first-person)."""
    prompt = f"""你是一个小红书内容创作者。请根据以下选题写一篇小红书笔记。

选题: {topic['title']}
描述: {topic.get('description', '')}

写作要求:
- 字数: 300-800 字
- 语气: 轻松口语化，适当使用 emoji
- 立场: 第一人称经验分享
- 结构: 开头痛点/好奇 → 主体干货 → 结尾互动引导
- 话题标签: 3-5 个相关 hashtag
- 不要"家人们""姐妹们"这种通用开头

直接输出笔记正文，不要额外说明。
"""
    return chat(
        system_prompt="你是一个小红书爆款笔记创作者。",
        user_prompt=prompt,
        temperature=0.8,
    )


def _generate_titles(text: str, topic_title: str) -> tuple[str, list[dict]]:
    """Generate attention-grabbing Xiaohongshu titles."""
    result = chat_structured(
        system_prompt="你是一个小红书标题专家。标题要让人想点开。",
        user_prompt=f"""生3个小爆款标题，打分选最优。

评分维度:
- 吸引力 (0-40): 是否让用户想点击
- 真实性 (0-30): 是否与内容一致
- 关键词 (0-30): 是否包含搜索词

输出JSON:
{{"candidates": [
  {{"title": "...", "score": 0, "rationale": "..."}}
]}}

选题: {topic_title}
内容开头: {text[:300]}
""",
        temperature=0.7,
    )
    candidates = result.get("candidates", [])
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return (candidates[0]["title"], candidates) if candidates else (topic_title, [])


def main():
    topic, work_dir = _parse_args()
    print(f"[writer_xhs] Starting for: {topic.get('title', 'unknown')}")

    # Draft
    text = _draft(topic)
    print(f"[writer_xhs] Draft done: {len(text)} chars")

    # Titles
    final_title, candidates = _generate_titles(text, topic["title"])
    print(f"[writer_xhs] Title: {final_title}")

    # Carousel description (Phase 3: HTML template generation)
    carousel_images = []  # placeholder — Phase 3.2 adds Playwright screenshot

    # Write output
    article_path = work_dir / f"{RUN_TIMESTAMP}-{TYPE}.md"
    meta_path = work_dir / f"{RUN_TIMESTAMP}-{TYPE}.meta.json"

    article_path.write_text(f"# {final_title}\n\n{text}", encoding="utf-8")
    meta = {
        "topic": topic["title"],
        "platform_standard": TYPE,
        "word_count": len(text),
        "title_candidates": candidates,
        "title_score": candidates[0]["score"] if candidates else 0,
        "images": carousel_images,
        "status": "completed",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    print(f"[writer_xhs] Done → {article_path}")
    print(json.dumps({"article": str(article_path), "meta": str(meta_path)}))


if __name__ == "__main__":
    main()
