"""Writer Agent — 7-stage article production pipeline.

Phase 1: single Worker (wechat standard), sequential 7 stages.
Takes a confirmed topic from queue/pending/ or via CLI argument.
Outputs to queue/review/ with .md + .meta.json.
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import (
    ACTIONS_DIR,
    DOMAIN,
    KB_DIR,
    LENGTH,
    MAX_REWRITE_ROUNDS,
    PENDING_DIR,
    QUALITY_THRESHOLD,
    REVIEW_DIR,
    STAGE_TIMEOUT_MINUTES,
    STATUS_DIR,
    TONE,
    STANCE,
)
from skills.llm import chat, chat_structured, LLMError, set_current_agent

# Set current agent for token tracking
set_current_agent("writer")

# ── Constants ──────────────────────────────────────────────────────
STAGES = [
    (1, "抓原文", "fetch_source"),
    (2, "LLM初稿", "draft"),
    (3, "AI腔审校", "proofread"),
    (4, "批评修订", "critique"),
    (5, "排版", "format"),
    (6, "标题优化", "titles"),
    (7, "配图", "illustrate"),
]

TYPE = "wechat"  # Phase 1: single worker
RUN_TIMESTAMP = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


# ── Status ─────────────────────────────────────────────────────────
def _write_status(stage_num: int, stage_name: str, pct: int, detail: str,
                  error: Optional[str] = None):
    status = {
        "agent": "writer",
        "worker": TYPE,
        "stage": stage_num,
        "stage_name": stage_name,
        "progress_pct": pct,
        "detail": detail,
        "started_at": RUN_TIMESTAMP,
        "error": error,
    }
    path = STATUS_DIR / f"writer-worker-{TYPE}.json"
    tmp = STATUS_DIR / f".writer-worker-{TYPE}.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)


# ── Stage utilities ────────────────────────────────────────────────
def _read_topic(topic_id: Optional[str] = None) -> dict:
    """Read a topic from pending/ or from CLI arg."""
    if topic_id:
        path = PENDING_DIR / f"{topic_id}.json"
        if path.exists():
            return json.loads(path.read_text())
        # Maybe it's a topic_ prefix
        for f in PENDING_DIR.glob(f"topic_*{topic_id}*.json"):
            return json.loads(f.read_text())

    # Find the highest-scored unconfirmed topic
    files = sorted(PENDING_DIR.glob("topic_*.json"), key=os.path.getmtime, reverse=True)
    if not files:
        raise SystemExit("No topics found in queue/pending/")
    return json.loads(files[0].read_text())


def _read_article_for_rewrite(target_id: str) -> tuple[str, dict, str]:
    """Read the original article + meta + reject reason for rewrite mode.

    target_id format: {timestamp}-{type}  (e.g. "20260525_093000-wechat")
    Returns (article_content, meta_dict, reject_reason).
    """
    meta_path = REVIEW_DIR / f"{target_id}.meta.json"
    article_path = REVIEW_DIR / f"{target_id}.md"

    # Try alternate patterns
    if not meta_path.exists():
        for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
            meta_path = f
            article_path = REVIEW_DIR / f.stem.replace(".meta", "") + ".md"
            break

    if not meta_path.exists():
        print(f"[writer] Rewrite target not found: {target_id}")
        # Fall back to reading from pending/
        topic = _read_topic(target_id)
        return "", topic, ""

    meta = json.loads(meta_path.read_text())
    content = article_path.read_text(encoding="utf-8") if article_path.exists() else ""

    # Try to find the reject action for the reason
    reject_reason = ""
    for f in sorted(ACTIONS_DIR.glob(f"reject_*{target_id}*.json"),
                     key=os.path.getmtime, reverse=True):
        try:
            action_data = json.loads(f.read_text())
            reject_reason = action_data.get("reason", "") or ""
            if reject_reason:
                break
        except (json.JSONDecodeError, OSError):
            pass

    return content, meta, reject_reason


def _fetch_source(url: str) -> str:
    """Stage 1: Fetch source material from URL.

    Uses Firecrawl via Hermes MCP. Falls back to LLM summary if fetch fails.
    """
    if not url:
        return "无原文链接。将仅基于选题方向生成内容。"

    try:
        result = subprocess.run(
            ["hermes", "mcp", "call", "firecrawl_scrape",
             "--params", json.dumps({"url": url})],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout[:8000]  # limit size
    except Exception:
        pass

    # Fallback: ask LLM to summarize the topic instead
    return f"[原文抓取失败，将基于选题内容生成]"


# ── Stage 2: Draft ─────────────────────────────────────────────────
def _draft(topic: dict, source_material: str) -> str:
    """Generate first draft via LLM."""
    prompt = f"""你是一个观点鲜明的科技写手。请基于以下信息撰写一篇公众号文章。

