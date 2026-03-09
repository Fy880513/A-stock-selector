"""
综合评分器模块

整合基本面、技术面、资金面、热点面四个维度，计算综合得分
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from config.settings import STOCK_SELECTION_CONFIG
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StockScore:
    """股票得分数据结构"""
    ts_code: str
    stock_name: str
    total_score: float
    fundamental_score: float
    technical_score: float
    capital_flow_score: float
    hotspot_score: float
    signal_count: int  # 技术指标信号数量
    pass_threshold: bool  # 是否通过基本面门槛
    rank: int = 0  # 排名


class Scorer:
    """综合评分器"""

    def __init__(self):
        self.config = STOCK_SELECTION_CONFIG
        self.weights = self.config["weights"]

    def calculate_total_score(
        self,
        fundamental_score: float,
        technical_score: float,
        capital_flow_score: float,
        hotspot_score: float,
    ) -> float:
        """
        计算综合得分

        Returns:
            float: 综合得分 0-100
        """
        total = (
            fundamental_score * self.weights["fundamental"] +
            technical_score * self.weights["technical"] +
            capital_flow_score * self.weights["capital_flow"] +
            hotspot_score * self.weights["hotspot"]
        )
        return round(total, 2)

    def create_stock_score(
        self,
        ts_code: str,
        stock_name: str,
        fundamental_data: Dict[str, float],
        technical_data: Dict[str, float],
        capital_flow_data: Dict[str, float],
        hotspot_data: Dict[str, float],
    ) -> StockScore:
        """
        创建股票得分对象

        Args:
            ts_code: 股票代码
            stock_name: 股票名称
            fundamental_data: 基本面得分数据
            technical_data: 技术面得分数据
            capital_flow_data: 资金面得分数据
            hotspot_data: 热点面得分数据

        Returns:
            StockScore: 股票得分对象
        """
        fundamental_score = fundamental_data.get("fundamental_score", 50.0)
        technical_score = technical_data.get("technical_score", 50.0)
        capital_flow_score = capital_flow_data.get("capital_flow_score", 50.0)
        hotspot_score = hotspot_data.get("hotspot_score", 50.0)

        total_score = self.calculate_total_score(
            fundamental_score,
            technical_score,
            capital_flow_score,
            hotspot_score,
        )

        return StockScore(
            ts_code=ts_code,
            stock_name=stock_name,
            total_score=total_score,
            fundamental_score=round(fundamental_score, 2),
            technical_score=round(technical_score, 2),
            capital_flow_score=round(capital_flow_score, 2),
            hotspot_score=round(hotspot_score, 2),
            signal_count=technical_data.get("signal_count", 0),
            pass_threshold=fundamental_data.get("pass_threshold", False),
        )

    def rank_stocks(self, stocks: List[StockScore]) -> List[StockScore]:
        """
        对股票进行排名

        排名规则：
        1. 必须通过基本面门槛
        2. 技术面信号数量 >= 3
        3. 按综合得分排序

        Returns:
            List[StockScore]: 排名后的股票列表
        """
        # 筛选符合条件的股票
        qualified = [
            s for s in stocks
            if s.pass_threshold and s.signal_count >= 3
        ]

        # 按综合得分排序
        qualified.sort(key=lambda x: x.total_score, reverse=True)

        # 设置排名
        for i, stock in enumerate(qualified):
            stock.rank = i + 1

        return qualified

    def filter_stocks(
        self,
        stocks: List[StockScore],
        min_total_score: float = 60.0,
        min_signal_count: int = 3,
        top_n: Optional[int] = None,
    ) -> List[StockScore]:
        """
        筛选股票

        Args:
            stocks: 股票得分列表
            min_total_score: 最低综合得分
            min_signal_count: 最低技术信号数量
            top_n: 取前 N 只

        Returns:
            List[StockScore]: 筛选后的股票列表
        """
        # 筛选
        filtered = [
            s for s in stocks
            if s.total_score >= min_total_score
            and s.signal_count >= min_signal_count
            and s.pass_threshold
        ]

        # 排序
        filtered.sort(key=lambda x: x.total_score, reverse=True)

        # 取前 N 只
        if top_n:
            filtered = filtered[:top_n]

        return filtered

    def to_dataframe(self, stocks: List[StockScore]) -> pd.DataFrame:
        """将股票得分列表转换为 DataFrame"""
        if not stocks:
            return pd.DataFrame()

        data = []
        for s in stocks:
            data.append({
                "ts_code": s.ts_code,
                "stock_name": s.stock_name,
                "total_score": s.total_score,
                "fundamental_score": s.fundamental_score,
                "technical_score": s.technical_score,
                "capital_flow_score": s.capital_flow_score,
                "hotspot_score": s.hotspot_score,
                "signal_count": s.signal_count,
                "rank": s.rank,
            })

        return pd.DataFrame(data)


def create_scorer() -> Scorer:
    """创建评分器实例"""
    return Scorer()
