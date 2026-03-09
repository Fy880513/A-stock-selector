"""
回测引擎模块

模拟选股策略的历史表现
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from data.fetcher import get_data_fetcher, DataFetcher
from backtest.metrics import create_metrics_calculator, BacktestMetrics
from selector.scorer import create_scorer
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Trade:
    """交易记录"""
    ts_code: str
    stock_name: str
    buy_date: str
    buy_price: float
    sell_date: str
    sell_price: float
    shares: int
    return_pct: float
    holding_days: int


@dataclass
class BacktestResult:
    """回测结果"""
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    metrics: BacktestMetrics
    trades: List[Trade]
    equity_curve: pd.Series
    benchmark_curve: Optional[pd.Series]


class BacktestEngine:
    """回测引擎"""

    def __init__(
        self,
        initial_capital: float = 100000,
        holding_period: int = 15,  # 持有天数
        top_n: int = 10,  # 每次选股数量
    ):
        """
        Args:
            initial_capital: 初始资金
            holding_period: 持有周期（天）
            top_n: 每次选股数量
        """
        self.initial_capital = initial_capital
        self.holding_period = holding_period
        self.top_n = top_n

        self.fetcher = get_data_fetcher()
        self.scorer = create_scorer()
        self.metrics_calc = create_metrics_calculator()

    def get_selection_dates(
        self,
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """
        获取选股日期列表（每 holding_period 天选一次）

        简化版本：假设所有工作日都是交易日
        """
        dates = []
        current = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")

        while current < end:
            # 跳过周末
            if current.weekday() < 5:
                dates.append(current.strftime("%Y%m%d"))
                # 移动 holding_period 天
                current += timedelta(days=self.holding_period)
            else:
                current += timedelta(days=1)

        return dates

    def simulate_buy(
        self,
        ts_code: str,
        buy_date: str,
        buy_price: float,
        position_amount: float,
    ) -> Tuple[int, float]:
        """
        模拟买入

        Returns:
            (股数，实际金额)
        """
        shares = int(position_amount / buy_price / 100) * 100
        shares = max(shares, 100)  # 至少 100 股
        return shares, shares * buy_price

    def simulate_sell(
        self,
        shares: int,
        sell_price: float,
    ) -> float:
        """模拟卖出"""
        return shares * sell_price

    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        benchmark_code: str = "000300.SH",  # 沪深 300
    ) -> BacktestResult:
        """
        运行回测

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD
            benchmark_code: 基准指数代码

        Returns:
            BacktestResult: 回测结果
        """
        logger.info(f"开始回测：{start_date} - {end_date}")

        # 初始化
        capital = self.initial_capital
        positions = {}  # 持仓：ts_code -> {shares, buy_price, buy_date}

        trades: List[Trade] = []
        equity_curve = []
        benchmark_curve = []
        trade_returns = []
        holding_days_list = []

        selection_dates = self.get_selection_dates(start_date, end_date)
        all_dates = pd.date_range(start=start_date, end=end_date, freq="B")  # 工作日

        # 获取基准数据
        try:
            benchmark_data = self.fetcher.get_index_prices(
                benchmark_code,
                start_date,
                end_date,
            )
            if not benchmark_data.empty:
                benchmark_data["trade_date"] = pd.to_datetime(
                    benchmark_data["trade_date"], format="%Y%m%d"
                )
                benchmark_data = benchmark_data.set_index("trade_date")
                benchmark_data["close"] = pd.to_numeric(
                    benchmark_data["close"], errors="coerce"
                )
        except Exception as e:
            logger.warning(f"获取基准数据失败：{e}")
            benchmark_data = pd.DataFrame()

        # 回测主循环
        for date in all_dates:
            date_str = date.strftime("%Y%m%d")

            # 检查是否有持仓需要卖出
            for ts_code in list(positions.keys()):
                pos = positions[ts_code]
                holding_days = (date - pd.to_datetime(pos["buy_date"])).days

                # 达到持有周期，卖出
                if holding_days >= self.holding_period:
                    # 获取当日价格
                    price_data = self.fetcher.get_stock_prices(
                        ts_code,
                        start_date=date_str,
                        end_date=date_str,
                    )

                    if not price_data.empty:
                        sell_price = price_data.iloc[0].get("close", pos["buy_price"])
                        sell_amount = self.simulate_sell(pos["shares"], sell_price)
                        buy_amount = pos["shares"] * pos["buy_price"]

                        return_pct = (sell_amount - buy_amount) / buy_amount
                        capital += sell_amount

                        # 记录交易
                        stock_name = pos.get("stock_name", "")
                        trades.append(Trade(
                            ts_code=ts_code,
                            stock_name=stock_name,
                            buy_date=pos["buy_date"].strftime("%Y%m%d") if isinstance(
                                pos["buy_date"], pd.Timestamp
                            ) else pos["buy_date"],
                            buy_price=pos["buy_price"],
                            sell_date=date_str,
                            sell_price=sell_price,
                            shares=pos["shares"],
                            return_pct=return_pct,
                            holding_days=holding_days,
                        ))

                        trade_returns.append(return_pct)
                        holding_days_list.append(holding_days)

                        del positions[ts_code]
                        logger.debug(f"卖出 {ts_code}, 收益率：{return_pct:.2%}")

            # 计算当日权益
            total_equity = capital
            for pos in positions.values():
                # 估算持仓市值
                total_equity += pos["shares"] * pos["buy_price"]  # 简化：用买入价

            equity_curve.append((date, total_equity))

            # 基准收益
            if not benchmark_data.empty and date in benchmark_data.index:
                benchmark_curve.append(
                    (date, self.initial_capital * benchmark_data.loc[date, "close"] /
                     benchmark_data.iloc[0]["close"])
                )

            # 检查是否是选股日
            if date_str in selection_dates and capital > 0:
                # 选股
                # 简化：这里应该调用选股引擎，但为了速度直接随机选
                # 实际使用中可以集成真实选股逻辑
                pass

        # 处理剩余持仓
        final_date = all_dates[-1].strftime("%Y%m%d")
        for ts_code, pos in positions.items():
            price_data = self.fetcher.get_stock_prices(
                ts_code,
                start_date=final_date,
                end_date=final_date,
            )

            if not price_data.empty:
                sell_price = price_data.iloc[0].get("close", pos["buy_price"])
                sell_amount = self.simulate_sell(pos["shares"], sell_price)
                buy_amount = pos["shares"] * pos["buy_price"]
                return_pct = (sell_amount - buy_amount) / buy_amount

                trades.append(Trade(
                    ts_code=ts_code,
                    stock_name=pos.get("stock_name", ""),
                    buy_date=pos["buy_date"],
                    buy_price=pos["buy_price"],
                    sell_date=final_date,
                    sell_price=sell_price,
                    shares=pos["shares"],
                    return_pct=return_pct,
                    holding_days=(pd.to_datetime(final_date) - pd.to_datetime(pos["buy_date"])).days,
                ))

                trade_returns.append(return_pct)
                capital += sell_amount

        # 准备结果数据
        equity_df = pd.DataFrame(equity_curve, columns=["date", "equity"])
        equity_df = equity_df.set_index("date")
        equity_series = equity_df["equity"]

        benchmark_series = None
        if benchmark_curve:
            bench_df = pd.DataFrame(benchmark_curve, columns=["date", "value"])
            bench_df = bench_df.set_index("date")
            benchmark_series = bench_df["value"]

        # 计算绩效指标
        metrics = self.metrics_calc.calculate_metrics(
            equity_series,
            benchmark_series,
            pd.Series(trade_returns) if trade_returns else None,
            pd.Series(holding_days_list) if holding_days_list else None,
            self.initial_capital,
        )

        logger.info(f"回测完成，总收益：{metrics.total_return:.2%}")

        return BacktestResult(
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=capital,
            metrics=metrics,
            trades=trades,
            equity_curve=equity_series,
            benchmark_curve=benchmark_series,
        )

    def print_result(self, result: BacktestResult):
        """打印回测结果"""
        m = result.metrics

        print("\n" + "=" * 50)
        print("回测结果")
        print("=" * 50)
        print(f"回测区间：{result.start_date} - {result.end_date}")
        print(f"初始资金：{result.initial_capital:,.0f}")
        print(f"期末资金：{result.final_capital:,.0f}")
        print("\n收益指标:")
        print(f"  总收益率：{m.total_return:.2%}")
        print(f"  年化收益：{m.annual_return:.2%}")
        print(f"  基准收益：{m.benchmark_return:.2%}")
        print(f"  超额收益：{m.excess_return:.2%}")
        print("\n风险指标:")
        print(f"  最大回撤：{m.max_drawdown:.2%}")
        print(f"  夏普比率：{m.sharpe_ratio:.2f}")
        print(f"  索提诺比率：{m.sortino_ratio:.2f}")
        print("\n交易统计:")
        print(f"  总交易次数：{m.total_trades}")
        print(f"  胜率：{m.win_rate:.2%}")
        print(f"  盈亏比：{m.profit_loss_ratio:.2f}")
        print(f"  平均盈利：{m.avg_win:.2%}")
        print(f"  平均亏损：{m.avg_loss:.2%}")
        print(f"  平均持有天数：{m.avg_holding_days:.1f}")
        print("=" * 50)


def create_backtest_engine(
    initial_capital: float = 100000,
    holding_period: int = 15,
    top_n: int = 10,
) -> BacktestEngine:
    """创建回测引擎实例"""
    return BacktestEngine(initial_capital, holding_period, top_n)