选题: {topic['title']}
来源: {topic.get('description', '')}
素材: {source_material[:4000]}

写作要求:
- 领域: {DOMAIN}
- 语气: {TONE}
- 立场: {STANCE}
- 目标字数: {LENGTH} 字 (中文字符)
- 结构: 开头3秒抓人 → 层层递进论证 → 总结观点
- 每段不要太长，多分段

直接输出文章正文，不要额外解释，不要"以下是我为您撰写的文章"这类话开头。
"""
    return chat(
        system_prompt="你是一个高质量科技内容写手，文风犀利有观点。",
        user_prompt=prompt,
        temperature=0.8,
    )


# ── Stage 3: AI-slop proofread ─────────────────────────────────────
_AI_SLOP_PATTERNS = [
    (r"值得注意的是[，,]", 5),
    (r"在这个信息[爆炸|过载]的时代", 8),
    (r"正如我们[上文|前面|之前]所[提到|说过|论述]", 6),
    (r"让我们[来|一起]", 4),
    (r"首先[，,].*其次[，,].*最后[，,]", 5),
    (r"不可否认[，,]", 5),
    (r"从某种[角度|意义]上来说", 5),
    (r"我们需要[清醒地|理性地]认识到", 6),
    (r"毋庸置疑[，,]", 5),
    (r"引发了[广泛|热烈]的讨论", 5),
    (r"总的来说[，,]", 4),
    (r"综上所述[，,]", 4),
    (r"我们可以[看到|发现|得出]", 4),
    (r"不难看出[，,]", 4),
    (r"在[.*]的[背景|语境|框架]下", 4),
    (r"这[一|个]问题[值得|需要]我们[深入|认真][思考|探讨|关注]", 6),
    (r"毫无疑问[，,]", 5),
    (r"事实上[，,]", 3),
    (r"某种意义上[，,]", 3),
    (r"不得不说[，,]", 4),
    (r"有待[.*]进一步[.*]", 4),
    (r"值得[我们][深入|认真]思考", 5),
    (r"我们[有理由|可以]相信[，,]", 5),
]


def _proofread(text: str) -> tuple[str, int]:
    """Stage 3: Remove AI-slop patterns and score.

    Returns (cleaned_text, proofread_score).
    Score: regex score × 0.4 + LLM score × 0.6
    """
    # Regex pass
    issues_found = 0
    cleaned = text
    for pattern, severity in _AI_SLOP_PATTERNS:
        matches = re.findall(pattern, cleaned)
        if matches:
            issues_found += len(matches) * severity
            cleaned = re.sub(pattern, "", cleaned)

    # Normalize regex score to 0-100
    regex_score = max(0, 100 - issues_found)

    # LLM pass
    llm_result = chat_structured(
        system_prompt="你是一个AI写作腔调检测专家。检测文本中的AI痕迹，返回0-100的分数和问题列表。",
        user_prompt=f"""请检测以下文章中"AI腔"的严重程度。

评分规则:
- 90-100: 几乎没有AI痕迹，自然口语化
- 70-89: 少量AI句式，可接受
- 50-69: 明显AI腔，需要修改
- 0-49: 严重AI腔，基本不可用

输出JSON:
{{"score": 0, "issues": ["问题1", "问题2"], "suggestion": "改进建议"}}

文章:
{cleaned[:3000]}
""",
        temperature=0.3,
    )
    llm_score = int(llm_result.get("score", 70))

    # Combined score
    final_score = int(regex_score * 0.4 + llm_score * 0.6)

    if final_score < QUALITY_THRESHOLD:
        # If below threshold, apply LLM suggestions and re-check
        suggestion = llm_result.get("suggestion", "")
        if suggestion:
            cleaned = chat(
                system_prompt="你是一个文字编辑。请重写以下段落，去掉AI写作腔调，使其更自然口语化。",
                user_prompt=f"请重写这段文字，更自然、更像真人写的:\n\n{cleaned[:3000]}\n\n建议: {suggestion}",
                temperature=0.7,
            )

    return cleaned, final_score


# ── Stage 4: Critique & rewrite ────────────────────────────────────
def _critique(text: str, topic_title: str, round_num: int) -> tuple[str, int, bool]:
    """Stage 4: Critic LLM scores the article. If < threshold, rewrite.

    Returns (text, score, passed).
    """
    result = chat_structured(
        system_prompt="你是一个严格的写作评委。请从论点、论据、结构、文笔四个维度评分。",
        user_prompt=f"""请评分以下文章（选题: {topic_title}）。

