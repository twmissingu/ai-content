"""Writer Agent — 7-stage article production pipeline.

Phase 1: single Worker (wechat standard), sequential 7 stages.
Takes a confirmed topic from queue/pending/ or via CLI argument.
Outputs to queue/review/ with .md + .meta.json.

Uses AgentBase for unified status writing, logging, and metrics.
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
    IMAGES_DIR,
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
from skills.common import AgentBase, agent_main
from skills.llm import chat, chat_structured, LLMError

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


# ── Writer Agent ───────────────────────────────────────────────────
class WriterAgent(AgentBase):
    """Writer agent with 7-stage pipeline."""
    
    name = "writer"
    version = "1.0.0"
    
    def __init__(self, worker_type: str = "wechat"):
        super().__init__(enable_metrics=True)
        self.worker_type = worker_type
        self._status_path = STATUS_DIR / f"writer-worker-{worker_type}.json"
        self._run_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    def write_status(self, stage: str, progress_pct: int, detail: str,
                     error: Optional[str] = None, **extra) -> None:
        """Override to include worker type in status."""
        super().write_status(
            stage=stage,
            progress_pct=progress_pct,
            detail=detail,
            error=error,
            worker=self.worker_type,
            **extra
        )
    
    # ── Stage utilities ────────────────────────────────────────────
    def _read_topic(self, topic_id: Optional[str] = None) -> dict:
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

    def _read_article_for_rewrite(self, target_id: str) -> tuple[str, dict, str]:
        """Read the original article + meta + reject reason for rewrite mode."""
        meta_path = REVIEW_DIR / f"{target_id}.meta.json"
        article_path = REVIEW_DIR / f"{target_id}.md"

        # Try alternate patterns
        if not meta_path.exists():
            for f in REVIEW_DIR.glob(f"*{target_id}*.meta.json"):
                meta_path = f
                article_path = REVIEW_DIR / f.stem.replace(".meta", "") + ".md"
                break

        if not meta_path.exists():
            self.logger.warning(f"Rewrite target not found: {target_id}")
            topic = self._read_topic(target_id)
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

    def _fetch_source(self, url: str) -> str:
        """Stage 1: Fetch source material from URL."""
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
        except Exception as e:
            self.logger.warning(f"Failed to fetch source: {e}")

        return "[原文抓取失败，将基于选题内容生成]"

    def _sanitize_text(self, text: str, max_length: int = 500) -> str:
        """Sanitize text to prevent prompt injection."""
        if not text:
            return ""
        # Remove common injection patterns
        import re
        # Remove markdown code blocks that might contain instructions
        text = re.sub(r'```[\s\S]*?```', '', text)
        # Remove system/instruction-like patterns
        text = re.sub(r'(?i)(ignore|forget|disregard)\s+(previous|above|all)\s+(instructions?|prompts?|rules?)', '', text)
        # Remove role-play injection attempts
        text = re.sub(r'(?i)you\s+are\s+now\s+', '', text)
        # Limit length
        return text[:max_length].strip()

    def _draft(self, topic: dict, source_material: str) -> str:
        """Stage 2: Generate first draft via LLM."""
        # Sanitize inputs to prevent prompt injection
        safe_title = self._sanitize_text(topic['title'], max_length=200)
        safe_description = self._sanitize_text(topic.get('description', ''), max_length=500)
        safe_material = self._sanitize_text(source_material, max_length=4000)

        prompt = f"""你是一个观点鲜明的科技写手，擅长用通俗易懂的语言解释复杂概念。你的文章有明确立场，不写废话。

选题: {safe_title}
背景: {safe_description}
素材: {safe_material}

写作要求:
- 领域: {DOMAIN}
- 语气: {TONE}
- 立场: {STANCE}
- 目标字数: {LENGTH} 字 (中文字符)

结构模板（严格按此结构输出）:
1. 【开头】用一个具体场景、数据或问题抓住读者注意力（3秒法则）
   - 好例子: "上周，一个只有3人的团队用AI工具做到了传统团队10人的产出。"
   - 差例子: "在当今数字化转型的浪潮中..."
2. 【正文】3-5个段落，每段一个核心论点，用案例或数据支撑
   - 每段以一个明确的论点句开头
   - 用具体案例、数据或类比支撑
   - 段落之间有逻辑递进关系
