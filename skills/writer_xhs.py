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
    prompt = f"""你是一个小红书爆款笔记创作者，专注{DOMAIN}领域。你的笔记特点是：真实感强、干货密度高、互动率高。

选题: {topic['title']}
描述: {topic.get('description', '')}

## 结构模板（严格按此输出）

1. **开头 (1-2句)** — 用以下任一方式切入:
   - 痛点切入: "找了3天都没找到靠谱的XX，最后自己摸索出来了"
   - 数据冲击: "试了10个工具，只有这2个真正好用"
   - 反差开头: "以为XX很难，结果10分钟就搞定了"
   - 禁止: "家人们""姐妹们""宝子们""今天给大家分享"

2. **主体 (3-5段)** — 每段一个干货点:
   - 每段2-3句，开头用 emoji 标记
   - 第一段: 最核心的点（直接给结论）
   - 中间段: 具体方法/步骤/对比
   - 最后段: 避坑提醒或进阶技巧

3. **结尾 (1-2句)** — 互动引导:
   - 提问式: "你们还有什么好用的XX推荐吗？"
   - 投票式: "你们觉得A好还是B好？"
   - 征集式: "评论区告诉我你们最想看什么"

## 风格硬性要求
- 字数: 300-800 字
- 语气: 像朋友聊天，轻松口语化，可以带"哈哈""真的""绝了"
- 立场: 第一人称真实经验分享（"我试了""我发现""我的建议"）
- emoji: 每段1-2个，放在段首或句中，不要连续堆砌
- 分段: 每段2-3句，段间留空行增加可读性

## 禁忌
- 禁止泛滥开头: "家人们""姐妹们""宝子们""今天给大家分享""给大家安利"
- 禁止营销感: "强烈推荐""必买""不买后悔"
- 禁止大段堆砌: 一段超过4句
- 禁止AI腔: "值得注意的是""综上所述""不可否认"

## 结尾格式
最后一行附上 3-5 个相关 hashtag（#话题标签），用空格分隔

直接输出笔记正文，不要额外说明。
"""
    return chat(
        system_prompt=f"你是一个小红书爆款笔记创作者，专注{DOMAIN}领域。你写的笔记真实感强、干货密度高、互动率高。你从不用'家人们''姐妹们'开头，也不写营销软文。",
        user_prompt=prompt,
        temperature=0.8,
    )


def _generate_titles(text: str, topic_title: str) -> tuple[str, list[dict]]:
    """Generate attention-grabbing Xiaohongshu titles."""
    result = chat_structured(
        system_prompt=f"你是一个小红书标题专家，精通平台算法和用户心理，专注{DOMAIN}领域。你生成的标题能精准命中用户好奇心，同时不做标题党。",
        user_prompt=f"""生成3个小红书爆款标题，每个用不同的公式，打分选最优。

## 标题公式（每个标题用一种）
1. 数字型: "X个/X招/X天" — 给人确定感，如"3个免费AI工具，效率翻倍"
2. 提问型: "为什么...？""...到底怎么选？" — 引发好奇，如"为什么大厂都在用这个框架？"
3. 反差型: "别再X了""从X到Y""X vs Y" — 制造冲突，如"别再用XX了，这个替代品更强"
4. 身份型: "打工人/学生党/程序员" — 精准人群，如"程序员必看的5个效率工具"
5. 情绪型: "绝了！""后悔没早知道""救命" — 情绪共鸣，如"后悔没早知道！这个工具太香了"

## 评分维度（严格打分）
- 吸引力 (0-40): 是否让用户想点击？是否制造了信息差/好奇心？
- 真实性 (0-30): 是否与内容一致？标题党会降低信任和推荐权重
- SEO (0-30): 是否包含搜索关键词？是否利于平台推荐和搜索流量？

## 输出JSON:
{{"candidates": [
  {{"title": "完整标题（15-25字最佳）", "score": 82, "rationale": "推荐理由", "formula": "数字型"}},
  {{"title": "完整标题（15-25字最佳）", "score": 75, "rationale": "推荐理由", "formula": "提问型"}},
  {{"title": "完整标题（15-25字最佳）", "score": 68, "rationale": "推荐理由", "formula": "反差型"}}
]}}

## 选题信息
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
