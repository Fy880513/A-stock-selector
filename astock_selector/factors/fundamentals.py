"""
基本面因子计算模块

权重：25%
包含估值、成长、盈利、偿债能力等因子
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional

from config.settings import FUNDAMENTAL_THRESHOLDS
from utils.logger import get_logger
from utils.helpers import normalize_score

logger = get_logger(__name__)


class FundamentalFactor:
    """基本面因子计算器"""

    def __init__(self):
        self.thresholds = FUNDAMENTAL_THRESHOLDS

    def calculate_pe_score(self, pe_ttm: float) -> float:
        """
        PE 得分计算

        PE 在合理范围内得分高，过高或过低都扣分
        """
        if pe_ttm is None or pd.isna(pe_ttm) or pe_ttm <= 0:
            return 0.0

        min_pe = self.thresholds["pe_ttm_min"]
        max_pe = self.thresholds["pe_ttm_max"]

        if pe_ttm > max_pe:
            return 20.0  # PE 过高，低分
        elif pe_ttm < min_pe:
            return 30.0  # PE 为负或异常

        # 在合理范围内，越低分越高（估值便宜）
        # 但也要考虑成长性，这里简化处理
        score = normalize_score(pe_ttm, min_pe, max_pe, reverse=True)
        return score

    def calculate_peg_score(self, peg: float) -> float:
        """
        PEG 得分计算

        PEG 在 0.5-1 之间最优，1-2 之间可接受
        """
        if peg is None or pd.isna(peg) or peg <= 0:
            return 50.0  # 无数据给中等分数

        if peg < 0.5:
            return 100.0  # 可能被低估
        elif peg <= 1:
            return 90.0  # 估值合理
        elif peg <= 1.5:
            return 70.0  # 估值略高
        elif peg <= 2:
            return 50.0  # 估值偏高
        else:
            return 20.0  # 估值过高

    def calculate_growth_score(
        self,
        revenue_growth: float,
        net_profit_growth: float,
    ) -> float:
        """
        成长能力得分

        营收增长率和净利润增长率的综合评分
        """
        rev_min = self.thresholds["revenue_growth_min"]  # 15%
        profit_min = self.thresholds["net_profit_growth_min"]  # 20%

        # 处理空值
        if revenue_growth is None or pd.isna(revenue_growth):
            revenue_growth = 0
        if net_profit_growth is None or pd.isna(net_profit_growth):
            net_profit_growth = 0

        # 营收增长得分
        if revenue_growth >= 0.30:
            rev_score = 100
        elif revenue_growth >= rev_min:
            rev_score = 60 + 40 * (revenue_growth - rev_min) / (0.30 - rev_min)
        elif revenue_growth >= 0:
            rev_score = 30 + 30 * revenue_growth / rev_min
        else:
            rev_score = max(0, 30 + 30 * revenue_growth / rev_min)

        # 净利润增长得分
        if net_profit_growth >= 0.50:
            profit_score = 100
        elif net_profit_growth >= profit_min:
            profit_score = 60 + 40 * (net_profit_growth - profit_min) / (0.50 - profit_min)
        elif net_profit_growth >= 0:
            profit_score = 30 + 30 * net_profit_growth / profit_min
        else:
            profit_score = max(0, 30 + 30 * net_profit_growth / profit_min)

        # 加权平均（净利润增长更重要）
        return rev_score * 0.4 + profit_score * 0.6

    def calculate_profitability_score(
        self,
        roe: float,
        gross_margin: float,
        net_margin: Optional[float] = None,
    ) -> float:
        """
        盈利能力得分

        ROE 和毛利率的综合评分
        """
        roe_min = self.thresholds["roe_min"]  # 10%
        gross_min = self.thresholds["gross_margin_min"]  # 20%

        # 处理空值
        if roe is None or pd.isna(roe):
            roe = 0
        if gross_margin is None or pd.isna(gross_margin):
            gross_margin = 0

        # ROE 得分
        if roe >= 0.25:
            roe_score = 100
        elif roe >= roe_min:
            roe_score = 60 + 40 * (roe - roe_min) / (0.25 - roe_min)
        elif roe >= 0:
            roe_score = 30 * roe / roe_min
        else:
            roe_score = 0

        # 毛利率得分
        if gross_margin >= 0.50:
            gross_score = 100
        elif gross_margin >= gross_min:
            gross_score = 60 + 40 * (gross_margin - gross_min) / (0.50 - gross_min)
        elif gross_margin >= 0:
            gross_score = 30 * gross_margin / gross_min
        else:
            gross_score = 0

        # 净利率得分（如果有数据）
        if net_margin is not None and not pd.isna(net_margin):
            if net_margin >= 0.30:
                net_score = 100
            elif net_margin >= 0.15:
                net_score = 60 + 40 * (net_margin - 0.15) / 0.15
            elif net_margin >= 0:
                net_score = 30 * net_margin / 0.15
            else:
                net_score = 0
            # 三个指标平均
            return (roe_score + gross_score + net_score) / 3
        else:
            # 只有两个指标
            return (roe_score + gross_score) / 2

    def calculate_solvency_score(
        self,
        debt_to_asset: float,
        current_ratio: float,
    ) -> float:
        """
        偿债能力得分

        资产负债率越低越好，流动比率越高越好
        """
        debt_max = self.thresholds["debt_to_asset_max"]  # 60%
        current_min = self.thresholds["current_ratio_min"]  # 1.2

        # 处理空值
        if debt_to_asset is None or pd.isna(debt_to_asset):
            debt_to_asset = 0.5  # 默认中等水平
        if current_ratio is None or pd.isna(current_ratio):
            current_ratio = 1.0

        # 资产负债率得分（反向，越低越好）
        if debt_to_asset >= 0.8:
            debt_score = 0
        elif debt_to_asset >= debt_max:
            debt_score = 20 + 30 * (0.8 - debt_to_asset) / (0.8 - debt_max)
        else:
            debt_score = 50 + 50 * (debt_max - debt_to_asset) / debt_max

        # 流动比率得分
        if current_ratio >= 2:
            current_score = 100
        elif current_ratio >= current_min:
            current_score = 60 + 40 * (current_ratio - current_min) / (2 - current_min)
        elif current_ratio >= 0.8:
            current_score = 30 + 30 * (current_ratio - 0.8) / (current_min - 0.8)
        else:
            current_score = 0

        # 平均
        return (debt_score + current_score) / 2

    def calculate_composite_score(
        self,
        pe_ttm: float,
        peg: float,
        revenue_growth: float,
        net_profit_growth: float,
        roe: float,
        gross_margin: float,
        debt_to_asset: float,
        current_ratio: float,
        net_margin: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        计算基本面综合得分

        Returns:
            dict: 各维度得分和综合得分
        """
        # 各子维度得分
        pe_score = self.calculate_pe_score(pe_ttm)
        peg_score = self.calculate_peg_score(peg)
        valuation_score = (pe_score + peg_score) / 2

        growth_score = self.calculate_growth_score(revenue_growth, net_profit_growth)
        profit_score = self.calculate_profitability_score(roe, gross_margin, net_margin)
        solvency_score = self.calculate_solvency_score(debt_to_asset, current_ratio)

        # 综合得分（估值 30% + 成长 30% + 盈利 25% + 偿债 15%）
        composite = (
            valuation_score * 0.30 +
            growth_score * 0.30 +
            profit_score * 0.25 +
            solvency_score * 0.15
        )

        # 门槛检查（是否满足基本条件）
        pass_threshold = self._check_threshold(
            pe_ttm, peg, revenue_growth, net_profit_growth,
            roe, gross_margin, debt_to_asset, current_ratio
        )

        return {
            "valuation_score": valuation_score,
            "growth_score": growth_score,
            "profitability_score": profit_score,
            "solvency_score": solvency_score,
            "fundamental_score": composite,
            "pass_threshold": pass_threshold,
        }

    def _check_threshold(
        self,
        pe_ttm: float,
        peg: float,
        revenue_growth: float,
        net_profit_growth: float,
        roe: float,
        gross_margin: float,
        debt_to_asset: float,
        current_ratio: float,
    ) -> bool:
        """检查是否满足基本面门槛（60% 条件满足）"""
        conditions = [
            self.thresholds["pe_ttm_min"] < pe_ttm < self.thresholds["pe_ttm_max"] if pe_ttm and pe_ttm > 0 else False,
            self.thresholds["peg_min"] < peg < self.thresholds["peg_max"] if peg and peg > 0 else True,  # PEG 可选
            revenue_growth and revenue_growth > self.thresholds["revenue_growth_min"] if revenue_growth else False,
            net_profit_growth and net_profit_growth > self.thresholds["net_profit_growth_min"] if net_profit_growth else False,
            roe and roe > self.thresholds["roe_min"] if roe else False,
            gross_margin and gross_margin > self.thresholds["gross_margin_min"] if gross_margin else False,
            debt_to_asset and debt_to_asset < self.thresholds["debt_to_asset_max"] if debt_to_asset else True,
            current_ratio and current_ratio > self.thresholds["current_ratio_min"] if current_ratio else True,
        ]

        # 至少满足 60% 的条件
        return sum(conditions) >= len(conditions) * 0.6


def calculate_fundamental_score(
    pe_ttm: float,
    peg: float,
    revenue_growth: float,
    net_profit_growth: float,
    roe: float,
    gross_margin: float,
    debt_to_asset: float,
    current_ratio: float,
    net_margin: Optional[float] = None,
) -> Dict[str, float]:
    """计算基本面综合得分（便捷函数）"""
    factor = FundamentalFactor()
    return factor.calculate_composite_score(
        pe_ttm, peg, revenue_growth, net_profit_growth,
        roe, gross_margin, debt_to_asset, current_ratio, net_margin
    )
