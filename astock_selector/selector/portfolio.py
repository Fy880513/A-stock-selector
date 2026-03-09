"""
仓位管理模块

根据资金规模和股票价格，计算建议仓位
"""
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass

from config.settings import STOCK_SELECTION_CONFIG
from utils.logger import get_logger
from utils.helpers import calculate_position_size as calc_pos

logger = get_logger(__name__)


@dataclass
class PositionInfo:
    """仓位信息"""
    ts_code: str
    stock_name: str
    buy_price: float
    target_shares: int  # 目标股数
    target_amount: float  # 目标金额
    stop_loss_price: float  # 止损价
    stop_profit_price: float  # 止盈价
    position_ratio: float  # 仓位占比


class PortfolioManager:
    """仓位管理器"""

    def __init__(self, total_capital: Optional[float] = None):
        self.config = STOCK_SELECTION_CONFIG
        self.total_capital = total_capital or self.config["total_capital"]
        self.min_position = self.config["min_position_per_stock"]
        self.max_position = self.config["max_position_per_stock"]

    def calculate_position(
        self,
        stock_price: float,
        position_ratio: Optional[float] = None,
    ) -> tuple[int, float]:
        """
        计算单只股票的仓位

        Args:
            stock_price: 股票价格
            position_ratio: 目标仓位比例（可选）

        Returns:
            (股数，金额)
        """
        if position_ratio:
            target_amount = self.total_capital * position_ratio
        else:
            # 默认均匀分配
            target_amount = (self.min_position + self.max_position) / 2

        # 计算股数（100 股的整数倍）
        shares = int(target_amount / stock_price / 100) * 100

        # 确保在最小和最大仓位之间
        if shares * stock_price < self.min_position:
            shares = int(self.min_position / stock_price / 100) * 100
        elif shares * stock_price > self.max_position:
            shares = int(self.max_position / stock_price / 100) * 100

        shares = max(shares, 100)  # 至少 100 股
        return shares, shares * stock_price

    def calculate_stop_loss(
        self,
        buy_price: float,
        ma20: Optional[float] = None,
        ma60: Optional[float] = None,
        stop_loss_ratio: float = 0.08,
    ) -> float:
        """
        计算止损价

        规则：
        - 跌破 MA20 减仓 50%
        - 跌破 MA60 或亏损 8% 清仓

        Returns:
            float: 止损价
        """
        # 固定比例止损
        fixed_stop = buy_price * (1 - stop_loss_ratio)

        # 技术位止损
        if ma60:
            tech_stop = ma60 * 0.98  # 留 2% 缓冲
        elif ma20:
            tech_stop = ma20 * 0.95
        else:
            tech_stop = fixed_stop

        # 取较高的止损位（更严格）
        return max(fixed_stop, tech_stop)

    def calculate_stop_profit(
        self,
        buy_price: float,
        stop_profit_ratio: float = 0.20,
    ) -> float:
        """
        计算止盈价

        规则：
        - 涨幅 20% 减仓 50%
        - 涨幅 30% 且顶背离清仓
        - 从最高点回撤 10% 清仓（移动止盈）

        Returns:
            float: 第一目标止盈价
        """
        return buy_price * (1 + stop_profit_ratio)

    def calculate_positions(
        self,
        stocks: List[Dict],
    ) -> List[PositionInfo]:
        """
        计算多只股票的仓位

        Args:
            stocks: 股票列表，每项包含 ts_code, stock_name, close_price 等

        Returns:
            List[PositionInfo]: 仓位信息列表
        """
        positions = []

        # 计算每只股票的仓位
        for stock in stocks:
            ts_code = stock.get("ts_code", "")
            stock_name = stock.get("stock_name", "")
            close_price = stock.get("close_price", stock.get("buy_price", 0))
            ma20 = stock.get("ma20")
            ma60 = stock.get("ma60")

            if close_price <= 0:
                continue

            shares, amount = self.calculate_position(close_price)
            stop_loss = self.calculate_stop_loss(close_price, ma20, ma60)
            stop_profit = self.calculate_stop_profit(close_price)

            positions.append(PositionInfo(
                ts_code=ts_code,
                stock_name=stock_name,
                buy_price=close_price,
                target_shares=shares,
                target_amount=amount,
                stop_loss_price=round(stop_loss, 2),
                stop_profit_price=round(stop_profit, 2),
                position_ratio=amount / self.total_capital,
            ))

        return positions

    def generate_position_report(
        self,
        positions: List[PositionInfo],
    ) -> Dict:
        """
        生成仓位报告

        Returns:
            dict: 仓位汇总信息
        """
        if not positions:
            return {
                "total_amount": 0,
                "used_ratio": 0,
                "remaining": self.total_capital,
                "positions": [],
            }

        total_amount = sum(p.target_amount for p in positions)

        report = {
            "total_amount": round(total_amount, 2),
            "used_ratio": round(total_amount / self.total_capital, 2),
            "remaining": round(self.total_capital - total_amount, 2),
            "position_count": len(positions),
            "positions": [
                {
                    "ts_code": p.ts_code,
                    "stock_name": p.stock_name,
                    "buy_price": p.buy_price,
                    "target_shares": p.target_shares,
                    "target_amount": p.target_amount,
                    "stop_loss": p.stop_loss_price,
                    "stop_profit": p.stop_profit_price,
                    "position_ratio": round(p.position_ratio * 100, 1),
                }
                for p in positions
            ],
        }

        return report

    def adjust_position(
        self,
        current_price: float,
        highest_price: float,
        buy_price: float,
        stop_loss: float,
        stop_profit: float,
    ) -> str:
        """
        根据当前价格给出仓位调整建议

        Returns:
            str: 操作建议
        """
        change_pct = (current_price - buy_price) / buy_price

        # 止损检查
        if current_price <= stop_loss:
            return "清仓止损"

        # 移动止盈检查
        if highest_price > buy_price * 1.2:  # 曾经涨过 20%
            trail_stop = highest_price * 0.9  # 从最高点回撤 10%
            if current_price <= trail_stop:
                return "清仓（移动止盈）"

        # 止盈检查
        if current_price >= stop_profit:
            return "减仓 50%（达到止盈位）"

        # 大幅上涨
        if change_pct > 0.3:
            return "持有，设置移动止盈"
        elif change_pct > 0.1:
            return "持有"
        elif change_pct > 0:
            return "持有观察"
        elif change_pct > -0.05:
            return "持有观察"
        else:
            return "接近止损位，注意风险"


def create_portfolio_manager(total_capital: Optional[float] = None) -> PortfolioManager:
    """创建仓位管理器实例"""
    return PortfolioManager(total_capital)
