"""Writer video — 图文转视频管线（方案 C）+ Agnes AI 视频生成。

方案 C（主流程）：文章拆段 → 每段配图+配音 → ffmpeg 合成视频
  1. LLM 将文章拆分为 5-8 个段落（每段含 TTS 文本 + 图片 prompt）
  2. 并行生成：Agnes 配图 + MiMo TTS 配音
  3. ffmpeg 合成：每张图显示对应音频时长，交叉淡入淡出

方案 A（备选）：Agnes AI 视频生成（慢、贵，适合短片头/片尾）

Note: This is a helper module, not an agent. WriterAgent passes its own logger
to each function here, so this module does not extend AgentBase directly.
"""

import json
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from config.settings import CONFIG_DIR
from skills.common import get_agent_logger, load_image_styles

# Backward compatibility alias
_load_image_styles = load_image_styles


def _load_video_count(worker_type: str) -> int:
    """Load video count from writing_styles.json for the given platform."""
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


def split_article_into_segments(
    text: str,
    topic_title: str,
    num_segments: int = 6,
    content_type: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> list[dict]:
    """Use LLM to split article into video segments.

    Each segment has:
    - tts_text: Chinese text for TTS (1-2 sentences, 15-30 seconds)
    - image_prompt: English image prompt for Agnes

    Returns: list of {"tts_text": str, "image_prompt": str}
    """
    from skills.llm import LLMError, chat_structured

    if logger is None:
        logger = get_agent_logger(__name__)

    image_styles = _load_image_styles()
    style_cfg = image_styles.get(content_type or "tutorial", {})
    style_keywords = style_cfg.get("style", "modern, clean, high quality")

    system_prompt = (
        "你是一个专业的视频脚本编辑。将文章拆分为适合短视频的段落。"
        "每段包含：1）中文配音文本（1-2句话，口语化，适合朗读）；"
        "2）英文配图 prompt（描述该段内容的视觉画面）。"
        "严格输出 JSON，不要有其他文字。"
    )

    user_prompt = f"""请将以下文章拆分为 {num_segments} 个短视频段落。

文章标题：{topic_title}
文章内容：
{text[:3000]}

要求：
1. 每段 tts_text 是 1-2 句中文口语化文本，适合朗读，每段约 15-30 秒
2. 每段 image_prompt 是英文，描述该段的视觉画面，风格：{style_keywords}
3. 第一段是开场钩子，最后一段是总结/行动引导
4. 段落之间有逻辑衔接，整体连贯

输出 JSON：
```json
{{
  "segments": [
    {{"tts_text": "中文配音文本", "image_prompt": "English image prompt"}},
    ...
  ]
}}
```"""

    try:
        result = chat_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.5,
        )
        segments = result.get("segments", [])
        if not segments:
            logger.warning("LLM returned empty segments")
            return []

        # Validate each segment has required fields
        valid = []
        for seg in segments:
            if seg.get("tts_text") and seg.get("image_prompt"):
                valid.append(seg)

        logger.info(f"Split article into {len(valid)} segments")
        return valid

    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Article segmentation failed: {e}")
        return []


def _generate_segment_audio(
    index: int,
    tts_text: str,
    output_path: Path,
    content_type: Optional[str] = None,
) -> Optional[str]:
    """Generate TTS audio for a single segment."""
    from skills.tts import synthesize_speech
    return synthesize_speech(
        tts_text, output_path, content_type=content_type,
    )


def _generate_segment_image(
    index: int,
    image_prompt: str,
    output_path: Path,
    size: str = "1024x576",
) -> Optional[str]:
    """Generate image for a single segment via Agnes."""
    from skills.writer_illustration import generate_images_agnes
    import logging
    logger = logging.getLogger(__name__)
    paths = generate_images_agnes([image_prompt], output_path.parent, size, logger)
    if paths:
        # Rename to expected filename
        src = Path(paths[0])
        if src != output_path:
            src.rename(output_path)
        return str(output_path)
    return None


