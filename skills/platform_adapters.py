"""Platform adaptation engine — per-platform content formatting.

Adapts article content for each platform's style and constraints:
- wechat: Long-form, structured, professional
- xiaohongshu: Emoji-heavy, short paragraphs, visual, trendy
- douyin: Hook-driven, short, punchy, golden sentences
- weibo: Conversational, hashtags, short
"""

import re
from typing import Optional


class PlatformAdapter:
    """Base class for platform-specific content adaptation."""

    name: str = "base"
    max_length: int = 10000
    style_notes: str = ""

    def adapt(self, title: str, content: str) -> tuple[str, str]:
        """Adapt title and content for this platform.

        Returns (adapted_title, adapted_content).
        """
        raise NotImplementedError


class WeChatAdapter(PlatformAdapter):
    """WeChat Official Account — long-form, structured, professional."""

    name = "wechat"
    max_length = 20000
    style_notes = "长文、分段清晰、专业深度、适当引用"

    def adapt(self, title: str, content: str) -> tuple[str, str]:
        # WeChat prefers structured long-form
        # Ensure proper paragraph spacing
        content = re.sub(r'\n{3,}', '\n\n', content)
        # Add section dividers if missing
        if '##' not in content and len(content) > 1000:
            paragraphs = content.split('\n\n')
            if len(paragraphs) >= 4:
                mid = len(paragraphs) // 2
                paragraphs.insert(mid, '---')
                content = '\n\n'.join(paragraphs)
        return title, content[:self.max_length]


class XiaohongshuAdapter(PlatformAdapter):
    """小红书 — emoji-heavy, short paragraphs, visual, trendy."""

    name = "xiaohongshu"
    max_length = 2000
    style_notes = "短段落、emoji点缀、口语化、干货清单"

    # Emoji decorations for different content types
    SECTION_EMOJIS = ['✨', '💡', '🔥', '📌', '🎯', '⭐', '💪', '🚀', '📝', '🔑']
    LIST_EMOJIS = ['✅', '👉', '💛', '🌟', '💖']

    def adapt(self, title: str, content: str) -> tuple[str, str]:
        # Add emoji to title
        if not re.search(r'[\U0001f300-\U0001f9ff]', title):
            title = f"💡 {title}"

        # Break long paragraphs into short ones
        paragraphs = content.split('\n\n')
        short_paragraphs = []
        for p in paragraphs:
            if len(p) > 150:
                # Split long paragraphs at sentence boundaries
                sentences = re.split(r'([。！？])', p)
                current = ''
                for i, s in enumerate(sentences):
                    current += s
                    if len(current) > 80 or (i % 2 == 1 and len(current) > 40):
                        short_paragraphs.append(current.strip())
                        current = ''
                if current.strip():
                    short_paragraphs.append(current.strip())
            else:
                short_paragraphs.append(p)

        # Add section emojis
        result_paragraphs = []
        emoji_idx = 0
        for p in short_paragraphs:
            p = p.strip()
            if not p:
                continue
            # Add emoji to list-like paragraphs
            if re.match(r'^[\d一二三四五六七八九十]+[.、）)]', p):
                emoji = self.LIST_EMOJIS[emoji_idx % len(self.LIST_EMOJIS)]
                p = re.sub(r'^[\d一二三四五六七八九十]+[.、）)]', f'{emoji}', p)
                emoji_idx += 1
            elif len(p) > 50 and not re.search(r'[\U0001f300-\U0001f9ff]', p):
                emoji = self.SECTION_EMOJIS[emoji_idx % len(self.SECTION_EMOJIS)]
                p = f"{emoji} {p}"
                emoji_idx += 1
            result_paragraphs.append(p)

        # Add hashtags at end
        content = '\n\n'.join(result_paragraphs)
        if '#' not in content:
            content += '\n\n#科技 #AI #干货分享 #职场'

        # Add CTA
        content += '\n\n💛 觉得有用的话，点赞收藏支持一下吧~'

        return title, content[:self.max_length]


class DouyinAdapter(PlatformAdapter):
    """抖音 — hook-driven, short, punchy, golden sentences."""

    name = "douyin"
    max_length = 1000
    style_notes = "开头钩子、短句金句、口语化、引导互动"

    def adapt(self, title: str, content: str) -> tuple[str, str]:
        # Make title more hook-like
        if len(title) > 20:
            title = title[:18] + '...'

        # Extract key sentences (golden sentences)
        sentences = re.split(r'[。！？\n]', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        # Pick the most impactful sentences
        golden = []
        for s in sentences[:8]:
            # Prefer sentences with numbers, questions, or strong opinions
            if re.search(r'\d+', s) or '？' in s or '！' in s:
                golden.insert(0, s)
            else:
                golden.append(s)

        # Format as short-form content
        result_parts = []

        # Hook opening
        if golden:
            result_parts.append(f"🔥 {golden[0]}")
        else:
            result_parts.append(f"🔥 {title}")

        # Key points (max 5)
        for s in golden[1:6]:
            result_parts.append(f"\n👉 {s}")

        # CTA
        result_parts.append(f"\n\n💬 你怎么看？评论区聊聊~")
        result_parts.append(f"#科技 #AI #热点")

        content = '\n'.join(result_parts)
        return title, content[:self.max_length]


class WeiboAdapter(PlatformAdapter):
    """微博 — conversational, hashtags, short."""

    name = "weibo"
    max_length = 2000
    style_notes = "口语化、话题标签、互动性、短段落"

    def adapt(self, title: str, content: str) -> tuple[str, str]:
        # Make it conversational
        # Extract first 2-3 paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        short_content = '\n\n'.join(paragraphs[:3])

        # Add hashtags
        if '#' not in short_content:
            short_content += '\n\n#科技# #AI# #热点话题#'

        # Add engagement prompt
        short_content += '\n\n转发说说你的看法 👇'

        return title, short_content[:self.max_length]


# Registry
ADAPTERS: dict[str, PlatformAdapter] = {
    "wechat": WeChatAdapter(),
    "xiaohongshu": XiaohongshuAdapter(),
    "douyin": DouyinAdapter(),
    "weibo": WeiboAdapter(),
}


def get_adapter(platform: str) -> Optional[PlatformAdapter]:
    """Get the adapter for a platform."""
    return ADAPTERS.get(platform)


def adapt_content(title: str, content: str, platform: str) -> tuple[str, str]:
    """Adapt content for a specific platform.

    Returns (adapted_title, adapted_content).
    Falls back to original if no adapter found.
    """
    adapter = get_adapter(platform)
    if not adapter:
        return title, content
    return adapter.adapt(title, content)


def get_supported_platforms() -> list[str]:
    """List all supported platforms."""
    return list(ADAPTERS.keys())
