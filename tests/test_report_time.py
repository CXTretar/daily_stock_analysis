# -*- coding: utf-8 -*-
"""Tests for user-facing report display time helpers."""
from datetime import datetime, timezone
import unittest
from unittest import mock

from src.report_time import format_report_date, format_report_timestamp


class TestReportTime(unittest.TestCase):
    """Report display time tests."""

    def test_report_timestamp_uses_beijing_time_when_runtime_is_utc(self) -> None:
        """报告展示时间固定转换为北京时间。"""
        with mock.patch("src.report_time.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 18, 7, 47, 3, tzinfo=timezone.utc)

            self.assertEqual(format_report_timestamp(), "2026-06-18 15:47:03")

    def test_report_date_uses_beijing_day_boundary(self) -> None:
        """报告日期按北京时间跨日，避免 UTC 环境显示前一天。"""
        with mock.patch("src.report_time.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 6, 17, 16, 1, 0, tzinfo=timezone.utc)

            self.assertEqual(format_report_date(), "2026-06-18")
