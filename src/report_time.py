# -*- coding: utf-8 -*-
"""Helpers for user-facing report display time."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


REPORT_DISPLAY_TIMEZONE = ZoneInfo("Asia/Shanghai")  # 报告面向中文用户与北京时间定时任务展示。


def report_now() -> datetime:
    """Return the current report display time in Beijing timezone."""
    return datetime.now(timezone.utc).astimezone(REPORT_DISPLAY_TIMEZONE)


def format_report_date() -> str:
    """Format the current report display date."""
    return report_now().strftime("%Y-%m-%d")


def format_report_timestamp(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format the current report display timestamp."""
    return report_now().strftime(fmt)
