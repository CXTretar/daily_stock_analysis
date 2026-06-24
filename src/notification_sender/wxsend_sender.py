# -*- coding: utf-8 -*-
"""
WxSend 发送提醒服务

职责：
1. 通过 wxpush Cloudflare Worker 的 /wxsend 接口发送微信消息
"""
import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional

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
# 响应摘要仅用于定位 Worker 403 / 业务错误；限制长度避免日志写入大段 HTML 或报告正文。
WXSEND_RESPONSE_SUMMARY_MAX_CHARS = 500
# Token 指纹用于跨 GitHub Secret / Worker 配置比对；12 位足够排障且不泄露完整凭证。
WXSEND_TOKEN_FINGERPRINT_CHARS = 12
# Worker 错误响应可能回显请求字段，常见密钥字段统一脱敏，避免泄露通知凭证。
WXSEND_SENSITIVE_RESPONSE_KEYS = frozenset(
    {
        "token",
        "authorization",
        "access_token",
        "api_key",
        "apikey",
        "key",
        "secret",
        "sendkey",
        "password",
    }
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

            logger.error(
                "WxSend 请求失败: HTTP %s, response=%s, token_diag=%s",
                response.status_code,
                self._response_summary(response),
                self._token_diagnostic_summary(),
            )
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

    def _response_explicitly_failed(self, response: requests.Response) -> bool:
        """识别常见 JSON 错误字段；未知 2xx body 按成功处理以兼容 Worker 返回。"""
        try:
            result = response.json()
        except ValueError:
            return False

        if not isinstance(result, dict):
            return False

        if result.get("ok") is False or result.get("success") is False:
            logger.error(
                "WxSend 返回错误: %s, token_diag=%s",
                self._response_summary(response, parsed=result),
                self._token_diagnostic_summary(),
            )
            return True

        code = result.get("code")
        if isinstance(code, int) and code not in (0, 200):
            logger.error(
                "WxSend 返回错误: %s, token_diag=%s",
                self._response_summary(response, parsed=result),
                self._token_diagnostic_summary(),
            )
            return True

        return False

    def _token_diagnostic_summary(self) -> str:
        """输出不可逆 token 指纹和格式特征，用于定位 GitHub Secret 与 Worker token 不一致。"""
        token = str(self._wxsend_token or "")
        stripped = token.strip()
        fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()[:WXSEND_TOKEN_FINGERPRINT_CHARS]
        return (
            f"len={len(token)}, stripped_len={len(stripped)}, "
            f"has_bearer_prefix={token.startswith('Bearer ')}, "
            f"has_surrounding_whitespace={token != stripped}, "
            f"sha256_12={fingerprint}"
        )

    @staticmethod
    def _response_summary(response: requests.Response, *, parsed: Optional[Any] = None) -> str:
        """生成脱敏、截断后的响应摘要，便于排查 Worker 拒绝原因。"""
        body: Any
        if parsed is not None:
            body = parsed
        else:
            try:
                body = response.json()
            except ValueError:
                body = getattr(response, "text", "")

        if isinstance(body, (dict, list)):
            safe_body = WxsendSender._sanitize_response_body(body)
            summary = json.dumps(safe_body, ensure_ascii=False, sort_keys=True)
        else:
            summary = str(body)

        if len(summary) > WXSEND_RESPONSE_SUMMARY_MAX_CHARS:
            return f"{summary[:WXSEND_RESPONSE_SUMMARY_MAX_CHARS]}...(truncated)"
        return summary

    @staticmethod
    def _sanitize_response_body(body: Any) -> Any:
        """递归脱敏 Worker 响应中的常见凭证字段。"""
        if isinstance(body, dict):
            sanitized = {}
            for key, value in body.items():
                if str(key).lower() in WXSEND_SENSITIVE_RESPONSE_KEYS:
                    sanitized[key] = "******"
                else:
                    sanitized[key] = WxsendSender._sanitize_response_body(value)
            return sanitized
        if isinstance(body, list):
            return [WxsendSender._sanitize_response_body(item) for item in body]
        return body
