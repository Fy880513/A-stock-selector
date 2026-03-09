"""
选股追踪模块

记录每日选股结果，追踪持仓表现，统计选股准确率
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from data.fetcher import get_data_fetcher, DataFetcher
from data.storage import get_storage, Storage
from selector.scorer import StockScore
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TrackingRecord:
    """追踪记录"""
    select_date: str
    ts_code: str
    stock_name: str
    rank: int
    buy_price: float
    current_price: float
    change_pct: float
    holding_return: float
    is_out: bool  # 是否已出局
    out_reason: Optional[str]  # 出局原因
    track_date: Optional[str]  # 最后追踪日期


class PerformanceTracker:
    """选股表现追踪器"""

    def __init__(self):
        self.fetcher = get_data_fetcher()
        self.storage = get_storage()

    def track_selection(
        self,
        select_date: str,
        stocks: List[Dict],
    ) -> List[TrackingRecord]:
        """
        追踪选股表现

        Args:
            select_date: 选股日期
            stocks: 选股列表（包含 ts_code, stock_name, rank, buy_price 等）

        Returns:
            List[TrackingRecord]: 追踪记录
        """
        records = []

        for stock in stocks:
            ts_code = stock.get("ts_code", "")
            stock_name = stock.get("stock_name", "")
            rank = stock.get("rank", 0)
            buy_price = stock.get("buy_price", 0)

            if not ts_code or buy_price <= 0:
                continue

            # 获取当前价格
            price_data = self.fetcher.get_stock_prices(ts_code, count=1)
            current_price = price_data.iloc[0].get("close", buy_price) if not price_data.empty else buy_price

            # 计算收益率
            change_pct = (current_price - buy_price) / buy_price if buy_price > 0 else 0
            holding_return = change_pct

            # 检查是否出局（止损/止盈）
            is_out = False
            out_reason = None

            # 止损检查
            stop_loss = stock.get("stop_loss", buy_price * 0.92)
            if current_price <= stop_loss:
                is_out = True
                out_reason = "止损"

            # 止盈检查
            stop_profit = stock.get("stop_profit", buy_price * 1.2)
            if current_price >= stop_profit:
                is_out = True
                out_reason = "止盈"

            records.append(TrackingRecord(
                select_date=select_date,
                ts_code=ts_code,
                stock_name=stock_name,
                rank=rank,
                buy_price=buy_price,
                current_price=current_price,
                change_pct=change_pct,
                holding_return=holding_return,
                is_out=is_out,
                out_reason=out_reason,
                track_date=datetime.now().strftime("%Y%m%d"),
            ))

        return records

    def update_tracking(
        self,
        select_date: str,
    ) -> Dict[str, float]:
        """
        更新某次选股的表现

        Returns:
            dict: 表现统计
        """
        # 获取选股历史
        selection_df = self.storage.get_selection_history(select_date, select_date)

        if selection_df.empty:
            return {}

        stats = {
            "total_count": len(selection_df),
            "positive_count": 0,
            "negative_count": 0,
            "avg_return": 0,
            "best_return": 0,
            "worst_return": 0,
        }

        returns = []

        for _, row in selection_df.iterrows():
            ts_code = row.get("ts_code", "")
            buy_price = row.get("buy_price", 0)

            if not ts_code or buy_price <= 0:
                continue

            # 获取当前价格
            price_data = self.fetcher.get_stock_prices(ts_code, count=1)
            current_price = price_data.iloc[0].get("close", buy_price) if not price_data.empty else buy_price

            ret = (current_price - buy_price) / buy_price if buy_price > 0 else 0
            returns.append(ret)

            if ret > 0:
                stats["positive_count"] += 1
            else:
                stats["negative_count"] += 1

        if returns:
            stats["avg_return"] = sum(returns) / len(returns)
            stats["best_return"] = max(returns)
            stats["worst_return"] = min(returns)

        stats["win_rate"] = stats["positive_count"] / stats["total_count"] if stats["total_count"] > 0 else 0

        return stats

    def get_selection_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict:
        """
        获取选股统计

        Returns:
            dict: 统计数据
        """
        selection_df = self.storage.get_selection_history(start_date, end_date)

        if selection_df.empty:
            return {"message": "无数据"}

        stats = {
            "selection_count": len(selection_df["select_date"].unique()),
            "stock_count": len(selection_df),
            "avg_score": selection_df["total_score"].mean(),
            "top_stock": selection_df.loc[selection_df["total_score"].idxmax(), "stock_name"] if not selection_df.empty else "",
            "top_score": selection_df["total_score"].max(),
        }

        return stats

    def generate_tracking_report(
        self,
        select_date: str,
    ) -> str:
        """
        生成追踪报告

        Returns:
            str: 报告文本
        """
        stats = self.update_tracking(select_date)

        if not stats:
            return f"【选股追踪报告】\n日期：{select_date}\n无数据"

        report = f"""【选股追踪报告】
日期：{select_date}

选股数量：{stats.get('total_count', 0)}
上涨数量：{stats.get('positive_count', 0)}
下跌数量：{stats.get('negative_count', 0)}
胜率：{stats.get('win_rate', '.2%')}
平均收益：{stats.get('avg_return', '.2%')}
最高收益：{stats.get('best_return', '.2%')}
最低收益：{stats.get('worst_return', '.2%')}
"""
        return report


def create_tracker() -> PerformanceTracker:
    """创建追踪器实例"""
    return PerformanceTracker()
