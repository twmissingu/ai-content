"""Feishu (Lark) webhook notification module.

Sends alerts to Feishu group chat via webhook.
Used by watchdog, budget monitor, and error handlers.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import PROJECT_ROOT

logger = logging.getLogger("gaoding.feishu")


def _get_webhook_url() -> str:
    """Get Feishu webhook URL from environment (read at call time, not import)."""
    return os.getenv("FEISHU_WEBHOOK_URL", "")


def send_feishu_alert(title: str, content: str, level: str = "info") -> bool:
    """Send alert to Feishu via webhook.

    Args:
        title: Alert title
        content: Alert content (supports markdown)
        level: Alert level (info, warning, error)

    Returns:
        True if sent successfully, False otherwise
    """
    webhook_url = _get_webhook_url()
    if not webhook_url:
        logger.info(f"No webhook configured. Alert: {title}")
        return False

    color_map = {"info": "blue", "warning": "orange", "error": "red"}
    emoji_map = {"info": "ℹ️", "warning": "⚠️", "error": "🚨"}

    color = color_map.get(level, "blue")
    emoji = emoji_map.get(level, "ℹ️")

    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"{emoji} {title}"},
                "template": color,
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"稿定 AI 内容系统 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
                        }
                    ],
                },
            ],
        },
    }

    try:
        import urllib.request

        data = json.dumps(card).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("code") == 0 or result.get("StatusCode") == 0:
                logger.info(f"Alert sent: {title}")
                return True
            else:
                logger.warning(f"Failed to send alert: {result}")
                return False

    except Exception as e:
        logger.error(f"Error sending alert: {e}")
        return False


def send_text_message(text: str) -> bool:
    """Send simple text message to Feishu."""
    webhook_url = _get_webhook_url()
    if not webhook_url:
        logger.info(f"No webhook configured. Message: {text}")
        return False

    payload = {"msg_type": "text", "content": {"text": text}}

    try:
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result.get("code") == 0 or result.get("StatusCode") == 0

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


# ── Convenience functions ──────────────────────────────────────────


def alert_agent_timeout(agent_name: str, duration_minutes: int):
    """Alert when an agent times out."""
    send_feishu_alert(
        title="Agent 超时告警",
        content=f"**{agent_name}** 已运行超过 {duration_minutes} 分钟，可能已卡死。\n\n请检查 Dashboard 管线状态。",
        level="warning",
    )


def alert_agent_error(agent_name: str, error_message: str):
    """Alert when an agent encounters an error."""
    send_feishu_alert(
        title="Agent 错误告警",
        content=f"**{agent_name}** 执行失败：\n\n```\n{error_message[:500]}\n```",
        level="error",
    )


def alert_budget_warning(current_cost: float, budget: float, percentage: float):
    """Alert when budget usage exceeds threshold."""
    send_feishu_alert(
        title="成本预警",
        content=f"本月已消耗 **${current_cost:.2f}** / ${budget:.2f} ({percentage:.1f}%)\n\n"
        f"{'⚠️ 接近上限' if percentage < 100 else '🚨 已达上限，管线已暂停'}",
        level="warning" if percentage < 100 else "error",
    )


def alert_service_down(service_name: str):
    """Alert when a service is down."""
    send_feishu_alert(
        title="服务宕机告警",
        content=f"**{service_name}** 已停止运行，正在尝试自动重启。",
        level="error",
    )


def alert_publish_success(topic: str, platforms: list[str]):
    """Notify when content is published successfully."""
    platform_str = ", ".join(platforms)
    send_feishu_alert(
        title="发布成功",
        content=f"**{topic}**\n\n已成功发布到：{platform_str}",
        level="info",
    )


def alert_approval_needed(topic: str, quality_score: int):
    """Notify when new content needs approval."""
    send_feishu_alert(
        title="新文章待审批",
        content=f"**{topic}**\n\n质量分：{quality_score}\n\n[打开 Dashboard 查看详情]",
        level="info",
    )


def test_webhook():
    """Test Feishu webhook connection."""
    return send_feishu_alert(
        title="连接测试",
        content="✅ 飞书 Webhook 连接正常！\n\n此消息由稿定 AI 内容系统发送。",
        level="info",
    )


if __name__ == "__main__":
    if test_webhook():
        print("Webhook test successful!")
    else:
        print("Webhook test failed or not configured.")
