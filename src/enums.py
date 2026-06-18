# -*- coding: utf-8 -*-
"""
===================================
枚举类型定义
===================================

集中管理系统中使用的枚举类型，提供类型安全和代码可读性。
"""

from enum import Enum


class ReportType(str, Enum):
    """
    报告类型枚举

    用于 API 触发分析时选择推送的报告格式。
    继承 str 使其可以直接与字符串比较和序列化。
    """
    SIMPLE = "simple"  # 短卡片推荐：默认推送格式
    FULL = "full"      # 完整仪表盘：使用 generate_dashboard_report
    BRIEF = "brief"    # 每股一行概括，适合移动端/推送

    @classmethod
    def from_str(cls, value: str) -> "ReportType":
        """
        从字符串安全地转换为枚举值
        
        Args:
            value: 字符串值
            
        Returns:
            对应的枚举值，无效输入返回默认值 SIMPLE
        """
        try:
            normalized = value.lower().strip()
            if normalized == "detailed":
                normalized = cls.FULL.value
            return cls(normalized)
        except (ValueError, AttributeError):
            return cls.SIMPLE
    
    @property
    def display_name(self) -> str:
        """获取用于显示的名称"""
        return {
            ReportType.SIMPLE: "短卡片推荐",
            ReportType.FULL: "完整仪表盘",
            ReportType.BRIEF: "每股一行概括",
        }.get(self, "短卡片推荐")