def _get_audio_duration(audio_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries",
             "format=duration", "-of", "csv=p=0", str(audio_path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return 5.0  # fallback to 5 seconds


def _combine_segments_ffmpeg(
    segments: list[dict],
    output_path: Path,
    crossfade_duration: float = 0.5,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Combine image+audio segments into final video using ffmpeg.

    Each segment dict must have:
    - image: path to image file
    - audio: path to audio file
    - duration: audio duration in seconds

    Returns: output video path, or None on failure.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    if not segments:
        logger.error("No segments to combine")
        return None

    # Check ffmpeg availability
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("ffmpeg not found. Install with: brew install ffmpeg")
        return None

    # Strategy: create individual video clips per segment, then concat
    temp_dir = output_path.parent / "tmp_clips"
    temp_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    for i, seg in enumerate(segments):
        img = seg["image"]
        audio = seg["audio"]
        duration = seg.get("duration", 5.0)
        clip_path = temp_dir / f"clip_{i:02d}.mp4"

        # Create video from image + audio
        # -loop 1: loop image for audio duration
        # -c:v libx264: H.264 video codec
        # -tune stillimage: optimize for still images
        # -pix_fmt yuv420p: compatibility
        # -shortest: match audio length
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img),
            "-i", str(audio),
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            str(clip_path),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and clip_path.exists():
                clip_paths.append(clip_path)
            else:
                logger.warning(f"ffmpeg clip {i} failed: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"ffmpeg clip {i} timeout")

    if not clip_paths:
        logger.error("No clips generated")
        return None

    # Concat all clips
    concat_file = temp_dir / "concat.txt"
    concat_content = "".join(f"file '{p}'\n" for p in clip_paths)
    concat_file.write_text(concat_content)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(output_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            logger.info(f"Video combined: {output_path.name} ({size_mb:.1f} MB)")

            # Cleanup temp clips
            for p in clip_paths:
                p.unlink(missing_ok=True)
            concat_file.unlink(missing_ok=True)
            temp_dir.rmdir()

            return str(output_path)
        else:
            logger.error(f"ffmpeg concat failed: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg concat timeout")
        return None


def generate_slideshow_video(
    text: str,
    topic_title: str,
    videos_dir: Path,
    run_timestamp: str,
    logger: Optional[logging.Logger] = None,
    worker_type: str = "douyin",
    content_type: Optional[str] = None,
    num_segments: int = 6,
) -> Optional[str]:
    """图文转视频管线（方案 C）：文章拆段 → 配图+配音 → ffmpeg 合成。

    Args:
        text: Article body text
        topic_title: Article title
        videos_dir: Base videos directory (config.settings.VIDEOS_DIR)
        run_timestamp: Current run timestamp for directory naming
        logger: Logger instance
        worker_type: Platform type (douyin/wechat/xiaohongshu)
        content_type: Content type (tutorial/news/etc.)
        num_segments: Number of segments to split article into (5-8)

    Returns: Output video path (MP4), or None if skipped/failed.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    # Check if video generation is enabled
    count = _load_video_count(worker_type)
    if count == 0:
        logger.info(f"videos=0 for {worker_type}, skipping video generation")
        return None

    video_dir = videos_dir / run_timestamp
    video_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Split article into segments
    logger.info(f"Step 1: Splitting article into {num_segments} segments")
    segments = split_article_into_segments(
        text, topic_title, num_segments, content_type, logger,
    )
    if not segments:
        logger.error("Failed to split article into segments")
        return None

    # Step 2: Generate images and audio in parallel
    logger.info(f"Step 2: Generating {len(segments)} images + audio tracks")
    image_styles = _load_image_styles()
    style_cfg = image_styles.get(content_type or "tutorial", {})
    img_size = style_cfg.get("size", "1024x576")

    completed_segments = []

    def _process_segment(i, seg):
        img_path = video_dir / f"img_{i:02d}.png"
        audio_path = video_dir / f"audio_{i:02d}.wav"

        # Generate image and audio in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            img_future = executor.submit(
                _generate_segment_image, i, seg["image_prompt"], img_path, img_size,
            )
            audio_future = executor.submit(
                _generate_segment_audio, i, seg["tts_text"], audio_path, content_type,
            )
            img_result = img_future.result()
            audio_result = audio_future.result()

        if img_result and audio_result:
            duration = _get_audio_duration(Path(audio_result))
            return {
                "image": img_result,
                "audio": audio_result,
                "duration": duration,
            }
        return None

    # Process all segments (limited concurrency to avoid API overload)
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_process_segment, i, seg): i
            for i, seg in enumerate(segments)
        }
        results = {}
        for future in as_completed(futures):
            i = futures[future]
            try:
                result = future.result()
                if result:
                    results[i] = result
            except Exception as e:
                logger.warning(f"Segment {i} failed: {e}")

    # Maintain order
    for i in sorted(results.keys()):
        completed_segments.append(results[i])

    if not completed_segments:
        logger.error("No segments completed successfully")
        return None

    logger.info(f"Step 2 done: {len(completed_segments)}/{len(segments)} segments ready")

    # Step 3: Combine with ffmpeg
    logger.info("Step 3: Combining segments with ffmpeg")
    output_path = video_dir / "video.mp4"
    path = _combine_segments_ffmpeg(completed_segments, output_path, logger=logger)

    if path:
        logger.info(f"Slideshow video complete: {path}")
    else:
        logger.error("Video combination failed")

    return path


# ── Legacy: Agnes AI video generation (方案 A) ──────────────────────────

def generate_video_prompt(
    text: str,
    topic_title: str,
    worker_type: str,
    content_type: Optional[str] = None,
    duration: int = 5,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Use LLM to generate a video prompt from article content."""
    from skills.llm import LLMError, chat_structured
    from skills.common import load_prompt

    if logger is None:
        logger = get_agent_logger(__name__)

    image_styles = _load_image_styles()
    style_cfg = image_styles.get(content_type or "tutorial", {})
    style_keywords = style_cfg.get("style", "modern, clean, high quality")

    prompt_template = load_prompt(
        "video_prompt_gen",
        topic=topic_title,
        content_type=content_type or "tutorial",
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
            temperature=0.7,
        )
        return result.get("video_prompt", "")
    except (LLMError, json.JSONDecodeError, KeyError) as e:
        logger.error(f"Video prompt generation failed: {e}")
        return ""


def generate_video_agnes(
    prompt: str,
    video_dir: Path,
    duration: int = 5,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """Generate a video using Agnes API for the given prompt."""
    if logger is None:
        logger = get_agent_logger(__name__)

    agnes_script = Path(os.environ.get(
        "AGNES_SCRIPT_PATH",
        str(Path.home() / ".agents/skills/agnes-generate/scripts/video_gen.py"),
    ))
    if not agnes_script.exists():
        logger.error(f"Agnes video script not found: {agnes_script}")
        return None

    output = video_dir / "video_1.mp4"
    safe_prompt = prompt.replace("\x00", "")
    safe_prompt = "".join(c for c in safe_prompt if c == "\n" or c == "\t" or (ord(c) >= 32))
    if len(safe_prompt) > 2000:
        safe_prompt = safe_prompt[:2000]

    try:
        result = subprocess.run(
            ["python3", str(agnes_script), safe_prompt, str(output), str(duration)],
            capture_output=True, text=True, timeout=900,
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
    num_segments: int = 6,
) -> Optional[str]:
    """Video generation entry point.

    Uses slideshow pipeline (方案 C) by default:
    article → segments → images + TTS → ffmpeg → MP4

    Falls back to Agnes video (方案 A) if slideshow fails.
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    # Try slideshow pipeline first (方案 C)
    logger.info("Attempting slideshow video pipeline (方案 C)")
    result = generate_slideshow_video(
        text, topic_title, videos_dir, run_timestamp,
        logger=logger, worker_type=worker_type,
        content_type=content_type, num_segments=num_segments,
    )

    if result:
        return result

    # Fallback to Agnes video (方案 A)
    logger.info("Slideshow failed, falling back to Agnes video (方案 A)")
    count = _load_video_count(worker_type)
    if count == 0:
        return None

    video_dir = videos_dir / run_timestamp
    video_dir.mkdir(parents=True, exist_ok=True)

    video_prompt = generate_video_prompt(
        text, topic_title, worker_type, content_type, duration, logger,
    )
    if not video_prompt:
        return None

    return generate_video_agnes(video_prompt, video_dir, duration, logger)
