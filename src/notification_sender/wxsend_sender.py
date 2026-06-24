# -*- coding: utf-8 -*-
"""
WxSend 发送提醒服务

职责：
1. 通过 wxpush Cloudflare Worker 的 /wxsend 接口发送微信消息
"""
import logging
from datetime import datetime
from typing import Optional

import requests

from src.config import Config


logger = logging.getLogger(__name__)

# WxSend Worker 是轻量 webhook；10 秒覆盖常见网络抖动，避免通知长时间阻塞主流程。
DEFAULT_WXSEND_TIMEOUT_SECONDS = 10
# Cloudflare Bot Fight Mode 可能拦截 python-requests 默认 UA；使用浏览器 UA 避免 1010 误杀。
DEFAULT_WXSEND_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class WxsendSender:
    def __init__(self, config: Config):
        """
        初始化 WxSend 配置

        Args:
            config: 配置对象
        """
        self._wxsend_url = getattr(config, "wxsend_url", None)
        self._wxsend_token = getattr(config, "wxsend_token", None)
        self._webhook_verify_ssl = getattr(config, "webhook_verify_ssl", True)

    def send_to_wxsend(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        推送消息到 wxpush Worker。

        wxsend API 格式：
        POST https://your-worker.workers.dev/wxsend
        Authorization: your_api_token
        {
            "title": "消息标题",
            "content": "消息内容"
        }

        Args:
            content: 消息内容（Markdown 格式）
            title: 消息标题（可选）

        Returns:
            是否发送成功
        """
        if not self._wxsend_url or not self._wxsend_token:
            logger.warning("WxSend URL 或 Token 未配置，跳过推送")
            return False

        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 股票分析报告 - {date_str}"

        endpoint = self._resolve_wxsend_endpoint(self._wxsend_url)
        payload = {
            "title": title,
            "content": content,
        }
        headers = {
            "Authorization": self._wxsend_token,
            "Content-Type": "application/json",
            "User-Agent": DEFAULT_WXSEND_USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=timeout_seconds or DEFAULT_WXSEND_TIMEOUT_SECONDS,
                verify=self._webhook_verify_ssl,
            )
            if 200 <= response.status_code < 300:
                if self._response_explicitly_failed(response):
                    return False
                logger.info("WxSend 消息发送成功")
                return True

            logger.error(f"WxSend 请求失败: HTTP {response.status_code}")
            return False
        except Exception as e:
            logger.error(f"发送 WxSend 消息失败: {e}")
            return False

    @staticmethod
    def _resolve_wxsend_endpoint(url: str) -> str:
        """将 Worker 根地址或完整 /wxsend 地址归一化为发送接口。"""
        normalized = str(url).strip().rstrip("/")
        if normalized.endswith("/wxsend"):
            return normalized
        return f"{normalized}/wxsend"

    @staticmethod
    def _response_explicitly_failed(response: requests.Response) -> bool:
        """识别常见 JSON 错误字段；未知 2xx body 按成功处理以兼容 Worker 返回。"""
        try:
            result = response.json()
        except ValueError:
            return False

        if not isinstance(result, dict):
            return False

        if result.get("ok") is False or result.get("success") is False:
            logger.error(f"WxSend 返回错误: {result}")
            return True

        code = result.get("code")
        if isinstance(code, int) and code not in (0, 200):
            logger.error(f"WxSend 返回错误: {result}")
            return True

        return False