输出JSON格式:
{{"score": 0, "weakness": "主要弱点", "suggestions": ["改进1", "改进2"]}}

评分维度:
- 论点是否鲜明 (0-25)
- 论据是否充分 (0-25)
- 结构是否合理 (0-25)
- 文笔是否有观点 (0-25)

文章:
{text[:4000]}
""",
        temperature=0.4,
    )
    score = int(result.get("score", 50))

    if score >= QUALITY_THRESHOLD or round_num >= MAX_REWRITE_ROUNDS:
        return text, score, score >= QUALITY_THRESHOLD

    # Rewrite
    suggestions = result.get("suggestions", [])
    weakness = result.get("weakness", "")
    improvement = "\n".join(f"- {s}" for s in suggestions)
    prompt = f"""你是一个高质量写手。请根据评委反馈重写这篇文章，解决以下问题。

评委评分: {score}/100
主要弱点: {weakness}
改进建议:
{improvement}

原文:
{text}

请直接输出重写后的完整文章，不要额外解释。
"""
    text = chat(
        system_prompt="你是一个精益求精的写手，能够根据反馈大幅提升文章质量。",
        user_prompt=prompt,
        temperature=0.8,
    )
    return text, score, False  # not passed yet


# ── Stage 5: Formatting ────────────────────────────────────────────
def _format(text: str) -> str:
    """Stage 5: Formatting — spaces, paragraphs, hashtags."""
    # Chinese-English spacing
    text = re.sub(r'([\u4e00-\u9fff])([a-zA-Z0-9])', r'\1 \2', text)
    text = re.sub(r'([a-zA-Z0-9])([\u4e00-\u9fff])', r'\1 \2', text)
    # Remove extra spaces
    text = re.sub(r'  +', ' ', text)
    # Normalize paragraph breaks
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Add hashtags at end
    hashtags = "\n\n#AI #科技 #人工智能 #观点"
    if DOMAIN == "科技/AI":
        text += hashtags
    return text.strip()


# ── Stage 6: Title optimization ────────────────────────────────────
def _generate_titles(text: str, topic_title: str) -> tuple[str, list[dict]]:
    """Stage 6: Generate 3 candidate titles, score each, pick best."""
    result = chat_structured(
        system_prompt="你是一个标题优化专家。生成有吸引力但不标题党的标题。",
        user_prompt=f"""根据以下文章生成3个公众号标题，并为每个打分。

评分维度 (各25分):
- 吸引力: 是否让读者想点开
- 准确性: 是否准确反映内容
- 独创性: 是否标题党
- 关键词: 是否包含关键搜索词

输出JSON:
{{"candidates": [
  {{"title": "标题1", "score": 0, "rationale": "理由"}},
  {{"title": "标题2", "score": 0, "rationale": "理由"}},
  {{"title": "标题3", "score": 0, "rationale": "理由"}}
]}}

