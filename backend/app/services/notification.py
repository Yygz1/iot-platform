"""告警通知服务 — 支持钉钉/企业微信 Webhook + 邮件 SMTP"""

import asyncio
import json
import logging

import requests

logger = logging.getLogger(__name__)


async def send_notification(channel: str, config: dict, title: str, content: str) -> bool:
    """发送通知，根据渠道类型分发"""
    try:
        if channel == "dingtalk":
            return await _send_dingtalk(config.get("webhook_url", ""), title, content)
        elif channel == "wechat":
            return await _send_wechat(config.get("webhook_url", ""), title, content)
        elif channel == "email":
            return await _send_email(config, title, content)
        else:
            logger.error("未知通知渠道: %s", channel)
            return False
    except Exception as e:
        logger.exception("通知发送失败: %s", e)
        return False


async def _send_dingtalk(webhook_url: str, title: str, content: str) -> bool:
    """发送钉钉 Webhook 通知"""
    if not webhook_url:
        logger.error("钉钉 Webhook URL 为空")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": f"### {title}\n\n{content}",
        },
    }

    def _post():
        r = requests.post(webhook_url, json=payload, timeout=10)
        return r.status_code == 200 and r.json().get("errcode") == 0

    result = await asyncio.to_thread(_post)
    if result:
        logger.info("钉钉通知发送成功: %s", title)
    else:
        logger.error("钉钉通知发送失败")
    return result


async def _send_wechat(webhook_url: str, title: str, content: str) -> bool:
    """发送企业微信 Webhook 通知"""
    if not webhook_url:
        logger.error("企业微信 Webhook URL 为空")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"## {title}\n\n{content}",
        },
    }

    def _post():
        r = requests.post(webhook_url, json=payload, timeout=10)
        return r.status_code == 200 and r.json().get("errcode") == 0

    result = await asyncio.to_thread(_post)
    if result:
        logger.info("企业微信通知发送成功: %s", title)
    else:
        logger.error("企业微信通知发送失败")
    return result


async def _send_email(config: dict, title: str, content: str) -> bool:
    """发送邮件通知"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = config.get("smtp_host", "")
    smtp_port = config.get("smtp_port", 465)
    username = config.get("username", "")
    password = config.get("password", "")
    to_email = config.get("to_email", "")
    use_ssl = config.get("use_ssl", True)

    if not all([smtp_host, username, password, to_email]):
        logger.error("邮件配置不完整")
        return False

    def _send():
        msg = MIMEMultipart()
        msg["From"] = username
        msg["To"] = to_email
        msg["Subject"] = title

        # 将 markdown 格式转为简单 HTML
        html_content = content.replace("\n", "<br>")
        msg.attach(MIMEText(f"<h2>{title}</h2><p>{html_content}</p>", "html", "utf-8"))

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
        server.login(username, password)
        server.send_message(msg)
        server.quit()
        return True

    result = await asyncio.to_thread(_send)
    if result:
        logger.info("邮件通知发送成功: %s -> %s", title, to_email)
    else:
        logger.error("邮件通知发送失败")
    return result


def format_alert_message(device_name: str, device_id: str,
                         old_state: str, new_state: str,
                         trigger: str, trend_info: dict | None = None) -> tuple[str, str]:
    """格式化告警消息"""
    state_emoji = {"warning": "⚠️", "critical": "🚨"}.get(new_state, "📢")
    title = f"{state_emoji} IoT告警: {device_name} {old_state}→{new_state}"

    lines = [
        f"**设备**: {device_name} (`{device_id}`)",
        f"**状态**: {old_state} → **{new_state.upper()}**",
        f"**原因**: {trigger}",
    ]

    if trend_info:
        if trend_info.get("direction"):
            direction_cn = {"rising": "上升", "falling": "下降", "stable": "平稳"}.get(trend_info["direction"], "")
            lines.append(f"**趋势**: {direction_cn}（斜率 {trend_info.get('slope', '')}）")
        if trend_info.get("predicted"):
            lines.append(f"**预测值**: {trend_info['predicted']}")
        if trend_info.get("is_anomaly"):
            lines.append(f"**异常检测**: 当前值偏离历史均值，属于异常范围")

    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=8)))
    lines.append(f"**时间**: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    content = "\n\n".join(lines)
    return title, content
