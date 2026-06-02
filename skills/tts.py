"""TTS utility — MiMo-V2.5-TTS 语音合成。

使用 MiMo chat completions API 进行文本转语音。
Endpoint: POST https://api.xiaomimimo.com/v1/chat/completions
Model: mimo-v2.5-tts

关键格式要求（来自官方文档）：
- 目标文本必须放在 role:assistant 的 messages 中
- role:user 可选，用于传入风格控制指令
- audio.format: wav（非流式）或 pcm16（流式，24kHz）
- audio.voice: 预置音色 ID（mimo_default/冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo）
- 返回 base64 编码的音频数据
"""

import base64
import json
import logging
from pathlib import Path
from typing import Optional

import httpx

from config.settings import LLM_API_KEY, LLM_BASE_URL, require_api_key
from skills.common import get_agent_logger

# 预置音色列表
VOICES = {
    "default": "mimo_default",   # 中国集群默认冰糖
    "冰糖": "冰糖",             # 中文女性
    "茉莉": "茉莉",             # 中文女性
    "苏打": "苏打",             # 中文男性
    "白桦": "白桦",             # 中文男性
    "Mia": "Mia",               # 英文女性
    "Chloe": "Chloe",           # 英文女性
    "Milo": "Milo",             # 英文男性
}

# 内容类型 → 默认风格指令映射
STYLE_MAP = {
    "news": "用专业沉稳的新闻播报语调，语速适中，吐字清晰，声音干净利落。",
    "tutorial": "用亲切自然的教学语气，语速稍慢，节奏平稳，像在手把手教朋友。",
    "tool_update": "用轻松明快的科技评测语气，语速适中，带着发现好东西的小兴奋。",
    "tech_science": "用深入浅出的科普语气，沉稳但不枯燥，像在讲一个有趣的故事。",
    "insight": "用沉稳有力的洞察语气，语速偏慢，每句话都有分量，像在分享深度思考。",
    "opinion": "用犀利直接的评论语气，语速稍快，观点鲜明，带着敢说真话的劲头。",
    "sharing": "用温暖真诚的分享语气，像在跟好朋友聊天，自然不做作。",
    "roundup": "用清爽利落的清单播报语气，节奏明快，每条推荐都干脆有力。",
}


class TTSError(Exception):
    """TTS 调用失败。"""


def synthesize_speech(
    text: str,
    output_path: Path,
    style_instruction: Optional[str] = None,
    voice: str = "default",
    content_type: Optional[str] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """将文本合成为语音文件。

    Args:
        text: 要合成的文本（将放在 role:assistant 中）
        output_path: 输出音频文件路径（.wav）
        style_instruction: 风格控制指令（放在 role:user 中），覆盖 content_type 默认
        voice: 音色 ID（见 VOICES 字典的 key）
        content_type: 内容类型，用于自动选择默认风格指令
        logger: 日志实例

    Returns:
        输出文件路径，失败返回 None
    """
    if logger is None:
        logger = get_agent_logger(__name__)

    api_key = LLM_API_KEY or require_api_key()
    voice_id = VOICES.get(voice, VOICES["default"])

    # 确定风格指令
    if style_instruction is None and content_type:
        style_instruction = STYLE_MAP.get(content_type)
    # 如果还是 None，不传 user message（使用默认风格）

    # 构建 messages（关键：目标文本在 role:assistant 中）
    messages = []
    if style_instruction:
        messages.append({"role": "user", "content": style_instruction})
    messages.append({"role": "assistant", "content": text})

    # 构建请求体
    body = {
        "model": "mimo-v2.5-tts",
        "messages": messages,
        "audio": {
            "format": "wav",
            "voice": voice_id,
        },
    }

    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    logger.info(f"TTS 合成: {len(text)} 字, 音色={voice_id}, 风格={content_type or '默认'}")

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()

        data = resp.json()

        # 提取 base64 音频数据
        audio_b64 = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("audio", {})
            .get("data", "")
        )

        if not audio_b64:
            logger.error(f"TTS 返回无音频数据: {json.dumps(data)[:300]}")
            return None

        # 解码并写入文件
        audio_bytes = base64.b64decode(audio_b64)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        size_kb = len(audio_bytes) / 1024
        logger.info(f"TTS 完成: {output_path.name} ({size_kb:.0f} KB)")
        return str(output_path)

    except httpx.HTTPStatusError as e:
        logger.error(f"TTS HTTP 错误 {e.response.status_code}: {e.response.text[:200]}")
        return None
    except (httpx.TimeoutException, httpx.ConnectError) as e:
        logger.error(f"TTS 网络错误: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"TTS 响应解析错误: {e}")
        return None
    except Exception as e:
        logger.error(f"TTS 未知错误: {e}")
        return None
