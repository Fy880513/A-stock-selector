"""
资金流向因子计算模块

权重：25%
包含主力资金、北向资金、龙虎榜、融资融券等因子
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from datetime import datetime, timedelta

from utils.logger import get_logger
from utils.helpers import normalize_score

logger = get_logger(__name__)


class CapitalFlowFactor:
    """资金流向因子计算器"""

    def __init__(self):
        pass

    def score_main_force_flow(
        self,
        net_inflows: List[float],
        prices: Optional[List[float]] = None,
    ) -> float:
        """
        主力资金流向得分

        Args:
            net_inflows: 近期主力净流入列表（最近 N 天）
            prices: 对应日期收盘价（用于背离分析）

        Returns:
            float: 得分 0-100
        """
        if not net_inflows or len(net_inflows) == 0:
            return 50.0

        score = 50.0

        # 反转顺序，让索引 0 表示最近一天
        net_inflows = list(reversed(net_inflows))[:10]  # 最近 10 天

        # 连续净流入
        consecutive_inflow = 0
        for inflow in net_inflows:
            if inflow > 0:
                consecutive_inflow += 1
            else:
                break

        if consecutive_inflow >= 5:
            score += 30
        elif consecutive_inflow >= 3:
            score += 20
        elif consecutive_inflow >= 1:
            score += 10

        # 净流入强度
        total_inflow = sum(net_inflows)
        avg_inflow = total_inflow / len(net_inflows)

        # 标准化处理（假设平均净流入超过 100 万为强）
        if avg_inflow > 1000000:  # 100 万
            score += 25
        elif avg_inflow > 500000:
            score += 15
        elif avg_inflow > 0:
            score += 5

        # 最近一天特大净流入
        if net_inflows[0] > 5000000:  # 500 万
            score += 15
        elif net_inflows[0] > 1000000:
            score += 10

        return min(100, max(0, score))

    def score_north_flow(
        self,
        hold_ratio: Optional[float] = None,
        hold_change: Optional[float] = None,
        consecutive_days: int = 0,
        north_hold_ratio: Optional[float] = None,
        north_hold_change: Optional[float] = None,
        north_continuous_days: int = 0,
    ) -> float:
        """
        北向资金得分（增强版）

        Args:
            hold_ratio: 北向资金持股比例（旧版参数，兼容用）
            hold_change: 持股比例变化（旧版参数，兼容用）
            consecutive_days: 连续增持天数（旧版参数，兼容用）
            north_hold_ratio: 北向资金持股比例（%）
            north_hold_change: 持股比例变化（百分点）
            north_continuous_days: 连续增持/减持天数

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 兼容旧版参数
        if north_hold_ratio is None:
            north_hold_ratio = hold_ratio
        if north_hold_change is None:
            north_hold_change = hold_change
        if north_continuous_days == 0:
            north_continuous_days = consecutive_days

        # 持股比例（代表北向资金认可度）
        if north_hold_ratio is not None and not np.isnan(north_hold_ratio):
            if north_hold_ratio > 5:
                score += 25  # 高持股比例，北向重仓
            elif north_hold_ratio > 3:
                score += 20
            elif north_hold_ratio > 1:
                score += 10

        # 持股变化（代表近期态度）
        if north_hold_change is not None and not np.isnan(north_hold_change):
            if north_hold_change > 0.5:  # 增持超过 0.5%
                score += 30  # 大幅增持
            elif north_hold_change > 0.2:
                score += 20
            elif north_hold_change > 0:
                score += 10
            elif north_hold_change < -0.5:
                score -= 25  # 大幅减持
            elif north_hold_change < -0.2:
                score -= 15

        # 连续增持/减持（代表趋势）
        if north_continuous_days >= 10:
            score += 25  # 连续 10 天以上
        elif north_continuous_days >= 5:
            score += 20
        elif north_continuous_days >= 3:
            score += 10
        elif north_continuous_days <= -10:
            score -= 25  # 连续 10 天以上减持
        elif north_continuous_days <= -5:
            score -= 15

        # 北向资金持股比例创 N 日新高（加分）
        # 这个数据需要在获取时计算，这里预留逻辑
        if north_hold_ratio is not None and north_hold_ratio > 3 and north_hold_change is not None and north_hold_change > 0:
            score += 10  # 高持股 + 增持，戴维斯双击

        return min(100, max(0, score))

    def score_lhb(
        self,
        lhb_count_5d: int = 0,
        net_buy: float = 0,
        has_institution: bool = False,
    ) -> float:
        """
        龙虎榜得分

        Args:
            lhb_count_5d: 近 5 日上榜次数
            net_buy: 净买入额（万元）
            has_institution: 是否有机构买入

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 上榜次数
        if lhb_count_5d >= 3:
            score += 10  # 频繁上榜
        elif lhb_count_5d >= 1:
            score += 5

        # 净买入
        if net_buy > 5000:  # 5000 万
            score += 25
        elif net_buy > 2000:
            score += 15
        elif net_buy > 1000:
            score += 10
        elif net_buy > 0:
            score += 5
        elif net_buy < -2000:
            score -= 15  # 大额净卖出

        # 机构买入
        if has_institution:
            score += 15

        return min(100, max(0, score))

    def score_margin_trading(
        self,
        margin_balance: Optional[float] = None,
        margin_change: Optional[float] = None,
        margin_ratio: Optional[float] = None,
    ) -> float:
        """
        融资融券得分

        Args:
            margin_balance: 融资余额（万元）
            margin_change: 融资余额变化
            margin_ratio: 融资余额占流通市值比

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 融资余额变化（代表短线情绪）
        if margin_change is not None and not np.isnan(margin_change):
            if margin_change > 5000:  # 增加 5000 万
                score += 25
            elif margin_change > 2000:
                score += 15
            elif margin_change > 0:
                score += 5
            elif margin_change < -3000:
                score -= 15

        # 融资比（过高有风险）
        if margin_ratio is not None and not np.isnan(margin_ratio):
            if 3 < margin_ratio < 10:
                score += 10  # 合理区间
            elif margin_ratio > 15:
                score -= 10  # 过高

        return min(100, max(0, score))

    def score_large_order(
        self,
        large_order_ratio: float,
        super_order_ratio: float,
    ) -> float:
        """
        大单流入得分

        Args:
            large_order_ratio: 大单占比（%）
            super_order_ratio: 超大单占比（%）

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 大单占比
        if large_order_ratio > 10:
            score += 20
        elif large_order_ratio > 5:
            score += 10
        elif large_order_ratio > 0:
            score += 5
        elif large_order_ratio < -5:
            score -= 15

        # 超大单占比
        if super_order_ratio > 5:
            score += 20
        elif super_order_ratio > 2:
            score += 10
        elif super_order_ratio > 0:
            score += 5

        return min(100, max(0, score))

    def calculate_composite_score(
        self,
        main_force_net_inflows: Optional[List[float]] = None,
        north_hold_ratio: Optional[float] = None,
        north_hold_change: Optional[float] = None,
        north_consecutive_days: int = 0,
        lhb_count_5d: int = 0,
        lhb_net_buy: float = 0,
        has_institution: bool = False,
        margin_change: Optional[float] = None,
        large_order_ratio: float = 0,
        super_order_ratio: float = 0,
    ) -> Dict[str, float]:
        """
        计算资金流向综合得分

        Returns:
            dict: 各维度得分和综合得分
        """
        # 各维度得分
        main_force_score = self.score_main_force_flow(
            main_force_net_inflows or []
        )

        north_score = self.score_north_flow(
            north_hold_ratio,
            north_hold_change,
            north_consecutive_days,
        )

        lhb_score = self.score_lhb(
            lhb_count_5d,
            lhb_net_buy,
            has_institution,
        )

        margin_score = self.score_margin_trading(
            margin_change=margin_change,
        )

        large_order_score = self.score_large_order(
            large_order_ratio,
            super_order_ratio,
        )

        # 综合得分（主力 30% + 北向 25% + 龙虎榜 20% + 大单 15% + 融资 10%）
        composite = (
            main_force_score * 0.30 +
            north_score * 0.25 +
            lhb_score * 0.20 +
            large_order_score * 0.15 +
            margin_score * 0.10
        )

        return {
            "main_force_score": main_force_score,
            "north_score": north_score,
            "lhb_score": lhb_score,
            "margin_score": margin_score,
            "large_order_score": large_order_score,
            "capital_flow_score": composite,
        }


def calculate_capital_flow_score(
    main_force_net_inflows: Optional[List[float]] = None,
    north_hold_ratio: Optional[float] = None,
    north_hold_change: Optional[float] = None,
    north_consecutive_days: int = 0,
    lhb_count_5d: int = 0,
    lhb_net_buy: float = 0,
    has_institution: bool = False,
    margin_change: Optional[float] = None,
    large_order_ratio: float = 0,
    super_order_ratio: float = 0,
) -> Dict[str, float]:
    """计算资金流向综合得分（便捷函数）"""
    factor = CapitalFlowFactor()
    return factor.calculate_composite_score(
        main_force_net_inflows,
        north_hold_ratio,
        north_hold_change,
        north_consecutive_days,
        lhb_count_5d,
        lhb_net_buy,
        has_institution,
        margin_change,
        large_order_ratio,
        super_order_ratio,
    )