选题: {topic_title}
文章开头: {text[:500]}
""",
        temperature=0.7,
    )
    candidates = result.get("candidates", [])
    if not candidates:
        return topic_title, []

    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
    return candidates[0]["title"], candidates


# ── Stage 7: Illustrations ─────────────────────────────────────────
def _illustrate(text: str, topic_title: str) -> list[str]:
    """Stage 7: Generate illustrations.

    Phase 1: HTML templates only.
    Phase 3.2: HTML → PNG via Playwright screenshot.
    Falls back to HTML-only if Playwright unavailable.
    Returns list of file paths (PNG preferred, HTML fallback).
    """
    images: list[str] = []
    img_dir = Path("queue/images") / RUN_TIMESTAMP
    img_dir.mkdir(parents=True, exist_ok=True)

    # Check if Playwright screenshot is available
    _can_screenshot = False
    try:
        from playwright.sync_api import sync_playwright
        _can_screenshot = True
    except ImportError:
        pass

    paragraphs = [p for p in text.split("\n\n") if len(p) > 50]
    sections_to_illustrate = paragraphs[:3]

    for i, section in enumerate(sections_to_illustrate):
        section_title = section[:60].replace("\n", " ")
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><style>
body {{ font-family: -apple-system, sans-serif; background: #f8f9fa;
       display: flex; justify-content: center; align-items: center;
       min-height: 400px; margin: 0; padding: 20px; }}
.card {{ background: white; border-radius: 16px; padding: 32px;
        max-width: 580px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
.label {{ color: #666; font-size: 12px; letter-spacing: 0.5px;
         text-transform: uppercase; margin-bottom: 8px; }}
h2 {{ font-size: 20px; line-height: 1.5; color: #111; margin: 0 0 12px 0; }}
p {{ font-size: 15px; line-height: 1.7; color: #333; margin: 0; }}
.divider {{ height: 1px; background: #eee; margin: 16px 0; }}
.tag {{ display: inline-block; background: #e8f4fd; color: #1a73e8;
        padding: 4px 12px; border-radius: 20px; font-size: 12px; }}
</style></head><body>
<div class="card">
  <div class="label">稿定 · AI 观点</div>
  <h2>{topic_title}</h2>
  <div class="divider"></div>
  <p>{section_title[:200]}</p>
  <div class="divider"></div>
  <span class="tag">{DOMAIN}</span>
</div></body></html>"""
        html_path = img_dir / f"illustration_{i + 1}.html"
        html_path.write_text(html, encoding="utf-8")

        # Try screenshot if Playwright available
        if _can_screenshot:
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(
                        viewport={"width": 580, "height": 440},
                        device_scale_factor=2,
                    )
                    page.goto(f"file://{html_path.resolve()}")
                    page.wait_for_load_state("networkidle")
                    png_path = html_path.with_suffix(".png")
                    page.screenshot(path=str(png_path))
                    browser.close()
                    images.append(str(png_path))
                    print(f"[writer] Screenshot: {png_path}")
            except Exception as e:
                print(f"[writer] Screenshot failed for {html_path.name}: {e}")
                images.append(str(html_path))
        else:
            images.append(str(html_path))

    return images


