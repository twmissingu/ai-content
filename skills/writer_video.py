"""Writer video — Agnes AI video generation + MiMo TTS with LLM prompt engineering.

Stage 7b flow (optional, after illustration):
  1. Load video count from writing_styles.json
  2. LLM generates English video prompt based on article content
  3. Agnes API generates video from prompt (async polling, up to 15 min)
  4. MiMo-V2.5-TTS generates voiceover audio from article text

Note: This is a helper module, not an agent. WriterAgent passes its own logger
to each function here, so this module does not extend AgentBase directly.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from config.settings import CONFIG_DIR
from skills.common import get_agent_logger


def _load_video_count(worker_type: str) -> int:
    """Load video count from writing_styles.json for the given platform.

    Uses the platform default style (e.g., 'douyin_default').
    Returns 0 if videos are not configured for this platform.
    """
    path = CONFIG_DIR / "writing_styles.json"
    if not path.exists():
        return 0
    try:
        styles = json.loads(path.read_text(encoding="utf-8"))
        default_key = f"{worker_type}_default"
        style = styles.get(default_key, {})
        return style.get("videos", 0)
    except (json.JSONDecodeError, OSError):
        return 0


def generate_video_prompt(
    text: str,
    topic_title: str,
    worker_type: str,
    content_type: Optional[str] = None,
    duration: int = 5,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Use LLM to generate a video prompt from article content.

    Returns: English video prompt string, or empty string on failure.
    """
    from skills.llm import LLMError, chat_structured
    from skills.common import load_prompt

    if logger is None:
        logger = get_agent_logger(__name__)

    if content_type is None:
        content_type = "tutorial"

    # Load image styles for visual style keywords (reused for video)
    styles_path = CONFIG_DIR / "image_styles.json"
    image_styles = {}
    if styles_path.exists():
        try:
            image_styles = json.loads(styles_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    style_cfg = image_styles.get(content_type, image_styles.get("tutorial", {}))
    style_keywords = style_cfg.get("style", "modern, clean, high quality")

    prompt_template = load_prompt(
        "video_prompt_gen",
        topic=topic_title,
        content_type=content_type,
        platform=worker_type,
        style=style_keywords,
        duration=duration,
        text_summary=text[:2000],
    )

    system_prompt = (
        "You are a professional AI video prompt engineer. "
        "Generate a high-quality English video prompt based on article content. "
        "Always respond with valid JSON only."
    )

    try:
        result = chat_structured(
            system_prompt=system_prompt,
            user_prompt=prompt_template,
            json_mode=True,
            temperature=0.7,
        )
        video_prompt = result.get("video_prompt", "")
        if video_prompt:
            logger.info(f"Generated video prompt ({len(video_prompt)} chars)")
        else:
            logger.warning("LLM returned empty video prompt")
        return video_prompt

    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Video prompt generation failed: {e}")
        return ""


def generate_video_agnes(
    prompt: str,
    video_dir: Path,
    duration: int = 5,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Generate a video using Agnes API for the given prompt.

    Returns local video file path, or None on failure.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    agnes_script = Path(os.environ.get(
        "AGNES_SCRIPT_PATH",
        str(Path.home() / ".agents/skills/agnes-generate/scripts/video_gen.py"),
    ))
    if not agnes_script.exists():
        logger.error(f"Agnes video script not found: {agnes_script}")
        return None

    def _sanitize_prompt(raw: str, max_len: int = 2000) -> str:
        """Strip control chars/null bytes and truncate LLM-generated prompt."""
        cleaned = raw.replace("\x00", "")
        cleaned = "".join(
            c for c in cleaned if c == "\n" or c == "\t" or (ord(c) >= 32)
        )
        if len(cleaned) > max_len:
            logger.warning(
                f"Video prompt truncated from {len(cleaned)} to {max_len} chars"
            )
            cleaned = cleaned[:max_len]
        return cleaned

    output = video_dir / "video_1.mp4"
    safe_prompt = _sanitize_prompt(prompt)

    try:
        result = subprocess.run(
            ["python3", str(agnes_script), safe_prompt, str(output), str(duration)],
            capture_output=True,
            text=True,
            timeout=900,  # 15 minutes — Agnes video is async with polling
        )
        if result.returncode == 0 and output.exists():
            size_mb = output.stat().st_size / (1024 * 1024)
            logger.info(f"Agnes generated video: {output.name} ({size_mb:.1f} MB)")
            return str(output)
        else:
            logger.warning(f"Agnes video failed: {result.stderr[:300]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning("Agnes video timeout (15 min)")
        return None
    except (OSError, subprocess.SubprocessError) as e:
        logger.warning(f"Agnes video error: {e}")
        return None


def generate_video(
    text: str,
    topic_title: str,
    videos_dir: Path,
    run_timestamp: str,
    logger: Optional[logging.Logger] = None,
    worker_type: str = "douyin",
    content_type: Optional[str] = None,
    duration: int = 5,
) -> Optional[str]:
    """Full video generation pipeline: LLM prompt → Agnes video generation.

    Args:
        text: Article body text
        topic_title: Article title
        videos_dir: Base videos directory (config.settings.VIDEOS_DIR)
        run_timestamp: Current run timestamp for directory naming
        logger: Logger instance
        worker_type: Platform type (douyin/wechat/xiaohongshu)
        content_type: Content type (tutorial/news/etc.) for style lookup
        duration: Video duration in seconds (1-15)

    Returns: Video file path (MP4), or None if skipped/failed.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    # Check if video generation is enabled for this platform
    count = _load_video_count(worker_type)
    if count == 0:
        logger.info(f"videos=0 for {worker_type}, skipping video generation")
        return None

    video_dir = videos_dir / run_timestamp
    video_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate prompt via LLM
    video_prompt = generate_video_prompt(
        text, topic_title, worker_type, content_type, duration, logger,
    )

    if not video_prompt:
        logger.info("No video prompt generated, skipping video generation")
        return None

    # Step 2: Generate video via Agnes
    path = generate_video_agnes(video_prompt, video_dir, duration, logger)

    # Step 3: Generate TTS voiceover (optional, non-blocking)
    try:
        from skills.tts import synthesize_speech
        tts_path = video_dir / "voiceover.wav"
        # Use first 500 chars for TTS (video is short, voiceover should be concise)
        tts_text = text[:500]
        audio_path = synthesize_speech(
            tts_text, tts_path,
            content_type=content_type,
            logger=logger,
        )
        if audio_path:
            logger.info(f"TTS voiceover generated: {audio_path}")
    except Exception as e:
        logger.warning(f"TTS voiceover failed (non-blocking): {e}")

    if path:
        logger.info(f"Video generation complete: {path}")
    else:
        logger.warning("Video generation failed")

    return path
