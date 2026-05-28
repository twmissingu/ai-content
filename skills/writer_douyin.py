"""Writer Worker — Douyin script standard (15-60s video script).

Phase 3: called by writer_router.py as a parallel Worker.
Outputs video script + scene descriptions for TTS + visual generation.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import DOMAIN
from skills.llm import chat, chat_structured

from datetime import datetime, timezone

RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
TYPE = "douyin"


def _parse_args() -> tuple[dict, Path]:
    topic_file = work_dir = None
    for i, arg in enumerate(sys.argv):
        if arg == "--topic-file" and i + 1 < len(sys.argv):
            topic_file = Path(sys.argv[i + 1])
        elif arg == "--work-dir" and i + 1 < len(sys.argv):
            work_dir = Path(sys.argv[i + 1])
    if not topic_file or not work_dir:
        from config.settings import PENDING_DIR
        files = sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True)
        if not files:
            raise SystemExit("No topic file found")
        topic_file = files[0]
        work_dir = Path("queue/tmp") / RUN_TIMESTAMP
        work_dir.mkdir(parents=True, exist_ok=True)
    return json.loads(topic_file.read_text()), work_dir


def _generate_script(topic: dict) -> dict:
    """Generate a Douyin short video script with scene descriptions."""
    result = chat_structured(
        system_prompt=f"你是一个抖音爆款短视频脚本专家，专注{DOMAIN}领域。你擅长用15-60秒讲清楚一个观点并引导互动。你的脚本节奏快、信息密度高、口语化强。",
        user_prompt=f"""为以下选题生成一个抖音短视频脚本。

选题: {topic['title']}
描述: {topic.get('description', '')}

## 脚本结构（严格按时长分配）

### 1. Hook (0-3秒) — 生死3秒，必须抓人
好的Hook示例:
- 数据冲击: "90%的人不知道，你的手机每天在偷看你"
- 反问悬念: "为什么苹果从不打价格战？"
- 反常识: "学编程最不该先学语法"
- 冲突对立: "程序员说这不可能，产品经理说今天必须上线"
禁止: "你知道吗""大家好""今天我来分享""最近很多人问"

### 2. 正文 (3-25秒) — 核心内容，一句一个信息点
- 每句话≤15字（口语化，像说话不像念稿）
- 一句一个信息点，不要一句话塞两个观点
- 节奏紧凑，句与句之间不要停顿太久
- 每句话都要配合画面描述（特写/全景/文字特效/数据图表）

### 3. CTA (最后5秒) — 引导互动
- 引导点赞/评论/关注（自然融入，不要硬求）
- 留一个开放性问题引发讨论
- 好例子: "你觉得AI会取代程序员吗？评论区告诉我"

## 输出JSON格式:
{{
  "hook": "前三秒抓眼球的一句话（≤20字）",
  "script": [
    {{"time_sec": 0, "text": "旁白文字（≤15字/句）", "visual": "具体画面描述", "duration": 5, "mood": "语气/情绪"}},
    {{"time_sec": 5, "text": "...", "visual": "...", "duration": 5, "mood": "..."}}
  ],
  "cta": "结尾引导语（≤25字）",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "total_duration_sec": 30,
  "target_audience": "目标受众画像（年龄+身份+兴趣）"
}}

## 技术约束
- 总时长: 15-60秒（推荐25-35秒）
- 语速: 3-4字/秒
- 每个scene的duration: 3-8秒
- 总scene数: 4-8个
"""
    )
    return result


def main():
    topic, work_dir = _parse_args()
    print(f"[writer_douyin] Starting for: {topic.get('title', 'unknown')}")

    script = _generate_script(topic)
    scenes = script.get("script", [])
    print(f"[writer_douyin] Script generated: {len(scenes)} scenes, ~{script.get('total_duration_sec', 0)}s")

    # Write output
    article_path = work_dir / f"{RUN_TIMESTAMP}-{TYPE}.md"
    meta_path = work_dir / f"{RUN_TIMESTAMP}-{TYPE}.meta.json"

    # Format as markdown
    lines = [f"# {script.get('hook', topic['title'])}", ""]
    lines.append(f"**总时长**: {script.get('total_duration_sec', 0)}秒 | **目标受众**: {script.get('target_audience', '科技爱好者')}", )
    lines.append("")
    for scene in scenes:
        lines.append(f"**{scene.get('time_sec', 0)}s** ({scene.get('duration', 5)}s) — {scene.get('mood', '')}")
        lines.append(f"🎤 {scene.get('text', '')}")
        lines.append(f"🎬 {scene.get('visual', '')}")
        lines.append("")

    lines.append("---")
    lines.append(f"**CTA**: {script.get('cta', '')}")
    lines.append(" ".join(script.get("hashtags", [])))

    article_path.write_text("\n".join(lines), encoding="utf-8")

    meta = {
        "topic": topic["title"],
        "platform_standard": TYPE,
        "hook": script.get("hook", ""),
        "total_duration_sec": script.get("total_duration_sec", 0),
        "scene_count": len(scenes),
        "hashtags": script.get("hashtags", []),
        "status": "completed",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    print(f"[writer_douyin] Done → {article_path}")
    print(json.dumps({"article": str(article_path), "meta": str(meta_path)}))


if __name__ == "__main__":
    main()
