"""
回测绩效指标计算模块

增强功能:
- 基础指标：总收益、年化收益、夏普比率、最大回撤等
- 进阶指标：Calmar 比率、VaR、CVaR、Omega 比率等
- 基准对比：相对收益、信息比率、跟踪误差
- 交易统计：连续盈亏、月度收益分布等
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BacktestMetrics:
    """回测绩效指标"""
    # 基础指标
    total_return: float  # 总收益率
    annual_return: float  # 年化收益率
    benchmark_return: float  # 基准收益率
    excess_return: float  # 超额收益
    max_drawdown: float  # 最大回撤
    sharpe_ratio: float  # 夏普比率
    sortino_ratio: float  # 索提诺比率

    # 进阶指标
    calmar_ratio: float = 0.0  # Calmar 比率
    var_95: float = 0.0  # 95% VaR
    cvar_95: float = 0.0  # 95% CVaR
    omega_ratio: float = 0.0  # Omega 比率
    tail_ratio: float = 0.0  # 尾部比率

    # 基准对比
    information_ratio: float = 0.0  # 信息比率
    tracking_error: float = 0.0  # 跟踪误差
    alpha: float = 0.0  # Alpha
    beta: float = 0.0  # Beta

    # 交易统计
    win_rate: float  # 胜率
    profit_loss_ratio: float  # 盈亏比
    total_trades: int  # 总交易次数
    winning_trades: int  # 盈利交易数
    losing_trades: int  # 亏损交易数
    avg_win: float  # 平均盈利
    avg_loss: float  # 平均亏损
    avg_holding_days: float  # 平均持有天数
    turnover_rate: float  # 换手率

    # 额外统计
    consecutive_wins: int = 0  # 最大连续盈利
    consecutive_losses: int = 0  # 最大连续亏损
    best_month: float = 0.0  # 最佳月度收益
    worst_month: float = 0.0  # 最差月度收益
    monthly_returns: List[float] = field(default_factory=list)  # 月度收益


class MetricsCalculator:
    """绩效指标计算器"""

    def __init__(self, risk_free_rate: float = 0.03):
        """
        Args:
            risk_free_rate: 无风险利率（年化）
        """
        self.risk_free_rate = risk_free_rate

    def calculate_total_return(
        self,
        initial_capital: float,
        final_capital: float,
    ) -> float:
        """计算总收益率"""
        if initial_capital == 0:
            return 0.0
        return (final_capital - initial_capital) / initial_capital

    def calculate_annual_return(
        self,
        total_return: float,
        days: int,
    ) -> float:
        """计算年化收益率"""
        if days <= 0:
            return 0.0
        years = days / 365
        if years <= 0:
            return total_return
        return (1 + total_return) ** (1 / years) - 1

    def calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """
        计算最大回撤

        Args:
            equity_curve: 权益曲线

        Returns:
            float: 最大回撤（正数）
        """
        if equity_curve.empty:
            return 0.0

        # 计算累计最大值
        running_max = equity_curve.cummax()
        drawdown = (equity_curve - running_max) / running_max

        return abs(drawdown.min())

    def calculate_sharpe_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None,
    ) -> float:
        """
        计算夏普比率

        Args:
            returns: 日收益率序列
            risk_free_rate: 无风险利率（年化）

        Returns:
            float: 夏普比率
        """
        if returns.empty or returns.std() == 0:
            return 0.0

        rf = risk_free_rate if risk_free_rate else self.risk_free_rate
        daily_rf = rf / 252  # 日化

        excess_returns = returns - daily_rf
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)

        return sharpe

    def calculate_sortino_ratio(
        self,
        returns: pd.Series,
        risk_free_rate: Optional[float] = None,
    ) -> float:
        """
        计算索提诺比率（只考虑下行波动）

        Args:
            returns: 日收益率序列

        Returns:
            float: 索提诺比率
        """
        if returns.empty:
            return 0.0

        rf = risk_free_rate if risk_free_rate else self.risk_free_rate
        daily_rf = rf / 252

        excess_returns = returns - daily_rf
        downside_returns = returns[returns < 0]

        if downside_returns.empty or downside_returns.std() == 0:
            return 0.0

        sortino = excess_returns.mean() / downside_returns.std() * np.sqrt(252)
        return sortino

    def calculate_win_rate(
        self,
        trade_returns: pd.Series,
    ) -> float:
        """
        计算胜率

        Args:
            trade_returns: 交易收益率序列

        Returns:
            float: 胜率
        """
        if trade_returns.empty:
            return 0.0

        winning_trades = (trade_returns > 0).sum()
        total_trades = len(trade_returns)

        return winning_trades / total_trades if total_trades > 0 else 0.0

    def calculate_profit_loss_ratio(
        self,
        trade_returns: pd.Series,
    ) -> float:
        """
        计算盈亏比

        Args:
            trade_returns: 交易收益率序列

        Returns:
            float: 盈亏比
        """
        if trade_returns.empty:
            return 0.0

        winning_returns = trade_returns[trade_returns > 0]
        losing_returns = trade_returns[trade_returns < 0]

        avg_win = winning_returns.mean() if not winning_returns.empty else 0
        avg_loss = abs(losing_returns.mean()) if not losing_returns.empty else 0

        if avg_loss == 0:
            return float('inf') if avg_win > 0 else 0.0

        return avg_win / avg_loss

    def calculate_metrics(
        self,
        equity_curve: pd.Series,
        benchmark_curve: Optional[pd.Series] = None,
        trade_returns: Optional[pd.Series] = None,
        holding_days: Optional[pd.Series] = None,
        initial_capital: float = 100000,
    ) -> BacktestMetrics:
        """
        计算完整绩效指标

        Args:
            equity_curve: 权益曲线
            benchmark_curve: 基准曲线（可选）
            trade_returns: 交易收益率序列（可选）
            holding_days: 持有天数序列（可选）
            initial_capital: 初始资金

        Returns:
            BacktestMetrics: 绩效指标
        """
        # 基础数据
        final_capital = equity_curve.iloc[-1] if not equity_curve.empty else initial_capital
        days = len(equity_curve)

        # 日收益率
        returns = equity_curve.pct_change().dropna()

        # 总收益和年化收益
        total_return = self.calculate_total_return(initial_capital, final_capital)
        annual_return = self.calculate_annual_return(total_return, days)

        # 基准收益
        benchmark_return = 0.0
        excess_return = total_return
        if benchmark_curve is not None and not benchmark_curve.empty:
            benchmark_return = self.calculate_total_return(
                benchmark_curve.iloc[0],
                benchmark_curve.iloc[-1],
            )
            excess_return = total_return - benchmark_return

        # 风险指标
        max_drawdown = self.calculate_max_drawdown(equity_curve)
        sharpe_ratio = self.calculate_sharpe_ratio(returns)
        sortino_ratio = self.calculate_sortino_ratio(returns)

        # 交易指标
        win_rate = 0.0
        profit_loss_ratio = 0.0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        avg_win = 0.0
        avg_loss = 0.0

        if trade_returns is not None and not trade_returns.empty:
            total_trades = len(trade_returns)
            winning_trades = (trade_returns > 0).sum()
            losing_trades = (trade_returns < 0).sum()
            win_rate = self.calculate_win_rate(trade_returns)
            profit_loss_ratio = self.calculate_profit_loss_ratio(trade_returns)

            winning_returns = trade_returns[trade_returns > 0]
            losing_returns = trade_returns[trade_returns < 0]
            avg_win = winning_returns.mean() if not winning_returns.empty else 0
            avg_loss = abs(losing_returns.mean()) if not losing_returns.empty else 0

            # 连续盈亏
            consecutive_wins, consecutive_losses = self.calculate_consecutive_trades(trade_returns)

        # 平均持有天数
        avg_holding_days = holding_days.mean() if holding_days is not None else 0

        # 换手率（简化计算）
        turnover_rate = total_trades / days * 252 if days > 0 else 0

        # 进阶指标
        calmar_ratio = self.calculate_calmar_ratio(annual_return, max_drawdown)
        var_95, cvar_95 = self.calculate_var(returns)
        omega_ratio = self.calculate_omega_ratio(returns)
        tail_ratio = self.calculate_tail_ratio(returns)

        # 基准对比指标
        information_ratio = 0.0
        tracking_error = 0.0
        alpha = 0.0
        beta = 0.0

        if benchmark_curve is not None and not benchmark_curve.empty:
            tracking_error = self.calculate_tracking_error(returns, benchmark_curve.pct_change().dropna())
            information_ratio = self.calculate_information_ratio(returns, benchmark_curve.pct_change().dropna())
            beta, alpha = self.calculate_alpha_beta(returns, benchmark_curve.pct_change().dropna())

        # 月度收益
        monthly_returns = self.calculate_monthly_returns(equity_curve)
        best_month = max(monthly_returns) if monthly_returns else 0
        worst_month = min(monthly_returns) if monthly_returns else 0

        return BacktestMetrics(
            total_return=round(total_return, 4),
            annual_return=round(annual_return, 4),
            benchmark_return=round(benchmark_return, 4),
            excess_return=round(excess_return, 4),
            max_drawdown=round(max_drawdown, 4),
            sharpe_ratio=round(sharpe_ratio, 2),
            sortino_ratio=round(sortino_ratio, 2),
            calmar_ratio=round(calmar_ratio, 2),
            var_95=round(var_95, 4),
            cvar_95=round(cvar_95, 4),
            omega_ratio=round(omega_ratio, 2),
            tail_ratio=round(tail_ratio, 2),
            information_ratio=round(information_ratio, 2),
            tracking_error=round(tracking_error, 4),
            alpha=round(alpha, 4),
            beta=round(beta, 4),
            win_rate=round(win_rate, 4),
            profit_loss_ratio=round(profit_loss_ratio, 2),
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=round(avg_win, 4),
            avg_loss=round(avg_loss, 4),
            avg_holding_days=round(avg_holding_days, 1),
            turnover_rate=round(turnover_rate, 2),
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            best_month=round(best_month, 4),
            worst_month=round(worst_month, 4),
            monthly_returns=[round(r, 4) for r in monthly_returns],
        )

    def calculate_calmar_ratio(self, annual_return: float, max_drawdown: float) -> float:
        """计算 Calmar 比率（年化收益/最大回撤）"""
        if max_drawdown == 0:
            return 0.0
        return annual_return / max_drawdown

    def calculate_var(self, returns: pd.Series, confidence: float = 0.95) -> Tuple[float, float]:
        """
        计算 VaR 和 CVaR

        Args:
            returns: 收益率序列
            confidence: 置信水平

        Returns:
            (VaR, CVaR)
        """
        if returns.empty:
            return 0.0, 0.0

        var = -returns.quantile(1 - confidence)
        cvar = -returns[returns <= -var].mean() if len(returns[returns <= -var]) > 0 else 0

        return var, cvar

    def calculate_omega_ratio(self, returns: pd.Series, threshold: float = 0.0) -> float:
        """
        计算 Omega 比率

        Args:
            returns: 收益率序列
            threshold: 最低可接受收益率

        Returns:
            Omega 比率
        """
        if returns.empty:
            return 0.0

        excess = returns - threshold
        gains = excess[excess > 0].sum()
        losses = abs(excess[excess < 0].sum())

        if losses == 0:
            return float('inf') if gains > 0 else 1.0

        return gains / losses

    def calculate_tail_ratio(self, returns: pd.Series, cutoff: float = 0.05) -> float:
        """
        计算尾部比率（右尾/左尾）

        Args:
            returns: 收益率序列
            cutoff: 尾部 cutoff

        Returns:
            尾部比率
        """
        if returns.empty:
            return 0.0

        left_tail = returns.quantile(cutoff)
        right_tail = returns.quantile(1 - cutoff)

        if left_tail == 0:
            return 0.0

        return abs(right_tail / left_tail)

    def calculate_tracking_error(self, returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """计算跟踪误差"""
        if returns.empty or benchmark_returns.empty:
            return 0.0

        # 对齐日期
        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0

        diff = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        return diff.std() * np.sqrt(252)

    def calculate_information_ratio(self, returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """计算信息比率"""
        if returns.empty or benchmark_returns.empty:
            return 0.0

        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0

        diff = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        active_return = diff.mean() * 252
        tracking_error = diff.std() * np.sqrt(252)

        if tracking_error == 0:
            return 0.0

        return active_return / tracking_error

    def calculate_alpha_beta(
        self,
        returns: pd.Series,
        benchmark_returns: pd.Series,
    ) -> Tuple[float, float]:
        """
        计算 Alpha 和 Beta

        Returns:
            (beta, alpha)
        """
        if returns.empty or benchmark_returns.empty:
            return 0.0, 0.0

        # 对齐日期
        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 10:  # 至少需要 10 个数据点
            return 0.0, 0.0

        # 计算协方差和方差
        cov = aligned.iloc[:, 0].cov(aligned.iloc[:, 1])
        var = aligned.iloc[:, 1].var()

        if var == 0:
            return 0.0, 0.0

        beta = cov / var
        alpha = (aligned.iloc[:, 0].mean() - beta * aligned.iloc[:, 1].mean()) * 252

        return beta, alpha

    def calculate_consecutive_trades(self, trade_returns: pd.Series) -> Tuple[int, int]:
        """
        计算最大连续盈利和亏损

        Returns:
            (最大连续盈利次数，最大连续亏损次数)
        """
        if trade_returns.empty:
            return 0, 0

        max_consecutive_wins = 0
        max_consecutive_losses = 0
        current_wins = 0
        current_losses = 0

        for ret in trade_returns:
            if ret > 0:
                current_wins += 1
                current_losses = 0
                max_consecutive_wins = max(max_consecutive_wins, current_wins)
            elif ret < 0:
                current_losses += 1
                current_wins = 0
                max_consecutive_losses = max(max_consecutive_losses, current_losses)
            else:
                current_wins = 0
                current_losses = 0

        return max_consecutive_wins, max_consecutive_losses

    def calculate_monthly_returns(self, equity_curve: pd.Series) -> List[float]:
        """计算月度收益率"""
        if equity_curve.empty:
            return []

        # 重新采样到月末
        monthly = equity_curve.resample('ME').last()
        if len(monthly) < 2:
            return []

        return monthly.pct_change().dropna().tolist()


def create_metrics_calculator(risk_free_rate: float = 0.03) -> MetricsCalculator:
    """创建绩效指标计算器"""
    return MetricsCalculator(risk_free_rate)