3. 【结尾】给出明确观点或行动建议，不要空泛总结
   - 好例子: "如果你还在犹豫是否该用AI辅助写作，我的建议是：先从标题生成开始，3天就能看到效果。"
   - 差例子: "综上所述，AI的发展值得我们关注。"

风格硬性要求:
- 每段3-5句，多分段提高可读性
- 用具体数字代替模糊描述（"提升了30%"而非"大幅提升"）
- 用类比解释技术概念（"就像..."）
- 禁止使用: "值得注意的是""不可否认""毋庸置疑""综上所述""总的来说""在这个...的时代""引发了广泛讨论"
- 可以适当使用反问、设问增加互动感
- 第一人称叙述，像在和朋友聊天

直接输出文章正文。不要"以下是我撰写的文章"这类话开头，直接进入主题。
"""
        start_time = time.monotonic()
        result = chat(
            system_prompt="你是一个高质量科技内容写手，文风犀利有观点。你的文章读起来像真人写的博客，不像AI生成的内容。禁止使用'值得注意的是''不可否认''毋庸置疑'等AI腔。",
            user_prompt=prompt,
            temperature=0.8,
        )
        duration = time.monotonic() - start_time
        self.record_llm_call(duration=duration, success=True)
        return result

    # ── Stage 3: AI-slop proofread ─────────────────────────────────
    _AI_SLOP_PATTERNS = [
        (r"值得注意的是[，,]", 5),
        (r"在这个信息(爆炸|过载)的时代", 8),
        (r"正如我们(上文|前面|之前)所(提到|说过|论述)", 6),
        (r"让我们(来|一起)", 4),
        (r"首先[，,].*其次[，,].*最后[，,]", 5),
        (r"不可否认[，,]", 5),
        (r"从某种(角度|意义)上来说", 5),
        (r"我们需要(清醒地|理性地)认识到", 6),
        (r"毋庸置疑[，,]", 5),
        (r"引发了(广泛|热烈)的讨论", 5),
        (r"总的来说[，,]", 4),
        (r"综上所述[，,]", 4),
        (r"我们可以(看到|发现|得出)", 4),
        (r"不难看出[，,]", 4),
        (r"在.*的(背景|语境|框架)下", 4),
        (r"这(一|个)问题(值得|需要)我们(深入|认真)(思考|探讨|关注)", 6),
        (r"毫无疑问[，,]", 5),
        (r"事实上[，,]", 3),
        (r"某种意义上[，,]", 3),
        (r"不得不说[，,]", 4),
        (r"有待.*进一步.*", 4),
        (r"值得我们(深入|认真)思考", 5),
        (r"我们(有理由|可以)相信[，,]", 5),
    ]

    def _proofread(self, text: str) -> tuple[str, int]:
        """Stage 3: Remove AI-slop patterns and score."""
        self.start_stage("proofread")

        # Regex pass
        issues_found = 0
        cleaned = text
        for pattern, severity in self._AI_SLOP_PATTERNS:
            matches = re.findall(pattern, cleaned)
            if matches:
                issues_found += len(matches) * severity
                cleaned = re.sub(pattern, "", cleaned)

        # Normalize regex score to 0-100
        regex_score = max(0, 100 - issues_found)

        # LLM pass
        start_time = time.monotonic()
        llm_result = chat_structured(
            system_prompt="你是一个专业的文字编辑，擅长识别AI生成内容的痕迹并使其更自然。你对AI腔零容忍。",
            user_prompt=f"""请检测以下文章中"AI腔"的严重程度，并给出具体修改建议。

AI腔检测清单（逐项检查）:
1. 过渡词滥用: "值得注意的是""不可否认""毋庸置疑""事实上""不得不说"
2. 空泛总结: "综上所述""总的来说""由此可见""不难看出"
3. 套话开头: "在这个信息爆炸的时代""随着...的发展""在...的背景下"
4. 机械结构: "首先...其次...最后..."的三段论
5. 缺乏具体数据: 用"大幅提升""显著改善"代替具体百分比
6. 情感平淡: 没有个人观点、反问、感叹等情感表达
7. 万能句式: "这值得我们深思""引发了广泛讨论""有待进一步研究"

评分标准（严格打分，不要给虚高分数）:
- 90-100: 完全自然，像真人写的博客/公众号，无AI痕迹
- 70-89: 有少量AI痕迹，但不影响阅读体验
- 50-69: 明显AI腔，需要润色修改
- 0-49: 严重AI腔，需要重写

