"""Tests for skills/platform_adapters.py — per-platform content formatting."""

import pytest
from skills.platform_adapters import (
    WeChatAdapter,
    XiaohongshuAdapter,
    DouyinAdapter,
    WeiboAdapter,
    adapt_content,
    get_adapter,
    get_supported_platforms,
)


class TestWeChatAdapter:
    """Test WeChat platform adapter."""

    def setup_method(self):
        self.adapter = WeChatAdapter()

    def test_returns_title_and_content(self):
        title, content = self.adapter.adapt("Test Title", "Some content here.")
        assert title == "Test Title"
        assert isinstance(content, str)

    def test_collapses_excessive_newlines(self):
        title, content = self.adapter.adapt("Title", "Para1\n\n\n\n\nPara2")
        assert "\n\n\n" not in content

    def test_adds_divider_for_long_content(self):
        long_content = "\n\n".join([f"Paragraph {i} with enough text to be meaningful for the reader." * 5 for i in range(10)])
        title, content = self.adapter.adapt("Title", long_content)
        assert "---" in content

    def test_respects_max_length(self):
        content = "x" * 30000
        title, result = self.adapter.adapt("Title", content)
        assert len(result) <= self.adapter.max_length

    def test_empty_content(self):
        title, content = self.adapter.adapt("Title", "")
        assert title == "Title"


class TestXiaohongshuAdapter:
    """Test Xiaohongshu platform adapter."""

    def setup_method(self):
        self.adapter = XiaohongshuAdapter()

    def test_adds_emoji_to_title_without_emoji(self):
        title, _ = self.adapter.adapt("Test Title", "Content")
        assert "💡" in title

    def test_preserves_title_with_existing_emoji(self):
        title, _ = self.adapter.adapt("🔥 Hot Title", "Content")
        assert title == "🔥 Hot Title"

    def test_breaks_long_paragraphs(self):
        long_para = "这是一个很长的段落。" * 30
        _, content = self.adapter.adapt("Title", long_para)
        # Should be broken into shorter paragraphs
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        assert len(paragraphs) > 1

    def test_adds_hashtags(self):
        _, content = self.adapter.adapt("Title", "Some content here.")
        assert "#" in content

    def test_adds_cta(self):
        _, content = self.adapter.adapt("Title", "Some content.")
        assert "点赞" in content or "收藏" in content

    def test_respects_max_length(self):
        content = "x" * 5000
        _, result = self.adapter.adapt("Title", content)
        assert len(result) <= self.adapter.max_length

    def test_list_items_get_emoji(self):
        content = "1. 第一点\n2. 第二点\n3. 第三点"
        _, result = self.adapter.adapt("Title", content)
        assert "✅" in result or "👉" in result


class TestDouyinAdapter:
    """Test Douyin platform adapter."""

    def setup_method(self):
        self.adapter = DouyinAdapter()

    def test_truncates_long_title(self):
        title = "这是一个非常非常长的标题需要被截断处理"
        result_title, _ = self.adapter.adapt(title, "Content")
        assert len(result_title) <= 20

    def test_preserves_short_title(self):
        title, _ = self.adapter.adapt("短标题", "Content")
        assert title == "短标题"

    def test_adds_hook_emoji(self):
        _, content = self.adapter.adapt("Title", "这是一些有价值的内容。包含数字123和更多信息。")
        assert "🔥" in content

    def test_adds_cta(self):
        _, content = self.adapter.adapt("Title", "Content here with enough text to work with.")
        assert "评论" in content or "聊聊" in content

    def test_respects_max_length(self):
        content = "x" * 3000
        _, result = self.adapter.adapt("Title", content)
        assert len(result) <= self.adapter.max_length

    def test_empty_content(self):
        title, content = self.adapter.adapt("Title", "")
        assert title == "Title"


class TestWeiboAdapter:
    """Test Weibo platform adapter."""

    def setup_method(self):
        self.adapter = WeiboAdapter()

    def test_preserves_title(self):
        title, _ = self.adapter.adapt("Test Title", "Content")
        assert title == "Test Title"

    def test_limits_paragraphs(self):
        content = "\n\n".join([f"Paragraph {i}" for i in range(10)])
        _, result = self.adapter.adapt("Title", content)
        # Should limit to first 3 paragraphs
        assert "Paragraph 9" not in result

    def test_adds_hashtags(self):
        _, content = self.adapter.adapt("Title", "Some content without hashtags.")
        assert "#" in content

    def test_adds_engagement(self):
        _, content = self.adapter.adapt("Title", "Some content.")
        assert "转发" in content or "看法" in content

    def test_respects_max_length(self):
        content = "x" * 5000
        _, result = self.adapter.adapt("Title", content)
        assert len(result) <= self.adapter.max_length


class TestAdaptContent:
    """Test the adapt_content() dispatcher."""

    def test_dispatches_to_wechat(self):
        title, content = adapt_content("Title", "Content", "wechat")
        assert title == "Title"

    def test_dispatches_to_xiaohongshu(self):
        title, content = adapt_content("Title", "Content", "xiaohongshu")
        assert "💡" in title

    def test_dispatches_to_douyin(self):
        title, content = adapt_content("Title", "Content", "douyin")
        assert "🔥" in content

    def test_dispatches_to_weibo(self):
        title, content = adapt_content("Title", "Content", "weibo")
        assert "#" in content

    def test_fallback_for_unknown_platform(self):
        title, content = adapt_content("Title", "Content", "unknown_platform")
        assert title == "Title"
        assert content == "Content"

    def test_fallback_preserves_original_content(self):
        original = "Original content that should not be modified."
        _, content = adapt_content("Title", original, "nonexistent")
        assert content == original


class TestGetAdapter:
    """Test get_adapter() function."""

    def test_returns_wechat_adapter(self):
        adapter = get_adapter("wechat")
        assert adapter is not None
        assert adapter.name == "wechat"

    def test_returns_none_for_unknown(self):
        adapter = get_adapter("nonexistent")
        assert adapter is None

    def test_all_adapters_have_max_length(self):
        for platform in get_supported_platforms():
            adapter = get_adapter(platform)
            assert adapter.max_length > 0


class TestGetSupportedPlatforms:
    """Test get_supported_platforms() function."""

    def test_returns_list(self):
        platforms = get_supported_platforms()
        assert isinstance(platforms, list)

    def test_includes_major_platforms(self):
        platforms = get_supported_platforms()
        assert "wechat" in platforms
        assert "xiaohongshu" in platforms
        assert "douyin" in platforms
        assert "weibo" in platforms
