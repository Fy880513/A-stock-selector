"""
风险监控模块

监控持仓股票的风险，包括止损止盈、技术破位、资金流出等
支持动态止损止盈：
- 基于波动率调整止损幅度
- 基于持仓时间调整止盈点
- 移动止盈（追踪止盈）
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from config.trading_config import RISK_CONFIG, TRADING_CONFIG
from position.analyzer import StockAnalysis
from utils.logger import get_logger

logger = get_logger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    NORMAL = "normal"      # 正常
    WATCH = "watch"        # 观察
    WARNING = "warning"    # 预警
    DANGER = "danger"      # 危险


class RiskType(Enum):
    """风险类型"""
    STOP_LOSS = "stop_loss"          # 止损
    STOP_PROFIT = "stop_profit"      # 止盈
    MA_BREAKDOWN = "ma_breakdown"    # 均线破位
    CAPITAL_OUTFLOW = "capital_outflow"  # 资金流出
    TECHNICAL_WEAK = "technical_weak"    # 技术面走弱
    TRAIL_STOP = "trail_stop"        # 移动止盈


@dataclass
class RiskWarning:
    """风险预警信息"""
    ts_code: str
    stock_name: str
    risk_type: RiskType
    risk_level: RiskLevel
    message: str
    current_price: float
    trigger_price: Optional[float]
    suggestion: str  # 建议操作


class RiskMonitor:
    """风险监控器"""

    def __init__(self):
        self.stop_loss_ratio = TRADING_CONFIG.get("stop_loss_ratio", 0.08)
        self.stop_profit_ratio = TRADING_CONFIG.get("stop_profit_ratio", 0.20)
        self.warning_threshold = RISK_CONFIG.get("stop_loss_warning_threshold", 0.05)
        self.trail_stop_ratio = TRADING_CONFIG.get("trail_stop_ratio", 0.10)

        # 波动率配置
        self.volatility_multiplier = 1.5  # 波动率乘数
        self.base_atr = 0.03  # 基准 ATR（3%）

        # 持仓时间配置
        self.holding_periods = [
            (1, 0.10),    # 1 天内：止盈 10%
            (3, 0.15),    # 3 天内：止盈 15%
            (5, 0.20),    # 5 天内：止盈 20%
            (10, 0.25),   # 10 天内：止盈 25%
            (20, 0.30),   # 20 天内：止盈 30%
        ]

    def calculate_dynamic_stop_loss(
        self,
        current_price: float,
        atr: Optional[float] = None,
        volatility: Optional[float] = None,
    ) -> float:
        """
        计算动态止损价（基于波动率/ATR）

        Args:
            current_price: 当前价格
            atr: 平均真实波幅（ATR）
            volatility: 波动率

        Returns:
            float: 动态止损价
        """
        if atr:
            # 使用 ATR 计算止损
            stop_loss_price = current_price - (atr * self.volatility_multiplier)
        elif volatility:
            # 使用波动率计算止损
            stop_loss_price = current_price * (1 - volatility * self.volatility_multiplier)
        else:
            # 使用固定比例
            stop_loss_price = current_price * (1 - self.stop_loss_ratio)

        return max(0, stop_loss_price)

    def calculate_dynamic_stop_profit(
        self,
        cost_price: float,
        holding_days: int,
        current_price: Optional[float] = None,
    ) -> float:
        """
        计算动态止盈价（基于持仓时间）

        Args:
            cost_price: 成本价
            holding_days: 持仓天数
            current_price: 当前价格（用于移动止盈）

        Returns:
            float: 动态止盈价
        """
        # 根据持仓时间确定止盈比例
        target_profit = self.stop_profit_ratio
        for days, profit in self.holding_periods:
            if holding_days >= days:
                target_profit = profit
                break

        # 基础止盈价
        stop_profit_price = cost_price * (1 + target_profit)

        # 如果当前已有盈利，启用移动止盈
        if current_price and current_price > cost_price * 1.1:  # 盈利超过 10%
            profit_ratio = (current_price - cost_price) / current_price
            if profit_ratio > target_profit:
                # 启用回撤止盈（从最高点回撤一定比例）
                stop_profit_price = current_price * (1 - self.trail_stop_ratio)

        return stop_profit_price

    def check_trail_stop(
        self,
        analysis: StockAnalysis,
        highest_price: float,
    ) -> Optional[RiskWarning]:
        """
        检查移动止盈（追踪止盈）

        Args:
            analysis: 股票分析
            highest_price: 持仓期间最高价

        Returns:
            RiskWarning 或 None
        """
        current_price = analysis.current_price
        cost_price = analysis.cost_price

        # 只有盈利超过 15% 才启用移动止盈
        if (current_price - cost_price) / cost_price < 0.15:
            return None

        # 计算回撤比例
        drawdown = (highest_price - current_price) / highest_price

        # 触发移动止盈
        if drawdown >= self.trail_stop_ratio:
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.TRAIL_STOP,
                risk_level=RiskLevel.WARNING,
                message=f"从高点回撤 {drawdown:.2%}，触发移动止盈",
                current_price=current_price,
                trigger_price=highest_price * (1 - self.trail_stop_ratio),
                suggestion="建议减仓 50% 锁定利润",
            )

        return None

    def check_stop_loss(
        self,
        analysis: StockAnalysis,
    ) -> Optional[RiskWarning]:
        """
        检查止损条件

        Returns:
            RiskWarning 或 None
        """
        profit_ratio = analysis.profit_ratio
        cost_price = analysis.cost_price
        current_price = analysis.current_price

        # 计算止损价
        stop_loss_price = cost_price * (1 - self.stop_loss_ratio)

        # 已触发止损
        if profit_ratio <= -self.stop_loss_ratio:
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.STOP_LOSS,
                risk_level=RiskLevel.DANGER,
                message=f"已触发止损线（亏损 {profit_ratio:.2%}）",
                current_price=current_price,
                trigger_price=stop_loss_price,
                suggestion="建议清仓止损",
            )

        # 接近止损（预警）
        if profit_ratio <= -self.stop_loss_ratio + self.warning_threshold:
            distance = (current_price - stop_loss_price) / current_price
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.STOP_LOSS,
                risk_level=RiskLevel.WARNING,
                message=f"接近止损线（亏损 {profit_ratio:.2%}，距离止损价 {distance:.2%}）",
                current_price=current_price,
                trigger_price=stop_loss_price,
                suggestion="注意风险，准备止损",
            )

        return None

    def check_stop_profit(
        self,
        analysis: StockAnalysis,
    ) -> Optional[RiskWarning]:
        """
        检查止盈条件

        Returns:
            RiskWarning 或 None
        """
        profit_ratio = analysis.profit_ratio
        cost_price = analysis.cost_price
        current_price = analysis.current_price

        # 计算止盈价
        stop_profit_price = cost_price * (1 + self.stop_profit_ratio)

        # 已触发止盈
        if profit_ratio >= self.stop_profit_ratio:
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.STOP_PROFIT,
                risk_level=RiskLevel.WATCH,
                message=f"已触发止盈线（盈利 {profit_ratio:.2%}）",
                current_price=current_price,
                trigger_price=stop_profit_price,
                suggestion="建议减仓 50% 锁定利润",
            )

        # 接近止盈（预警）
        if profit_ratio >= self.stop_profit_ratio - self.warning_threshold:
            distance = (stop_profit_price - current_price) / current_price
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.STOP_PROFIT,
                risk_level=RiskLevel.WATCH,
                message=f"接近止盈线（盈利 {profit_ratio:.2%}，距离止盈价 {distance:.2%}）",
                current_price=current_price,
                trigger_price=stop_profit_price,
                suggestion="准备止盈",
            )

        return None

    def check_ma_breakdown(
        self,
        analysis: StockAnalysis,
    ) -> Optional[RiskWarning]:
        """
        检查均线破位

        Returns:
            RiskWarning 或 None
        """
        current_price = analysis.current_price
        ma20 = analysis.ma20
        ma60 = analysis.ma60
        ma_trend = analysis.ma_trend

        # 跌破 MA60（严重）
        if ma60 and current_price < ma60:
            if ma_trend in ["多头强势", "多头"]:
                # 之前在多头趋势，突然跌破
                return RiskWarning(
                    ts_code=analysis.ts_code,
                    stock_name=analysis.stock_name,
                    risk_type=RiskType.MA_BREAKDOWN,
                    risk_level=RiskLevel.DANGER,
                    message=f"跌破 MA60（{ma60:.2f}），趋势可能反转",
                    current_price=current_price,
                    trigger_price=ma60,
                    suggestion="建议减仓或清仓",
                )

        # 跌破 MA20（警告）
        if ma20 and current_price < ma20:
            if ma_trend in ["多头强势", "多头"]:
                return RiskWarning(
                    ts_code=analysis.ts_code,
                    stock_name=analysis.stock_name,
                    risk_type=RiskType.MA_BREAKDOWN,
                    risk_level=RiskLevel.WARNING,
                    message=f"跌破 MA20（{ma20:.2f}），短期趋势转弱",
                    current_price=current_price,
                    trigger_price=ma20,
                    suggestion="建议减仓观察",
                )

        return None

    def check_technical_weak(
        self,
        analysis: StockAnalysis,
    ) -> Optional[RiskWarning]:
        """
        检查技术面走弱

        Returns:
            RiskWarning 或 None
        """
        technical_score = analysis.technical_score
        kdj_status = analysis.kdj_status
        macd_status = analysis.macd_status
        ma_trend = analysis.ma_trend

        # 技术面得分过低
        if technical_score < 40:
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.TECHNICAL_WEAK,
                risk_level=RiskLevel.WARNING,
                message=f"技术面得分过低（{technical_score} 分）",
                current_price=analysis.current_price,
                trigger_price=None,
                suggestion="注意风险，考虑减仓",
            )

        # KDJ 超买 + 技术得分下降
        if kdj_status == "超买" and technical_score < 60:
            return RiskWarning(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                risk_type=RiskType.TECHNICAL_WEAK,
                risk_level=RiskLevel.WATCH,
                message=f"KDJ 超买且技术面走弱",
                current_price=analysis.current_price,
                trigger_price=None,
                suggestion="注意回调风险",
            )

        return None

    def check_all_risks(
        self,
        analysis: StockAnalysis,
    ) -> List[RiskWarning]:
        """
        检查所有风险

        Returns:
            List[RiskWarning]: 风险预警列表
        """
        warnings = []

        # 止损检查
        warning = self.check_stop_loss(analysis)
        if warning:
            warnings.append(warning)

        # 止盈检查
        warning = self.check_stop_profit(analysis)
        if warning:
            warnings.append(warning)

        # 均线破位检查
        warning = self.check_ma_breakdown(analysis)
        if warning:
            warnings.append(warning)

        # 技术面走弱检查
        warning = self.check_technical_weak(analysis)
        if warning:
            warnings.append(warning)

        # 按风险等级排序
        risk_order = {RiskLevel.DANGER: 0, RiskLevel.WARNING: 1, RiskLevel.WATCH: 2, RiskLevel.NORMAL: 3}
        warnings.sort(key=lambda w: risk_order.get(w.risk_level, 3))

        return warnings

    def generate_risk_report(
        self,
        analyses: List[StockAnalysis],
    ) -> Dict:
        """
        生成风险报告

        Returns:
            dict: 风险报告
        """
        all_warnings = []
        danger_warnings = []
        warning_warnings = []
        watch_warnings = []

        for analysis in analyses:
            warnings = self.check_all_risks(analysis)
            all_warnings.extend(warnings)

            for w in warnings:
                if w.risk_level == RiskLevel.DANGER:
                    danger_warnings.append(w)
                elif w.risk_level == RiskLevel.WARNING:
                    warning_warnings.append(w)
                else:
                    watch_warnings.append(w)

        return {
            "total_warnings": len(all_warnings),
            "danger_count": len(danger_warnings),
            "warning_count": len(warning_warnings),
            "watch_count": len(watch_warnings),
            "warnings": all_warnings,
            "danger_warnings": danger_warnings,
            "warning_warnings": warning_warnings,
            "watch_warnings": watch_warnings,
        }

    def print_risk_warnings(
        self,
        warnings: List[RiskWarning],
    ):
        """打印风险预警"""
        if not warnings:
            print("【风险警示】无")
            return

        print("【风险警示】")
        for w in warnings:
            emoji = {"danger": "🔴", "warning": "⚠️", "watch": "🟡"}.get(
                w.risk_level.value, "⚪"
            )
            print(f"{emoji} {w.ts_code} {w.stock_name}: {w.message}")
            print(f"   建议：{w.suggestion}")


def create_risk_monitor() -> RiskMonitor:
    """创建风险监控器实例"""
    return RiskMonitor()
