"""
回测引擎模块

模拟选股策略的历史表现
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass

from data.fetcher import get_data_fetcher, DataFetcher
from backtest.metrics import create_metrics_calculator, BacktestMetrics
from selector.scorer import create_scorer
from selector.screener import get_screener
from strategies.dragon_strategy import create_dragon_strategy
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
    position_ratio: float  # 仓位比例


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
    sector_performance: Dict[str, float]  # 行业表现
    best_trades: List[Trade]  # 最佳交易
    worst_trades: List[Trade]  # 最差交易


class BacktestEngine:
    """回测引擎"""

    def __init__(
        self,
        initial_capital: float = 100000,
        holding_period: int = 15,  # 持有天数
        top_n: int = 10,  # 每次选股数量
        selection_strategy: str = "comprehensive",  # 选股策略
        strategy_weights: Optional[Dict[str, float]] = None,  # 多策略权重
    ):
        """
        Args:
            initial_capital: 初始资金
            holding_period: 持有周期（天）
            top_n: 每次选股数量
            selection_strategy: 选股策略名称
            strategy_weights: 多策略权重配置
        """
        self.initial_capital = initial_capital
        self.holding_period = holding_period
        self.top_n = top_n
        self.selection_strategy = selection_strategy
        self.strategy_weights = strategy_weights or {}

        self.fetcher = get_data_fetcher()
        self.scorer = create_scorer()
        self.screener = get_screener()
        self.dragon_strategy = create_dragon_strategy()
        self.metrics_calc = create_metrics_calculator()

    def get_selection_dates(
        self,
        start_date: str,
        end_date: str,
    ) -> List[str]:
        """
        获取选股日期列表（每 holding_period 天选一次）

        基于真实交易日历
        """
        # 获取交易日历
        calendar = self.fetcher.get_trade_calendar()
        if calendar.empty:
            # 回退到简化版本
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
        
        # 使用真实交易日历
        calendar = calendar[calendar["is_open"] == 1]
        calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
        calendar = calendar[(calendar["trade_date"] >= start_date) & 
                          (calendar["trade_date"] <= end_date)]
        
        trade_dates = calendar["trade_date"].dt.strftime("%Y%m%d").tolist()
        
        # 每 holding_period 个交易日选一次
        selection_dates = []
        for i in range(0, len(trade_dates), self.holding_period):
            selection_dates.append(trade_dates[i])
        
        return selection_dates

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
        """
        模拟卖出
        
        Returns:
            卖出金额
        """
        return shares * sell_price

    def select_stocks(self, date: str, capital: float) -> List[Dict]:
        """
        基于策略选择股票
        
        Args:
            date: 选股日期
            capital: 当前资金
            
        Returns:
            选中的股票列表
        """
        try:
            if self.strategy_weights:
                # 多策略组合
                all_stocks = {}
                
                # 从每个策略中选择股票
                for strategy, weight in self.strategy_weights.items():
                    if weight <= 0:
                        continue
                    
                    strategy_stocks = []
                    if strategy == "dragon":
                        # 龙头战法
                        boards = ["人工智能", "新能源", "半导体", "医药", "大消费"]
                        for board in boards:
                            try:
                                dragons = self.dragon_strategy.identify_dragon_stocks(board, top_n=2)
                                for dragon in dragons:
                                    strategy_stocks.append({
                                        "ts_code": dragon.ts_code,
                                        "stock_name": dragon.stock_name,
                                        "score": dragon.dragon_score * weight,
                                        "board_name": board,
                                        "strategy": strategy
                                    })
                            except Exception as e:
                                logger.error(f"龙头策略选股失败 {board}：{e}")
                    else:
                        # 综合评分策略
                        try:
                            result = self.screener.select_with_portfolio(trade_date=date, top_n=self.top_n)
                            for stock in result.get("stocks", []):
                                strategy_stocks.append({
                                    "ts_code": stock.get("ts_code"),
                                    "stock_name": stock.get("stock_name"),
                                    "score": stock.get("total_score", 50) * weight,
                                    "board_name": "未知",
                                    "strategy": strategy
                                })
                        except Exception as e:
                            logger.error(f"综合策略选股失败：{e}")
                    
                    # 合并股票，权重累加
                    for stock in strategy_stocks:
                        ts_code = stock["ts_code"]
                        if ts_code in all_stocks:
                            all_stocks[ts_code]["score"] += stock["score"]
                        else:
                            all_stocks[ts_code] = stock
                
                # 转换为列表并排序
                stocks = list(all_stocks.values())
                stocks.sort(key=lambda x: x["score"], reverse=True)
                return stocks[:self.top_n]
            elif self.selection_strategy == "dragon":
                # 单一龙头战法
                stocks = []
                # 获取热门板块
                boards = ["人工智能", "新能源", "半导体", "医药", "大消费"]
                for board in boards:
                    dragons = self.dragon_strategy.identify_dragon_stocks(board, top_n=2)
                    for dragon in dragons:
                        stocks.append({
                            "ts_code": dragon.ts_code,
                            "stock_name": dragon.stock_name,
                            "score": dragon.dragon_score,
                            "board_name": board
                        })
                # 排序并取前 top_n
                stocks.sort(key=lambda x: x["score"], reverse=True)
                return stocks[:self.top_n]
            else:
                # 单一综合评分
                result = self.screener.select_with_portfolio(trade_date=date, top_n=self.top_n)
                return result.get("stocks", [])
        except Exception as e:
            logger.error(f"选股失败 {date}：{e}")
            # 回退到随机选股
            return self._random_select_stocks(date)

    def _random_select_stocks(self, date: str) -> List[Dict]:
        """
        随机选择股票（作为回退方案）
        """
        try:
            market_data = self.fetcher.get_market_data(date)
            if not market_data.empty:
                # 随机选择 top_n 只股票
                sample = market_data.sample(min(self.top_n, len(market_data)))
                stocks = []
                for _, row in sample.iterrows():
                    stocks.append({
                        "ts_code": row.get("ts_code", ""),
                        "stock_name": row.get("name", ""),
                        "score": 50.0
                    })
                return stocks
        except Exception:
            pass
        return []

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
        logger.info(f"开始回测：{start_date} - {end_date}, 策略：{self.selection_strategy}")

        # 初始化
        capital = self.initial_capital
        positions = {}  # 持仓：ts_code -> {shares, buy_price, buy_date, stock_name, position_ratio}

        trades: List[Trade] = []
        equity_curve = []
        benchmark_curve = []
        trade_returns = []
        holding_days_list = []
        sector_returns = {}

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
                        position_ratio = pos.get("position_ratio", 0)
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
                            position_ratio=position_ratio,
                        ))

                        trade_returns.append(return_pct)
                        holding_days_list.append(holding_days)

                        # 记录行业收益
                        board_name = pos.get("board_name", "未知")
                        if board_name not in sector_returns:
                            sector_returns[board_name] = []
                        sector_returns[board_name].append(return_pct)

                        del positions[ts_code]
                        logger.debug(f"卖出 {ts_code}, 收益率：{return_pct:.2%}")

            # 计算当日权益
            total_equity = capital
            for pos in positions.values():
                # 获取最新价格
                ts_code = pos["ts_code"]
                price_data = self.fetcher.get_stock_prices(
                    ts_code,
                    start_date=date_str,
                    end_date=date_str,
                )
                if not price_data.empty:
                    current_price = price_data.iloc[0].get("close", pos["buy_price"])
                    total_equity += pos["shares"] * current_price
                else:
                    total_equity += pos["shares"] * pos["buy_price"]

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
                selected_stocks = self.select_stocks(date_str, capital)
                
                if selected_stocks:
                    # 计算每只股票的仓位
                    position_per_stock = capital / len(selected_stocks)
                    
                    for stock in selected_stocks:
                        ts_code = stock.get("ts_code")
                        if not ts_code or ts_code in positions:
                            continue
                        
                        # 获取买入价格
                        price_data = self.fetcher.get_stock_prices(
                            ts_code,
                            start_date=date_str,
                            end_date=date_str,
                        )
                        
                        if not price_data.empty:
                            buy_price = price_data.iloc[0].get("close")
                            shares, actual_amount = self.simulate_buy(
                                ts_code,
                                date_str,
                                buy_price,
                                position_per_stock,
                            )
                            
                            # 记录持仓
                            positions[ts_code] = {
                                "shares": shares,
                                "buy_price": buy_price,
                                "buy_date": date_str,
                                "stock_name": stock.get("stock_name", ts_code),
                                "position_ratio": actual_amount / capital,
                                "board_name": stock.get("board_name", "未知"),
                            }
                            
                            capital -= actual_amount
                            logger.debug(f"买入 {ts_code}, 价格：{buy_price}, 股数：{shares}")

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
                    position_ratio=pos.get("position_ratio", 0),
                ))

                trade_returns.append(return_pct)
                capital += sell_amount

                # 记录行业收益
                board_name = pos.get("board_name", "未知")
                if board_name not in sector_returns:
                    sector_returns[board_name] = []
                sector_returns[board_name].append(return_pct)

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

        # 计算行业表现
        sector_performance = {}
        for sector, returns in sector_returns.items():
            if returns:
                sector_performance[sector] = np.mean(returns)

        # 排序交易结果
        trades.sort(key=lambda x: x.return_pct, reverse=True)
        best_trades = trades[:5] if len(trades) >= 5 else trades
        worst_trades = trades[-5:] if len(trades) >= 5 else trades
        worst_trades.reverse()

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
            sector_performance=sector_performance,
            best_trades=best_trades,
            worst_trades=worst_trades,
        )

    def print_result(self, result: BacktestResult):
        """打印回测结果"""
        m = result.metrics

        print("\n" + "=" * 60)
        print("回测结果")
        print("=" * 60)
        print(f"回测区间：{result.start_date} - {result.end_date}")
        print(f"初始资金：{result.initial_capital:,.0f}")
        print(f"期末资金：{result.final_capital:,.0f}")
        print(f"选股策略：{self.selection_strategy}")
        if self.strategy_weights:
            print(f"多策略权重：{self.strategy_weights}")
        print("\n收益指标:")
        print(f"  总收益率：{m.total_return:.2%}")
        print(f"  年化收益：{m.annual_return:.2%}")
        print(f"  基准收益：{m.benchmark_return:.2%}")
        print(f"  超额收益：{m.excess_return:.2%}")
        print("\n风险指标:")
        print(f"  最大回撤：{m.max_drawdown:.2%}")
        print(f"  夏普比率：{m.sharpe_ratio:.2f}")
        print(f"  索提诺比率：{m.sortino_ratio:.2f}")
        print(f"  年化波动率：{m.annual_volatility:.2%}")
        print("\n交易统计:")
        print(f"  总交易次数：{m.total_trades}")
        print(f"  胜率：{m.win_rate:.2%}")
        print(f"  盈亏比：{m.profit_loss_ratio:.2f}")
        print(f"  平均盈利：{m.avg_win:.2%}")
        print(f"  平均亏损：{m.avg_loss:.2%}")
        print(f"  平均持有天数：{m.avg_holding_days:.1f}")
        
        # 行业表现
        if result.sector_performance:
            print("\n行业表现:")
            for sector, avg_return in sorted(result.sector_performance.items(), 
                                         key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {sector}: {avg_return:.2%}")
        
        # 最佳交易
        if result.best_trades:
            print("\n最佳交易:")
            print(f"{'股票':<15}{'买入日期':<10}{'卖出日期':<10}{'收益率':<10}{'持有天数':<10}")
            print("-" * 65)
            for trade in result.best_trades:
                print(f"{trade.stock_name:<15}{trade.buy_date:<10}{trade.sell_date:<10}" 
                      f"{trade.return_pct:.2%:<10}{trade.holding_days:<10}")
        
        # 最差交易
        if result.worst_trades:
            print("\n最差交易:")
            print(f"{'股票':<15}{'买入日期':<10}{'卖出日期':<10}{'收益率':<10}{'持有天数':<10}")
            print("-" * 65)
            for trade in result.worst_trades:
                print(f"{trade.stock_name:<15}{trade.buy_date:<10}{trade.sell_date:<10}" 
                      f"{trade.return_pct:.2%:<10}{trade.holding_days:<10}")
        
        print("=" * 60)

    def optimize_parameters(
        self,
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List[float]],
        benchmark_code: str = "000300.SH",
        objective: str = "sharpe_ratio",  # 优化目标：sharpe_ratio, total_return, sortino_ratio
    ) -> Dict:
        """
        参数优化

        Args:
            start_date: 开始日期
            end_date: 结束日期
            param_grid: 参数网格
            benchmark_code: 基准指数
            objective: 优化目标

        Returns:
            最优参数和结果
        """
        import itertools
        
        logger.info(f"开始参数优化，目标：{objective}")
        
        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))
        
        best_score = -float('inf')
        best_params = None
        best_result = None
        
        # 遍历所有参数组合
        for i, params in enumerate(param_combinations):
            param_dict = dict(zip(param_names, params))
            logger.info(f"测试参数组合 {i+1}/{len(param_combinations)}: {param_dict}")
            
            # 创建临时回测引擎
            temp_engine = BacktestEngine(
                initial_capital=self.initial_capital,
                holding_period=param_dict.get('holding_period', self.holding_period),
                top_n=param_dict.get('top_n', self.top_n),
                selection_strategy=param_dict.get('selection_strategy', self.selection_strategy),
                strategy_weights=param_dict.get('strategy_weights', self.strategy_weights),
            )
            
            # 运行回测
            try:
                result = temp_engine.run_backtest(start_date, end_date, benchmark_code)
                
                # 计算目标值
                if objective == 'sharpe_ratio':
                    score = result.metrics.sharpe_ratio
                elif objective == 'total_return':
                    score = result.metrics.total_return
                elif objective == 'sortino_ratio':
                    score = result.metrics.sortino_ratio
                else:
                    score = result.metrics.sharpe_ratio
                
                # 比较并更新最优结果
                if score > best_score:
                    best_score = score
                    best_params = param_dict
                    best_result = result
                    logger.info(f"找到更优参数：{best_params}, 得分：{best_score:.4f}")
                    
            except Exception as e:
                logger.error(f"参数组合测试失败 {param_dict}：{e}")
                continue
        
        if best_result:
            logger.info(f"参数优化完成，最优参数：{best_params}, 最优得分：{best_score:.4f}")
            return {
                'best_params': best_params,
                'best_score': best_score,
                'best_result': best_result
            }
        else:
            logger.warning("参数优化失败，没有找到有效参数组合")
            return {
                'best_params': None,
                'best_score': None,
                'best_result': None
            }


def create_backtest_engine(
    initial_capital: float = 100000,
    holding_period: int = 15,
    top_n: int = 10,
    selection_strategy: str = "comprehensive",
    strategy_weights: Optional[Dict[str, float]] = None,
) -> BacktestEngine:
    """创建回测引擎实例"""
    return BacktestEngine(initial_capital, holding_period, top_n, selection_strategy, strategy_weights)