# ── Main pipeline ──────────────────────────────────────────────────
def main():
    # Support --topic-file for router compatibility
    topic_file_arg = None
    work_dir_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == "--topic-file" and i + 1 < len(sys.argv):
            topic_file_arg = Path(sys.argv[i + 1])
        elif arg == "--work-dir" and i + 1 < len(sys.argv):
            work_dir_arg = Path(sys.argv[i + 1])

    topic_id = sys.argv[1] if len(sys.argv) > 1 else None
    rewrite_mode = "--rewrite" in sys.argv
    rewrite_target = topic_id if rewrite_mode else None

    # If topic_file_arg given, use that instead of scanning pending/
    _topic_from_file = None
    if topic_file_arg and topic_file_arg.exists():
        _topic_from_file = json.loads(topic_file_arg.read_text())

    # ── Mode: Rewrite ──────────────────────────────────────────────
    if rewrite_mode and rewrite_target:
        print(f"[writer] Rewrite mode: {rewrite_target}")
        _write_status(0, "初始化", 0, f"重写模式: {rewrite_target}")
        original_text, topic, reject_reason = _read_article_for_rewrite(rewrite_target)
        if reject_reason:
            print(f"[writer] Reject reason: {reject_reason}")
            topic["reject_reason"] = reject_reason

        # Use the original topic title + reject reason as prompt context
        # topic dict from meta has "topic" key; from pending/ fallback has "title"
        topic_title = topic.get("topic") or topic.get("title", rewrite_target)
        source_url = topic.get("source_url", topic.get("url", ""))
        source_material = original_text

        _write_status(1, "抓原文", 5, "读取原文素材")
        if source_url and not original_text:
            source_material = _fetch_source(source_url)
        else:
            source_material = original_text or "无原文素材"

        # Stage 2: Rewrite with feedback
        _write_status(2, "LLM初稿", 20, "根据反馈重写")
        prompt_extra = ""
        if reject_reason:
            prompt_extra = f"\n\n驳回原因（必须针对性改进）: {reject_reason}"
        text = _draft(
            {"title": topic_title, "description": topic.get("topic", "") + prompt_extra},
            source_material,
        )

    # ── Mode: Normal from topic ────────────────────────────────────
    else:
        _write_status(0, "初始化", 0, "读取选题配置")
        topic = _topic_from_file if _topic_from_file else _read_topic(topic_id)
        print(f"[writer] Starting pipeline for: {topic['title']}")
        source_material = ""
        source_url = topic.get("url", "")

        _write_status(1, "抓原文", 5, "抓取原文素材")
        if source_url:
            source_material = _fetch_source(source_url)
        else:
            source_material = "无原文链接。将基于选题方向生成。"
        print(f"[writer] Stage 1 done. Source: {len(source_material)} chars")

        _write_status(2, "LLM初稿", 20, "生成初稿")
        text = _draft(topic, source_material)
        print(f"[writer] Stage 2 done. Draft: {len(text)} chars")

    # Stage 3: Proofread
    _write_status(3, "AI腔审校", 35, "检测并移除AI腔")
    text, proofread_score = _proofread(text)
    print(f"[writer] Stage 3 done. Proofread score: {proofread_score}")

    # Stage 4: Critique & rewrite loop
    _write_status(4, "批评修订", 50, "评委评分中")
    critique_scores: list[int] = []
    for round_num in range(1, MAX_REWRITE_ROUNDS + 1):
        text, score, passed = _critique(text, topic["title"], round_num)
        critique_scores.append(score)
        _write_status(4, "批评修订", 50 + round_num * 10,
                      f"第{round_num}轮: 评分{score}")
        print(f"[writer] Stage 4 round {round_num}: score={score}, passed={passed}")
        if passed:
            break
        if round_num < MAX_REWRITE_ROUNDS:
            _write_status(4, "批评修订", 50 + round_num * 10,
                          f"第{round_num}轮未通过，开始第{round_num + 1}轮")

    # Stage 5: Format
    _write_status(5, "排版", 75, "格式化排版")
    text = _format(text)
    print(f"[writer] Stage 5 done. Formatted.")

    # Stage 6: Titles
    _write_status(6, "标题优化", 85, "生成候选标题")
    final_title, title_candidates = _generate_titles(text, topic["title"])
    title_score = title_candidates[0]["score"] if title_candidates else 0
    print(f"[writer] Stage 6 done. Best title: {final_title}")

    # Stage 7: Illustrations
    _write_status(7, "配图", 92, "生成配图")
    images = _illustrate(text, topic["title"])
    print(f"[writer] Stage 7 done. Images: {len(images)}")

    # Write output
    _write_status(7, "完成", 95, "写入输出文件")
    article_path = REVIEW_DIR / f"{RUN_TIMESTAMP}-{TYPE}.md"
    meta_path = REVIEW_DIR / f"{RUN_TIMESTAMP}-{TYPE}.meta.json"

    article_path.write_text(f"# {final_title}\n\n{text}", encoding="utf-8")

    meta = {
        "topic": topic["title"],
        "source_url": source_url,
        "platform_standard": TYPE,
        "proofread_score": proofread_score,
        "critique_scores": critique_scores,
        "revised_rounds": len(critique_scores),
        "title_score": title_score,
        "title_candidates": title_candidates,
        "word_count": len(text),
        "ai_slop_issues": 100 - proofread_score,
        "images": images,
        "writing_style": f"{TYPE}_default",
        "image_generation_method": "html_template" if images else "none",
        "status": "completed",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    # Final status
    _write_status(7, "完成", 100, "管线完成")
    status = {
        "agent": "writer",
        "worker": TYPE,
        "stage": 7,
        "stage_name": "完成",
        "progress_pct": 100,
        "detail": f"管线完成 · 评分{proofread_score}/{critique_scores[-1] if critique_scores else 0}",
        "started_at": RUN_TIMESTAMP,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "article": str(article_path),
        "meta": str(meta_path),
        "error": None,
    }
    path = STATUS_DIR / f"writer-worker-{TYPE}.json"
    tmp = STATUS_DIR / f".writer-worker-{TYPE}.json.tmp"
    tmp.write_text(json.dumps(status, ensure_ascii=False, indent=2))
    os.rename(tmp, path)

    print(f"[writer] Pipeline complete!")
    print(f"[writer] Article: {article_path}")
    print(f"[writer] Meta: {meta_path}")
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
