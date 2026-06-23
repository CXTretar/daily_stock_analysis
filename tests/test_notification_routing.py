# -*- coding: utf-8 -*-
"""Tests for notification route channel parsing."""

from src.notification_routing import ROUTABLE_NOTIFICATION_CHANNELS, split_notification_route_channels


def test_ntfy_gotify_and_wxsend_are_routable_notification_channels() -> None:
    valid, invalid = split_notification_route_channels(["wechat", "ntfy", "gotify", "wxsend", "not-a-channel"])

    assert "ntfy" in ROUTABLE_NOTIFICATION_CHANNELS
    assert "gotify" in ROUTABLE_NOTIFICATION_CHANNELS
    assert "wxsend" in ROUTABLE_NOTIFICATION_CHANNELS
    assert valid == ["wechat", "ntfy", "gotify", "wxsend"]
    assert invalid == ["not-a-channel"]