输出JSON:
{{"score": 65, "issues": ["问题1: 原文'...'过于套话", "问题2: 第X段缺乏数据支撑"], "suggestion": "具体改进建议: 第X段改为...，第Y段加入...数据"}}

文章:
{cleaned[:3000]}
""",
            temperature=0.3,
        )
        duration = time.monotonic() - start_time
        self.record_llm_call(duration=duration, success=True)
        
        llm_score = int(llm_result.get("score", 70))

        # Combined score
        final_score = int(regex_score * 0.4 + llm_score * 0.6)

        if final_score < QUALITY_THRESHOLD:
            # If below threshold, apply LLM suggestions and re-check
            suggestion = llm_result.get("suggestion", "")
            if suggestion:
                start_time = time.monotonic()
                cleaned = chat(
                    system_prompt="你是一个文字编辑。请重写以下段落，去掉AI写作腔调，使其更自然口语化。",
                    user_prompt=f"请重写这段文字，更自然、更像真人写的:\n\n{cleaned[:3000]}\n\n建议: {suggestion}",
                    temperature=0.7,
                )
                duration = time.monotonic() - start_time
                self.record_llm_call(duration=duration, success=True)

        self.end_stage("proofread")
        return cleaned, final_score

    # ── Stage 4: Critique & rewrite (multi-perspective editorial board) ──
    def _critique(self, text: str, topic_title: str, round_num: int) -> tuple[str, int, bool]:
        """Stage 4: Multi-perspective editorial board review.

        Inspired by FLUX's 3-model editorial board pattern:
        - Perspective 1 (Scorer): Strict scoring on rubric
        - Perspective 2 (Critic): Devil's advocate, finds weaknesses
        Final score = weighted average of both perspectives.
        """
        # ── Perspective 1: Strict Scorer ──
        start_time = time.monotonic()
        scorer_result = chat_structured(
            system_prompt="你是一个严格但建设性的写作评委。你给分很吝啬——好文章才给80+，平庸的文章给60以下。你从不给'还行'的文章高分。",
            user_prompt=f"""请严格评价以下文章（选题: {topic_title}）。

评分维度（各25分，满分100，每个维度独立打分后求和）:

1. 论点鲜明度 (0-25):
   - 25: 观点犀利独特，让人眼前一亮，有明确立场
   - 20: 观点清晰，有一定新意
   - 15: 观点明确但缺乏新意，人云亦云
   - 10以下: 观点模糊、没有立场、两边讨好

2. 论据充分度 (0-25):
   - 25: 有具体数据、真实案例、完整逻辑链
   - 20: 有具体支撑，偶有薄弱环节
   - 15: 论据不足，说服力一般
   - 10以下: 空泛论述，缺乏任何具体支撑

3. 结构合理性 (0-25):
   - 25: 起承转合流畅，节奏感好，段落间有逻辑递进
   - 20: 结构清晰，偶有跳跃
   - 15: 结构松散但可读
   - 10以下: 逻辑混乱，段落间无关联

4. 文笔观点性 (0-25):
   - 25: 文风鲜明有记忆点，像真人写的博客
   - 20: 表达流畅，有个人风格
   - 15: 中规中矩，无功无过
   - 10以下: 生硬AI腔、套话连篇、读起来像机器生成

请输出 JSON:
{{"score": 62, "weakness": "最主要的一个问题（必须具体引用原文句子）", "suggestions": ["改进1: 具体说明要改哪里、改成什么", "改进2: 具体说明要改哪里、改成什么"]}}

文章:
{text[:4000]}
""",
            temperature=0.4,
        )
        scorer_duration = time.monotonic() - start_time
        self.record_llm_call(duration=scorer_duration, success=True)

        scorer_score = int(scorer_result.get("score", 50))
        scorer_weakness = scorer_result.get("weakness", "")
        scorer_suggestions = scorer_result.get("suggestions", [])

        # ── Perspective 2: Devil's Advocate (finds weaknesses) ──
        start_time = time.monotonic()
        critic_result = chat_structured(
            system_prompt="你是一个挑剔的读者和内容批评家。你的工作是找出文章中所有问题：逻辑漏洞、论据不足、表述模糊、读者可能的质疑。你只关注问题，不夸优点。",
            user_prompt=f"""请以挑剔读者的视角，找出以下文章的所有问题（选题: {topic_title}）。

