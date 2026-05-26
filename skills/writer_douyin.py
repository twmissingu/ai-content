"""Writer Worker — Douyin script standard (15-60s video script).

Phase 3: called by writer_router.py as a parallel Worker.
Outputs video script + scene descriptions for TTS + visual generation.
"""

import json
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
        system_prompt="你是一个短视频脚本专家。输出结构化脚本 JSON。",
        user_prompt=f"""为以下选题生成一个15-60秒的抖音短视频脚本。

选题: {topic['title']}
描述: {topic.get('description', '')}

输出JSON格式:
{{"hook": "前三秒抓眼球的一句话",
  "script": [
    {{"time_sec": 0, "text": "旁白文字", "visual": "画面描述", "duration": 5}}
  ],
  "cta": "结尾引导语",
  "hashtags": ["#tag1", "#tag2"],
  "total_duration_sec": 30
}}

要求:
- 语速快、节奏紧凑
- 前三秒必须抓眼球
- 核心观点 + 例证
- 结尾行动引导
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
    for scene in scenes:
        lines.append(f"**{scene.get('time_sec', 0)}s** ({scene.get('duration', 5)}s)")
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
