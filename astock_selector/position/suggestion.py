"""
操作建议生成模块

根据持仓分析结果，生成买入/持有/减仓/卖出等操作建议
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from config.trading_config import SUGGESTION_CONFIG, TRADING_CONFIG
from position.analyzer import StockAnalysis
from position.risk_monitor import RiskWarning, RiskLevel
from utils.logger import get_logger

logger = get_logger(__name__)


class ActionType(Enum):
    """操作类型"""
    BUY = "buy"        # 买入/加仓
    HOLD = "hold"      # 持有
    REDUCE = "reduce"  # 减仓
    SELL = "sell"      # 卖出/清仓
    WATCH = "watch"    # 观察


@dataclass
class OperationSuggestion:
    """操作建议"""
    ts_code: str
    stock_name: str
    action: ActionType
    confidence: str  # 高/中/低
    reason: str
    target_ratio: Optional[float]  # 目标仓位比例
    details: str  # 详细说明


class SuggestionGenerator:
    """操作建议生成器"""

    def __init__(self):
        self.config = SUGGESTION_CONFIG
        self.conditions = self.config.get("conditions", {})

    def generate_suggestion(
        self,
        analysis: StockAnalysis,
        warnings: List[RiskWarning],
    ) -> OperationSuggestion:
        """
        生成单只股票的操作建议

        Args:
            analysis: 股票分析结果
            warnings: 风险预警列表

        Returns:
            OperationSuggestion: 操作建议
        """
        # 检查是否有严重风险
        danger_warnings = [w for w in warnings if w.risk_level == RiskLevel.DANGER]
        warning_warnings = [w for w in warnings if w.risk_level == RiskLevel.WARNING]

        # 优先级：止损 > 止盈 > 技术面 > 持有

        # 1. 止损卖出
        if any(w.risk_type.value == "stop_loss" for w in danger_warnings):
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action= ActionType.SELL,
                confidence="高",
                reason="已触发止损线",
                target_ratio=0.0,
                details=f"亏损 {analysis.profit_ratio:.2%}，建议清仓止损，避免进一步损失",
            )

        # 2. 跌破 MA60 卖出
        if any(w.risk_type.value == "ma_breakdown" for w in danger_warnings):
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.SELL,
                confidence="高",
                reason="跌破 MA60，趋势反转",
                target_ratio=0.0,
                details=f"股价跌破 MA60（{analysis.ma60:.2f}），长期趋势可能反转，建议清仓",
            )

        # 3. 大幅盈利减仓
        if analysis.profit_ratio >= 0.30:
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.REDUCE,
                confidence="中",
                reason="盈利超过 30%，建议锁定利润",
                target_ratio=0.5,
                details=f"盈利 {analysis.profit_ratio:.2%}，建议减仓 50%，剩余仓位设置移动止盈",
            )

        # 4. 触发止盈减仓
        if any(w.risk_type.value == "stop_profit" for w in warnings):
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.REDUCE,
                confidence="中",
                reason="达到止盈位",
                target_ratio=0.5,
                details=f"盈利 {analysis.profit_ratio:.2%}，达到止盈位，建议减仓 50% 锁定利润",
            )

        # 5. 跌破 MA20 减仓
        if any(w.risk_type.value == "ma_breakdown" for w in warning_warnings):
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.REDUCE,
                confidence="中",
                reason="跌破 MA20，短期趋势转弱",
                target_ratio=0.5,
                details=f"股价跌破 MA20（{analysis.ma20:.2f}），短期趋势转弱，建议减仓观察",
            )

        # 6. 技术面弱势减仓
        if analysis.technical_score < 40:
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.REDUCE,
                confidence="低",
                reason="技术面得分过低",
                target_ratio=0.5,
                details=f"技术面得分仅 {analysis.technical_score} 分，建议减仓避险",
            )

        # 7. 技术面强势 + 盈利 - 可以加仓
        if (analysis.technical_score >= 70 and
            analysis.profit_ratio > 0 and
            analysis.ma_trend in ["多头强势", "多头"]):
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.BUY,
                confidence="中",
                reason="技术面强势，盈利状态",
                target_ratio=None,
                details=f"技术面得分 {analysis.technical_score}，均线{analysis.ma_trend}，可适当加仓",
            )

        # 8. 小幅亏损 + 技术面稳定 - 持有观察
        if -0.05 <= analysis.profit_ratio <= 0:
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.HOLD,
                confidence="中",
                reason="小幅亏损，观望为主",
                target_ratio=None,
                details=f"亏损 {analysis.profit_ratio:.2%}，建议持有观察，设置好止损位",
            )

        # 9. 小幅盈利 + 技术面稳定 - 继续持有
        if 0 < analysis.profit_ratio < 0.20:
            return OperationSuggestion(
                ts_code=analysis.ts_code,
                stock_name=analysis.stock_name,
                action=ActionType.HOLD,
                confidence="中",
                reason="盈利状态，继续持有",
                target_ratio=None,
                details=f"盈利 {analysis.profit_ratio:.2%}，建议继续持有，关注 MA20 支撑",
            )

        # 10. 默认持有
        return OperationSuggestion(
            ts_code=analysis.ts_code,
            stock_name=analysis.stock_name,
            action=ActionType.HOLD,
            confidence="低",
            reason="无明显信号",
            target_ratio=None,
            details=f"当前价 {analysis.current_price:.2f}，建议持有观察",
        )

    def generate_all_suggestions(
        self,
        analyses: List[StockAnalysis],
        all_warnings: Dict[str, List[RiskWarning]],
    ) -> List[OperationSuggestion]:
        """
        生成全部持仓的操作建议

        Args:
            analyses: 分析结果列表
            all_warnings: 每只股票的预警列表

        Returns:
            List[OperationSuggestion]: 操作建议列表
        """
        suggestions = []

        for analysis in analyses:
            warnings = all_warnings.get(analysis.ts_code, [])
            suggestion = self.generate_suggestion(analysis, warnings)
            suggestions.append(suggestion)

        # 按优先级排序：卖出 > 减仓 > 持有 > 买入
        action_order = {
            ActionType.SELL: 0,
            ActionType.REDUCE: 1,
            ActionType.HOLD: 2,
            ActionType.WATCH: 3,
            ActionType.BUY: 4,
        }
        suggestions.sort(key=lambda s: action_order.get(s.action, 3))

        return suggestions

    def generate_summary(self, suggestions: List[OperationSuggestion]) -> Dict:
        """
        生成操作建议汇总

        Returns:
            dict: 汇总信息
        """
        sell_count = sum(1 for s in suggestions if s.action == ActionType.SELL)
        reduce_count = sum(1 for s in suggestions if s.action == ActionType.REDUCE)
        hold_count = sum(1 for s in suggestions if s.action == ActionType.HOLD)
        buy_count = sum(1 for s in suggestions if s.action == ActionType.BUY)
        watch_count = sum(1 for s in suggestions if s.action == ActionType.WATCH)

        return {
            "total_count": len(suggestions),
            "sell_count": sell_count,
            "reduce_count": reduce_count,
            "hold_count": hold_count,
            "buy_count": buy_count,
            "watch_count": watch_count,
            "suggestions": suggestions,
        }

    def print_suggestions(
        self,
        suggestions: List[OperationSuggestion],
    ):
        """打印操作建议"""
        if not suggestions:
            print("【操作建议】无")
            return

        print("\n【操作建议】")
        print("-" * 70)
        print(f"{'代码':<10}{'名称':<12}{'建议':<8}{'信心':<6}{'原因':<30}")
        print("-" * 70)

        action_emoji = {
            ActionType.SELL: "🔴 卖出",
            ActionType.REDUCE: "🟡 减仓",
            ActionType.HOLD: "⚪ 持有",
            ActionType.BUY: "🟢 买入",
            ActionType.WATCH: "👀 观察",
        }

        for s in suggestions:
            emoji = action_emoji.get(s.action, s.action.value)
            print(f"{s.ts_code:<10}{s.stock_name:<12}{emoji:<12}{s.confidence:<6}{s.reason:<25}")

        print("-" * 70)

        # 详细建议
        print("\n【详细建议】")
        for s in suggestions:
            if s.action in [ActionType.SELL, ActionType.REDUCE]:
                print(f"• {s.ts_code} {s.stock_name}: {s.details}")


def create_suggestion_generator() -> SuggestionGenerator:
    """创建操作建议生成器实例"""
    return SuggestionGenerator()