重点关注:
1. 逻辑漏洞: 论证是否有跳跃或矛盾？
2. 论据质疑: 数据来源是否可靠？案例是否有代表性？
3. 读者困惑: 哪些地方读者会看不懂或产生歧义？
4. 遗漏: 文章没提到但读者会关心的重要方面
5. 可信度: 哪些表述会让读者怀疑作者的专业性？

请输出 JSON:
{{"critique_score": 55, "issues": ["问题1: 具体说明", "问题2: 具体说明"], "missing": "文章遗漏的关键点"}}

文章:
{text[:4000]}
""",
            temperature=0.6,
        )
        critic_duration = time.monotonic() - start_time
        self.record_llm_call(duration=critic_duration, success=True)

        critic_score = int(critic_result.get("critique_score", 50))
        critic_issues = critic_result.get("issues", [])
        critic_missing = critic_result.get("missing", "")

        # ── Combine scores (scorer 70% + critic 30%) ──
        score = int(scorer_score * 0.7 + critic_score * 0.3)

        if score >= QUALITY_THRESHOLD or round_num >= MAX_REWRITE_ROUNDS:
            return text, score, score >= QUALITY_THRESHOLD

        # Rewrite — combine feedback from both perspectives
        all_suggestions = scorer_suggestions + [f"[读者视角] {issue}" for issue in critic_issues[:2]]
        if critic_missing:
            all_suggestions.append(f"[遗漏] 需要补充: {critic_missing}")
        improvement = "\n".join(f"- {s}" for s in all_suggestions)
        prompt = f"""你是一个高质量写手。请根据编辑委员会的反馈重写这篇文章，解决以下问题。

编辑委员会评分: {score}/100（评委评 {scorer_score}，批评家评 {critic_score}）

评委指出的主要弱点: {scorer_weakness}

批评家发现的问题:
{chr(10).join(f'- {issue}' for issue in critic_issues)}

改进建议:
{improvement}

原文:
{text}

请直接输出重写后的完整文章，不要额外解释。重点解决评委和批评家指出的问题。
"""
        start_time = time.monotonic()
        text = chat(
            system_prompt="你是一个精益求精的写手，能够根据反馈大幅提升文章质量。",
            user_prompt=prompt,
            temperature=0.8,
        )
        duration = time.monotonic() - start_time
        self.record_llm_call(duration=duration, success=True)
        
        return text, score, False  # not passed yet

    # ── Stage 5: Formatting ────────────────────────────────────────
    def _format(self, text: str) -> str:
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

    # ── Stage 6: Title optimization ────────────────────────────────
    def _generate_titles(self, text: str, topic_title: str) -> tuple[str, list[dict]]:
        """Stage 6: Generate 3 candidate titles, score each, pick best."""
        start_time = time.monotonic()
        result = chat_structured(
            system_prompt="你是一个标题优化专家，深谙公众号读者心理。你生成的标题必须让人忍不住点开，但不能是标题党。好的标题=准确+好奇+差异化。",
            user_prompt=f"""根据以下文章生成3个公众号标题，每个使用不同的标题公式。

标题公式（请各用一种）:
1. 数字型: "X个方法""X天从0到1""提升X%" — 用具体数字给人确定感
2. 提问型: "为什么...？""...到底该怎么选？" — 用问题引发好奇心
3. 对比/反差型: "从X到Y""X vs Y""别再X了，试试Y" — 用反差制造张力

评分维度 (各25分，满分100，严格打分):
- 吸引力 (0-25): 是否让读者在信息流中停下来看？是否制造了信息差/好奇心？
- 准确性 (0-25): 是否准确反映文章核心观点？标题党扣分
- 独特性 (0-25): 是否与同类文章标题差异化？搜索结果中是否脱颖而出？
- SEO (0-25): 是否包含搜索关键词？是否利于平台推荐？

输出JSON:
{{"candidates": [
  {{"title": "完整标题（15-30字）", "score": 78, "type": "数字型", "rationale": "具体推荐理由"}},
  {{"title": "完整标题（15-30字）", "score": 72, "type": "提问型", "rationale": "具体推荐理由"}},
  {{"title": "完整标题（15-30字）", "score": 68, "type": "对比型", "rationale": "具体推荐理由"}}
]}}

