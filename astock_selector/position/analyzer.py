"""
持仓分析器模块

对持仓股票进行分析，包括技术面、资金面等维度
复用 factors 模块的计算逻辑
"""
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from data.fetcher import get_data_fetcher
from factors.technicals import TechnicalFactor, calculate_technical_score
from factors.capital_flow import calculate_capital_flow_score
from selector.scorer import calculate_position_size
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class StockAnalysis:
    """个股分析结果"""
    ts_code: str
    stock_name: str
    volume: int
    cost_price: float
    current_price: float
    market_value: float
    profit: float
    profit_ratio: float

    # 技术指标
    technical_score: float
    ma_trend: str  # 多头/空头/震荡
    macd_status: str  # 金叉/死叉/中性
    kdj_status: str  # 超买/超卖/中性

    # 资金面
    capital_flow_score: float

    # 综合评分
    composite_score: float

    # 技术位
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    ma60: Optional[float] = None


class PositionAnalyzer:
    """持仓分析器"""

    def __init__(self):
        self.fetcher = get_data_fetcher()
        self.technical_factor = TechnicalFactor()

    def get_price_data(self, ts_code: str, count: int = 60) -> pd.DataFrame:
        """获取价格数据"""
        return self.fetcher.get_stock_prices(ts_code, count=count)

    def analyze_technical(self, price_data: pd.DataFrame) -> Dict[str, float]:
        """分析技术面"""
        if price_data is None or price_data.empty:
            return {"technical_score": 50.0}
        return calculate_technical_score(price_data)

    def analyze_capital_flow(self, ts_code: str) -> Dict[str, float]:
        """分析资金面"""
        # 简化版本，实际可以调用 AKShare 获取真实数据
        return calculate_capital_flow_score()

    def analyze_single_position(
        self,
        ts_code: str,
        stock_name: str,
        volume: int,
        cost_price: float,
        current_price: Optional[float] = None,
    ) -> Optional[StockAnalysis]:
        """
        分析单只持仓股

        Args:
            ts_code: 股票代码
            stock_name: 股票名称
            volume: 持股数量
            cost_price: 成本价
            current_price: 当前价（可选，从 API 获取）

        Returns:
            StockAnalysis: 分析结果
        """
        # 获取当前价格和行情数据
        if current_price is None:
            price_data = self.get_price_data(ts_code, count=1)
            if not price_data.empty:
                current_price = price_data.iloc[0].get("close", cost_price)
            else:
                current_price = cost_price

        # 计算盈亏
        market_value = current_price * volume
        profit = (current_price - cost_price) * volume
        profit_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0

        # 获取历史价格数据用于技术分析
        price_data = self.get_price_data(ts_code, count=60)

        # 技术面分析
        technical_data = self.analyze_technical(price_data)
        technical_score = technical_data.get("technical_score", 50.0)

        # 计算均线
        ma_data = self._calculate_ma(price_data)
        ma5 = ma_data.get("ma5")
        ma10 = ma_data.get("ma10")
        ma20 = ma_data.get("ma20")
        ma60 = ma_data.get("ma60")

        # 判断均线趋势
        ma_trend = self._judge_ma_trend(ma5, ma10, ma20, ma60, current_price)

        # MACD 状态
        macd_status = self._judge_macd(price_data)

        # KDJ 状态
        kdj_status = self._judge_kdj(price_data)

        # 资金面分析
        capital_flow_data = self.analyze_capital_flow(ts_code)
        capital_flow_score = capital_flow_data.get("capital_flow_score", 50.0)

        # 综合评分（技术面 60% + 资金面 40%）
        composite_score = technical_score * 0.6 + capital_flow_score * 0.4

        return StockAnalysis(
            ts_code=ts_code,
            stock_name=stock_name,
            volume=volume,
            cost_price=cost_price,
            current_price=current_price,
            market_value=market_value,
            profit=profit,
            profit_ratio=profit_ratio,
            technical_score=round(technical_score, 2),
            ma_trend=ma_trend,
            macd_status=macd_status,
            kdj_status=kdj_status,
            capital_flow_score=round(capital_flow_score, 2),
            composite_score=round(composite_score, 2),
            ma5=round(ma5, 2) if ma5 else None,
            ma10=round(ma10, 2) if ma10 else None,
            ma20=round(ma20, 2) if ma20 else None,
            ma60=round(ma60, 2) if ma60 else None,
        )

    def analyze_all_positions(
        self,
        positions: List[Dict],
    ) -> List[StockAnalysis]:
        """
        分析全部持仓

        Args:
            positions: 持仓列表，每项包含 ts_code, stock_name, volume, cost_price

        Returns:
            List[StockAnalysis]: 分析结果列表
        """
        results = []

        for pos in positions:
            ts_code = pos.get("ts_code", pos.get("证券代码", ""))
            stock_name = pos.get("stock_name", pos.get("证券名称", ""))
            volume = int(pos.get("volume", pos.get("股份余额", 0)))
            cost_price = float(pos.get("cost_price", pos.get("成本价", 0)))
            current_price = pos.get("current_price", pos.get("市价", None))

            if not ts_code:
                continue

            analysis = self.analyze_single_position(
                ts_code,
                stock_name,
                volume,
                cost_price,
                current_price,
            )

            if analysis:
                results.append(analysis)

        # 按综合得分排序
        results.sort(key=lambda x: x.composite_score, reverse=True)

        return results

    def _calculate_ma(self, df: pd.DataFrame) -> Dict[str, Optional[float]]:
        """计算均线"""
        if df is None or df.empty or len(df) < 60:
            return {"ma5": None, "ma10": None, "ma20": None, "ma60": None}

        try:
            close = df["close"]
            return {
                "ma5": close.rolling(5).mean().iloc[-1],
                "ma10": close.rolling(10).mean().iloc[-1],
                "ma20": close.rolling(20).mean().iloc[-1],
                "ma60": close.rolling(60).mean().iloc[-1],
            }
        except Exception:
            return {"ma5": None, "ma10": None, "ma20": None, "ma60": None}

    def _judge_ma_trend(
        self,
        ma5: Optional[float],
        ma10: Optional[float],
        ma20: Optional[float],
        ma60: Optional[float],
        current_price: float,
    ) -> str:
        """判断均线趋势"""
        if not all([ma5, ma10, ma20, ma60]):
            return "未知"

        # 多头排列
        if ma5 > ma10 > ma20 > ma60 and current_price > ma5:
            return "多头强势"
        elif ma5 > ma10 > ma20 and current_price > ma20:
            return "多头"
        elif ma5 < ma10 < ma20 < ma60 and current_price < ma5:
            return "空头弱势"
        elif ma5 < ma10 < ma20 and current_price < ma20:
            return "空头"
        else:
            return "震荡"

    def _judge_macd(self, df: pd.DataFrame) -> str:
        """判断 MACD 状态"""
        if df is None or df.empty or len(df) < 30:
            return "未知"

        try:
            # 计算 MACD
            fast, slow, signal = 12, 26, 9
            exp1 = df["close"].ewm(span=fast, adjust=False).mean()
            exp2 = df["close"].ewm(span=slow, adjust=False).mean()
            dif = exp1 - exp2
            dea = dif.ewm(span=signal, adjust=False).mean()
            macd_hist = (dif - dea) * 2

            latest_dif = dif.iloc[-1]
            latest_dea = dea.iloc[-1]
            latest_hist = macd_hist.iloc[-1]
            prev_hist = macd_hist.iloc[-2] if len(macd_hist) > 1 else latest_hist

            if latest_dif > 0 and latest_dea > 0:
                if latest_dif > latest_dea:
                    return "金叉 (零轴上方)"
                else:
                    return "死叉 (零轴上方)"
            elif latest_dif < 0 and latest_dea < 0:
                if latest_dif > latest_dea:
                    return "金叉 (零轴下方)"
                else:
                    return "死叉 (零轴下方)"
            else:
                return "穿越零轴"

        except Exception:
            return "未知"

    def _judge_kdj(self, df: pd.DataFrame) -> str:
        """判断 KDJ 状态"""
        if df is None or df.empty or len(df) < 10:
            return "未知"

        try:
            low_min = df["low"].rolling(9).min()
            high_max = df["high"].rolling(9).max()
            rsv = (df["close"] - low_min) / (high_max - low_min) * 100
            rsv = rsv.fillna(50)

            k = rsv.ewm(com=2, adjust=False).mean()
            d = k.ewm(com=2, adjust=False).mean()
            j = 3 * k - 2 * d

            latest_j = j.iloc[-1]

            if latest_j > 80:
                return "超买"
            elif latest_j < 20:
                return "超卖"
            else:
                return "中性"

        except Exception:
            return "未知"

    def generate_summary(self, analyses: List[StockAnalysis]) -> Dict:
        """
        生成持仓汇总

        Returns:
            dict: 汇总信息
        """
        if not analyses:
            return {}

        total_market_value = sum(a.market_value for a in analyses)
        total_profit = sum(a.profit for a in analyses)
        total_cost = total_market_value - total_profit

        # 持仓分布
        position_distribution = []
        for a in analyses:
            ratio = a.market_value / total_market_value if total_market_value > 0 else 0
            position_distribution.append({
                "ts_code": a.ts_code,
                "stock_name": a.stock_name,
                "market_value": a.market_value,
                "ratio": round(ratio, 2),
                "profit_ratio": a.profit_ratio,
            })

        # 按盈亏排序
        profit_ranking = sorted(
            position_distribution,
            key=lambda x: x["profit_ratio"],
            reverse=True,
        )

        # 技术面统计
        avg_technical_score = sum(a.technical_score for a in analyses) / len(analyses)
        strong_count = sum(1 for a in analyses if a.ma_trend in ["多头强势", "多头"])
        weak_count = sum(1 for a in analyses if a.ma_trend in ["空头弱势", "空头"])

        return {
            "total_market_value": round(total_market_value, 2),
            "total_profit": round(total_profit, 2),
            "total_profit_ratio": round(total_profit / total_cost, 4) if total_cost > 0 else 0,
            "position_count": len(analyses),
            "avg_technical_score": round(avg_technical_score, 2),
            "strong_count": strong_count,
            "weak_count": weak_count,
            "positions": position_distribution,
            "profit_ranking": profit_ranking,
        }


def create_position_analyzer() -> PositionAnalyzer:
    """创建持仓分析器实例"""
    return PositionAnalyzer()