选题: {topic_title}
文章开头: {text[:500]}
""",
            temperature=0.7,
        )
        duration = time.monotonic() - start_time
        self.record_llm_call(duration=duration, success=True)
        
        candidates = result.get("candidates", [])
        if not candidates:
            return topic_title, []

        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return candidates[0]["title"], candidates

    # ── Stage 7: Illustrations ─────────────────────────────────────
    def _generate_html_templates(self, text: str, topic_title: str, img_dir: Path) -> list[Path]:
        """Generate HTML template files for illustrations."""
        html_files = []
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
            html_files.append(html_path)

        return html_files

    def _batch_screenshot(self, html_files: list[Path]) -> list[str]:
        """Batch screenshot HTML files, reusing browser instance."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.info("Playwright not installed, returning HTML files")
            return [str(f) for f in html_files]
        
        png_paths = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for html_path in html_files:
                    try:
                        page = browser.new_page(
                            viewport={"width": 580, "height": 440},
                            device_scale_factor=2,
                        )
                        page.goto(f"file://{html_path.resolve()}")
                        page.wait_for_load_state("networkidle")
                        png_path = html_path.with_suffix(".png")
                        page.screenshot(path=str(png_path))
                        page.close()
                        png_paths.append(str(png_path))
                        self.logger.info(f"Screenshot: {png_path}")
                    except Exception as e:
                        self.logger.warning(f"Screenshot failed for {html_path.name}: {e}")
                        png_paths.append(str(html_path))
                browser.close()
        except Exception as e:
            self.logger.error(f"Browser launch failed: {e}")
            return [str(f) for f in html_files]
        
        return png_paths

    def _illustrate(self, text: str, topic_title: str) -> list[str]:
        """Stage 7: Generate illustrations with batched screenshots."""
        img_dir = IMAGES_DIR / self._run_timestamp
        img_dir.mkdir(parents=True, exist_ok=True)

        # Generate HTML templates
        html_files = self._generate_html_templates(text, topic_title, img_dir)
        
        if not html_files:
            return []

        # Batch screenshot (reuses browser instance)
        return self._batch_screenshot(html_files)

    # ── Main pipeline ──────────────────────────────────────────────
    def run(self, topic_id: Optional[str] = None, rewrite_mode: bool = False):
        """Main pipeline execution."""
        # Support --topic-file for router compatibility
        topic_file_arg = None
        work_dir_arg = None
        for i, arg in enumerate(sys.argv):
            if arg == "--topic-file" and i + 1 < len(sys.argv):
                topic_file_arg = Path(sys.argv[i + 1])
            elif arg == "--work-dir" and i + 1 < len(sys.argv):
                work_dir_arg = Path(sys.argv[i + 1])

        if topic_id is None:
            topic_id = sys.argv[1] if len(sys.argv) > 1 else None
        
        if not rewrite_mode:
            rewrite_mode = "--rewrite" in sys.argv
        
        rewrite_target = topic_id if rewrite_mode else None

        # If topic_file_arg given, use that instead of scanning pending/
        _topic_from_file = None
        if topic_file_arg and topic_file_arg.exists():
            _topic_from_file = json.loads(topic_file_arg.read_text())

        # ── Mode: Rewrite ──────────────────────────────────────────
        if rewrite_mode and rewrite_target:
            self.logger.info(f"Rewrite mode: {rewrite_target}")
            self.write_status("初始化", 0, f"重写模式: {rewrite_target}")
            original_text, topic, reject_reason = self._read_article_for_rewrite(rewrite_target)
            if reject_reason:
                self.logger.info(f"Reject reason: {reject_reason}")
                topic["reject_reason"] = reject_reason

            topic_title = topic.get("topic") or topic.get("title", rewrite_target)
            source_url = topic.get("source_url", topic.get("url", ""))
            source_material = original_text

            self.write_status("抓原文", 5, "读取原文素材")
            self.start_stage("fetch_source")
            if source_url and not original_text:
                source_material = self._fetch_source(source_url)
            else:
                source_material = original_text or "无原文素材"
            self.end_stage("fetch_source")

            # Stage 2: Rewrite with feedback
            self.write_status("LLM初稿", 20, "根据反馈重写")
            self.start_stage("draft")
            prompt_extra = ""
            if reject_reason:
                prompt_extra = f"\n\n驳回原因（必须针对性改进）: {reject_reason}"
            text = self._draft(
                {"title": topic_title, "description": topic.get("topic", "") + prompt_extra},
                source_material,
            )
            self.end_stage("draft")

        # ── Mode: Normal from topic ────────────────────────────────
        else:
            self.write_status("初始化", 0, "读取选题配置")
            topic = _topic_from_file if _topic_from_file else self._read_topic(topic_id)
            self.logger.info(f"Starting pipeline for: {topic['title']}")
            source_material = ""
            source_url = topic.get("url", "")

            self.write_status("抓原文", 5, "抓取原文素材")
            self.start_stage("fetch_source")
            if source_url:
                source_material = self._fetch_source(source_url)
            else:
                source_material = "无原文链接。将基于选题方向生成。"
            self.end_stage("fetch_source")
            self.logger.info(f"Stage 1 done. Source: {len(source_material)} chars")

            self.write_status("LLM初稿", 20, "生成初稿")
            self.start_stage("draft")
            text = self._draft(topic, source_material)
            self.end_stage("draft")
            self.logger.info(f"Stage 2 done. Draft: {len(text)} chars")

        # Stage 3: Proofread
        self.write_status("AI腔审校", 35, "检测并移除AI腔")
        text, proofread_score = self._proofread(text)
        self.logger.info(f"Stage 3 done. Proofread score: {proofread_score}")

        # Stage 4: Critique & rewrite loop
        self.write_status("批评修订", 50, "评委评分中")
        self.start_stage("critique")
        critique_scores: list[int] = []
        for round_num in range(1, MAX_REWRITE_ROUNDS + 1):
            text, score, passed = self._critique(text, topic["title"], round_num)
            critique_scores.append(score)
            self.write_status("批评修订", 50 + round_num * 10,
                          f"第{round_num}轮: 评分{score}")
            self.logger.info(f"Stage 4 round {round_num}: score={score}, passed={passed}")
            if passed:
                break
            if round_num < MAX_REWRITE_ROUNDS:
                self.write_status("批评修订", 50 + round_num * 10,
                              f"第{round_num}轮未通过，开始第{round_num + 1}轮")
        self.end_stage("critique")

        # Stage 5: Format
        self.write_status("排版", 75, "格式化排版")
        self.start_stage("format")
        text = self._format(text)
        self.end_stage("format")
        self.logger.info("Stage 5 done. Formatted.")

        # Stage 6: Titles
        self.write_status("标题优化", 85, "生成候选标题")
        self.start_stage("titles")
        final_title, title_candidates = self._generate_titles(text, topic["title"])
        title_score = title_candidates[0]["score"] if title_candidates else 0
        self.end_stage("titles")
        self.logger.info(f"Stage 6 done. Best title: {final_title}")

        # Stage 7: Illustrations
        self.write_status("配图", 92, "生成配图")
        self.start_stage("illustrate")
        images = self._illustrate(text, topic["title"])
        self.end_stage("illustrate")
        self.logger.info(f"Stage 7 done. Images: {len(images)}")

        # Write output
        self.write_status("完成", 95, "写入输出文件")
        article_path = REVIEW_DIR / f"{self._run_timestamp}-{self.worker_type}.md"
        meta_path = REVIEW_DIR / f"{self._run_timestamp}-{self.worker_type}.meta.json"

        article_path.write_text(f"# {final_title}\n\n{text}", encoding="utf-8")

        meta = {
            "topic": topic["title"],
            "source_url": source_url,
            "platform_standard": self.worker_type,
            "proofread_score": proofread_score,
            "critique_scores": critique_scores,
            "revised_rounds": len(critique_scores),
            "title_score": title_score,
            "title_candidates": title_candidates,
            "word_count": len(text),
            "ai_slop_issues": 100 - proofread_score,
            "images": images,
            "writing_style": f"{self.worker_type}_default",
            "image_generation_method": "html_template" if images else "none",
            "status": "completed",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

        # Final status with metrics
        self.write_completed(
            detail=f"管线完成 · 评分{proofread_score}/{critique_scores[-1] if critique_scores else 0}",
            article=str(article_path),
            meta=str(meta_path),
        )

        self.logger.info(f"Pipeline complete!")
        self.logger.info(f"Article: {article_path}")
        self.logger.info(f"Meta: {meta_path}")


def main():
    """Entry point for backward compatibility."""
    agent = WriterAgent()
    agent.run()


if __name__ == "__main__":
    main()
