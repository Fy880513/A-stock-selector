"""
风险监控模块

监控持仓股票的风险，包括止损止盈、技术破位、资金流出等
支持动态止损止盈：
- 基于波动率调整止损幅度
- 基于持仓时间调整止盈点
- 移动止盈（追踪止盈）
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta

from config.trading_config import RISK_CONFIG, TRADING_CONFIG
from position.analyzer import StockAnalysis
from data.fetcher import get_data_fetcher
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
    FUNDAMENTAL_RISK = "fundamental_risk"  # 基本面风险
    SECTOR_RISK = "sector_risk"      # 行业风险
    LIQUIDITY_RISK = "liquidity_risk"  # 流动性风险
    CONCENTRATION_RISK = "concentration_risk"  # 集中度风险
    MARKET_RISK = "market_risk"      # 市场风险
    SYSTEMIC_RISK = "systemic_risk"    # 系统性风险
    POLICY_RISK = "policy_risk"      # 政策风险


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
    risk_score: float = 0.0  # 风险评分（0-100）


@dataclass
class PortfolioRisk:
    """组合风险评估"""
    total_risk_score: float  # 总风险评分
    risk_level: RiskLevel  # 风险等级
    top_risk_stocks: List[Tuple[str, str, float]]  # 风险最高的股票
    sector_exposure: Dict[str, float]  # 行业暴露
    risk_distribution: Dict[str, int]  # 风险分布
    recommendations: List[str]  # 风险建议


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

        # 风险评分权重（已归一化）
        # 原始权重总和为 2.35，此处已归一化为 1.0
        self.risk_weights = {
            RiskType.STOP_LOSS: 0.128,      # 0.3 / 2.35
            RiskType.MA_BREAKDOWN: 0.106,   # 0.25 / 2.35
            RiskType.CAPITAL_OUTFLOW: 0.085,  # 0.2 / 2.35
            RiskType.TECHNICAL_WEAK: 0.064,  # 0.15 / 2.35
            RiskType.FUNDAMENTAL_RISK: 0.106,  # 0.25 / 2.35
            RiskType.SECTOR_RISK: 0.085,    # 0.2 / 2.35
            RiskType.LIQUIDITY_RISK: 0.064,  # 0.15 / 2.35
            RiskType.CONCENTRATION_RISK: 0.043,  # 0.1 / 2.35
            RiskType.MARKET_RISK: 0.149,    # 0.35 / 2.35
            RiskType.SYSTEMIC_RISK: 0.170,  # 0.4 / 2.35
            RiskType.POLICY_RISK: 0.106,    # 0.25 / 2.35
        }

        self.fetcher = get_data_fetcher()

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
                risk_score=60.0,
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
                risk_score=90.0,
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
                risk_score=70.0,
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
                risk_score=30.0,
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
                risk_score=20.0,
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
                    risk_score=85.0,
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
                    risk_score=65.0,
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
                risk_score=60.0,
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
                risk_score=45.0,
            )

        return None

    def check_liquidity_risk(
        self,
        analysis: StockAnalysis,
    ) -> Optional[RiskWarning]:
        """
        检查流动性风险

        Returns:
            RiskWarning 或 None
        """
        try:
            # 获取成交量数据
            volume_data = self.fetcher.get_stock_prices(analysis.ts_code, count=20)
            if not volume_data.empty:
                avg_volume = volume_data['vol'].mean()
                current_volume = volume_data['vol'].iloc[-1]
                market_value = analysis.market_value or 0

                # 成交量异常萎缩
                if current_volume < avg_volume * 0.3:
                    return RiskWarning(
                        ts_code=analysis.ts_code,
                        stock_name=analysis.stock_name,
                        risk_type=RiskType.LIQUIDITY_RISK,
                        risk_level=RiskLevel.WARNING,
                        message=f"成交量异常萎缩（当前 {current_volume}，平均 {avg_volume}）",
                        current_price=analysis.current_price,
                        trigger_price=None,
                        suggestion="注意流动性风险，避免重仓",
                        risk_score=55.0,
                    )

                # 市值过小
                if market_value < 5000000000:  # 50亿以下
                    return RiskWarning(
                        ts_code=analysis.ts_code,
                        stock_name=analysis.stock_name,
                        risk_type=RiskType.LIQUIDITY_RISK,
                        risk_level=RiskLevel.WATCH,
                        message=f"市值过小（{market_value / 100000000:.1f}亿）",
                        current_price=analysis.current_price,
                        trigger_price=None,
                        suggestion="注意流动性风险，控制仓位",
                        risk_score=40.0,
                    )
        except Exception as e:
            logger.error(f"检查流动性风险失败：{e}")

        return None

    def check_concentration_risk(
        self,
        analyses: List[StockAnalysis],
        position_ratios: Dict[str, float],
    ) -> Optional[RiskWarning]:
        """
        检查集中度风险

        Returns:
            RiskWarning 或 None
        """
        if not analyses or not position_ratios:
            return None

        # 计算前三大持仓占比
        sorted_positions = sorted(position_ratios.items(), key=lambda x: x[1], reverse=True)
        top_three = sorted_positions[:3]
        top_three_ratio = sum(ratio for _, ratio in top_three)

        if top_three_ratio > 0.6:  # 前三大持仓超过60%
            top_stocks = [f"{code}({ratio:.1%})".split('.')[0] for code, ratio in top_three]
            return RiskWarning(
                ts_code="PORTFOLIO",
                stock_name="组合",
                risk_type=RiskType.CONCENTRATION_RISK,
                risk_level=RiskLevel.WARNING,
                message=f"持仓过于集中，前三大持仓占比 {top_three_ratio:.1%}",
                current_price=0.0,
                trigger_price=None,
                suggestion=f"建议分散投资，降低 {', '.join(top_stocks)} 的仓位",
                risk_score=65.0,
            )

        return None

    def check_market_risk(self) -> Optional[RiskWarning]:
        """
        检查市场风险

        Returns:
            RiskWarning 或 None
        """
        try:
            # 获取主要指数数据
            indices = ["000001.SH", "399001.SZ", "399006.SZ"]  # 上证指数、深证成指、创业板指
            index_data = {}
            market_risk_score = 0
            
            for idx in indices:
                df = self.fetcher.get_index_prices(idx, start_date="20230101", end_date="20251231")
                if not df.empty:
                    df = df.sort_values("trade_date")
                    # 计算最近30天收益率
                    if len(df) >= 30:
                        recent = df.tail(30)
                        return_30d = (recent["close"].iloc[-1] / recent["close"].iloc[0] - 1) * 100
                        index_data[idx] = return_30d
            
            # 计算市场风险得分
            if index_data:
                avg_return = sum(index_data.values()) / len(index_data.values())
                
                # 市场大幅下跌
                if avg_return < -10:
                    return RiskWarning(
                        ts_code="MARKET",
                        stock_name="市场",
                        risk_type=RiskType.MARKET_RISK,
                        risk_level=RiskLevel.DANGER,
                        message=f"市场大幅下跌，平均跌幅 {avg_return:.2%}",
                        current_price=0.0,
                        trigger_price=None,
                        suggestion="建议大幅降低仓位，观望为主",
                        risk_score=90.0,
                    )
                elif avg_return < -5:
                    return RiskWarning(
                        ts_code="MARKET",
                        stock_name="市场",
                        risk_type=RiskType.MARKET_RISK,
                        risk_level=RiskLevel.WARNING,
                        message=f"市场明显下跌，平均跌幅 {avg_return:.2%}",
                        current_price=0.0,
                        trigger_price=None,
                        suggestion="建议降低仓位，防御为主",
                        risk_score=70.0,
                    )
                elif avg_return < 0:
                    return RiskWarning(
                        ts_code="MARKET",
                        stock_name="市场",
                        risk_type=RiskType.MARKET_RISK,
                        risk_level=RiskLevel.WATCH,
                        message=f"市场小幅下跌，平均跌幅 {avg_return:.2%}",
                        current_price=0.0,
                        trigger_price=None,
                        suggestion="建议保持谨慎，控制仓位",
                        risk_score=45.0,
                    )
        except Exception as e:
            logger.error(f"检查市场风险失败：{e}")
        
        return None

    def check_systemic_risk(self) -> Optional[RiskWarning]:
        """
        检查系统性风险

        Returns:
            RiskWarning 或 None
        """
        try:
            # 检查北向资金流向
            north_flow = self.fetcher.get_north_flow()
            if not north_flow.empty:
                # 计算最近5个交易日净流出
                if len(north_flow) >= 5:
                    recent_flow = north_flow.tail(5)
                    net_outflow = recent_flow.get("净买入", recent_flow.get("net_amount", 0)).sum()
                    
                    # 北向资金连续大幅流出
                    if net_outflow < -5000000000:  # 50亿以上净流出
                        return RiskWarning(
                            ts_code="SYSTEMIC",
                            stock_name="系统性",
                            risk_type=RiskType.SYSTEMIC_RISK,
                            risk_level=RiskLevel.DANGER,
                            message=f"北向资金连续大幅流出，累计净流出 {net_outflow/100000000:.2f} 亿",
                            current_price=0.0,
                            trigger_price=None,
                            suggestion="建议大幅降低仓位，防范系统性风险",
                            risk_score=95.0,
                        )
                    elif net_outflow < -2000000000:  # 20亿以上净流出
                        return RiskWarning(
                            ts_code="SYSTEMIC",
                            stock_name="系统性",
                            risk_type=RiskType.SYSTEMIC_RISK,
                            risk_level=RiskLevel.WARNING,
                            message=f"北向资金持续流出，累计净流出 {net_outflow/100000000:.2f} 亿",
                            current_price=0.0,
                            trigger_price=None,
                            suggestion="建议降低仓位，关注风险",
                            risk_score=75.0,
                        )
        except Exception as e:
            logger.error(f"检查系统性风险失败：{e}")
        
        return None

    def check_policy_risk(self) -> Optional[RiskWarning]:
        """
        检查政策风险

        Returns:
            RiskWarning 或 None
        """
        try:
            # 获取财经新闻，检查是否有重大政策消息
            today = datetime.now().strftime("%Y%m%d")
            news = self.fetcher.get_financial_news(today)
            
            if not news.empty:
                # 关键词列表
                risk_keywords = ["监管", "限制", "调控", "收紧", "处罚", "反垄断", "退市", "减持"]
                
                risk_news_count = 0
                for _, row in news.iterrows():
                    title = str(row.get("title", ""))
                    content = str(row.get("content", ""))
                    text = title + " " + content
                    
                    for keyword in risk_keywords:
                        if keyword in text:
                            risk_news_count += 1
                            break
                
                if risk_news_count >= 3:
                    return RiskWarning(
                        ts_code="POLICY",
                        stock_name="政策",
                        risk_type=RiskType.POLICY_RISK,
                        risk_level=RiskLevel.WARNING,
                        message=f"检测到 {risk_news_count} 条可能的政策风险新闻",
                        current_price=0.0,
                        trigger_price=None,
                        suggestion="建议关注政策动向，适当降低仓位",
                        risk_score=65.0,
                    )
        except Exception as e:
            logger.error(f"检查政策风险失败：{e}")
        
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

        # 流动性风险检查
        warning = self.check_liquidity_risk(analysis)
        if warning:
            warnings.append(warning)

        # 按风险等级排序
        risk_order = {RiskLevel.DANGER: 0, RiskLevel.WARNING: 1, RiskLevel.WATCH: 2, RiskLevel.NORMAL: 3}
        warnings.sort(key=lambda w: risk_order.get(w.risk_level, 3))

        return warnings

    def calculate_portfolio_risk(
        self,
        analyses: List[StockAnalysis],
        position_ratios: Dict[str, float],
    ) -> PortfolioRisk:
        """
        计算组合风险

        Returns:
            PortfolioRisk: 组合风险评估
        """
        if not analyses:
            return PortfolioRisk(
                total_risk_score=0.0,
                risk_level=RiskLevel.NORMAL,
                top_risk_stocks=[],
                sector_exposure={},
                risk_distribution={},
                recommendations=[],
            )

        # 计算每只股票的风险
        stock_risks = []
        risk_distribution = {}
        sector_exposure = {}

        for analysis in analyses:
            warnings = self.check_all_risks(analysis)
            position_ratio = position_ratios.get(analysis.ts_code, 0)

            # 计算股票风险得分
            if warnings:
                # 取最高风险得分
                max_risk = max(warnings, key=lambda w: w.risk_score)
                risk_score = max_risk.risk_score
                stock_risks.append((analysis.ts_code, analysis.stock_name, risk_score * position_ratio))

                # 统计风险分布
                for w in warnings:
                    risk_type = w.risk_type.value
                    risk_distribution[risk_type] = risk_distribution.get(risk_type, 0) + 1
            else:
                stock_risks.append((analysis.ts_code, analysis.stock_name, 10 * position_ratio))

            # 统计行业暴露
            sector = analysis.industry or "未知"
            sector_exposure[sector] = sector_exposure.get(sector, 0) + position_ratio

        # 计算总风险得分
        total_risk_score = sum(score for _, _, score in stock_risks)

        # 确定风险等级
        if total_risk_score >= 70:
            risk_level = RiskLevel.DANGER
        elif total_risk_score >= 50:
            risk_level = RiskLevel.WARNING
        elif total_risk_score >= 30:
            risk_level = RiskLevel.WATCH
        else:
            risk_level = RiskLevel.NORMAL

        # 排序风险股票
        stock_risks.sort(key=lambda x: x[2], reverse=True)
        top_risk_stocks = stock_risks[:3]

        # 生成建议
        recommendations = []
        if risk_level == RiskLevel.DANGER:
            recommendations.append("组合风险较高，建议降低仓位，特别是高风险股票")
        elif risk_level == RiskLevel.WARNING:
            recommendations.append("组合风险适中，建议关注高风险股票，适当调整仓位")

        # 检查集中度风险
        concentration_warning = self.check_concentration_risk(analyses, position_ratios)
        if concentration_warning:
            recommendations.append(concentration_warning.suggestion)

        # 检查行业集中度
        sorted_sectors = sorted(sector_exposure.items(), key=lambda x: x[1], reverse=True)
        if sorted_sectors and sorted_sectors[0][1] > 0.4:
            recommendations.append(f"行业过于集中，{sorted_sectors[0][0]}占比 {sorted_sectors[0][1]:.1%}，建议分散投资")

        return PortfolioRisk(
            total_risk_score=total_risk_score,
            risk_level=risk_level,
            top_risk_stocks=top_risk_stocks,
            sector_exposure=sector_exposure,
            risk_distribution=risk_distribution,
            recommendations=recommendations,
        )

    def generate_risk_report(
        self,
        analyses: List[StockAnalysis],
        position_ratios: Optional[Dict[str, float]] = None,
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

        # 检查市场风险
        market_warning = self.check_market_risk()
        if market_warning:
            all_warnings.append(market_warning)
            if market_warning.risk_level == RiskLevel.DANGER:
                danger_warnings.append(market_warning)
            elif market_warning.risk_level == RiskLevel.WARNING:
                warning_warnings.append(market_warning)
            else:
                watch_warnings.append(market_warning)

        # 检查系统性风险
        systemic_warning = self.check_systemic_risk()
        if systemic_warning:
            all_warnings.append(systemic_warning)
            if systemic_warning.risk_level == RiskLevel.DANGER:
                danger_warnings.append(systemic_warning)
            elif systemic_warning.risk_level == RiskLevel.WARNING:
                warning_warnings.append(systemic_warning)
            else:
                watch_warnings.append(systemic_warning)

        # 检查政策风险
        policy_warning = self.check_policy_risk()
        if policy_warning:
            all_warnings.append(policy_warning)
            if policy_warning.risk_level == RiskLevel.DANGER:
                danger_warnings.append(policy_warning)
            elif policy_warning.risk_level == RiskLevel.WARNING:
                warning_warnings.append(policy_warning)
            else:
                watch_warnings.append(policy_warning)

        # 计算组合风险
        portfolio_risk = None
        if position_ratios:
            portfolio_risk = self.calculate_portfolio_risk(analyses, position_ratios)

        report = {
            "total_warnings": len(all_warnings),
            "danger_count": len(danger_warnings),
            "warning_count": len(warning_warnings),
            "watch_count": len(watch_warnings),
            "warnings": all_warnings,
            "danger_warnings": danger_warnings,
            "warning_warnings": warning_warnings,
            "watch_warnings": watch_warnings,
            "market_risk": market_warning,
            "systemic_risk": systemic_warning,
            "policy_risk": policy_warning,
        }

        if portfolio_risk:
            report["portfolio_risk"] = portfolio_risk

        return report

    def print_risk_warnings(
        self,
        warnings: List[RiskWarning],
    ):
        """打印风险预警"""
        if not warnings:
            print("【风险警示】无")
            return

        # 按风险类型分组
        risk_groups = {}
        for w in warnings:
            risk_type = w.risk_type.value
            if risk_type not in risk_groups:
                risk_groups[risk_type] = []
            risk_groups[risk_type].append(w)

        # 打印风险预警
        print("【风险警示】")
        
        # 先打印系统性风险
        systemic_risks = ['market_risk', 'systemic_risk', 'policy_risk']
        for risk_type in systemic_risks:
            if risk_type in risk_groups:
                print(f"\n{risk_type.upper()}:")
                for w in risk_groups[risk_type]:
                    emoji = {"danger": "🔴", "warning": "⚠️", "watch": "🟡"}.get(
                        w.risk_level.value, "⚪"
                    )
                    print(f"{emoji} {w.ts_code} {w.stock_name}: {w.message}")
                    print(f"   建议：{w.suggestion}")
                del risk_groups[risk_type]
        
        # 打印其他风险
        if risk_groups:
            print("\n个股风险:")
            for risk_type, group_warnings in risk_groups.items():
                for w in group_warnings:
                    emoji = {"danger": "🔴", "warning": "⚠️", "watch": "🟡"}.get(
                        w.risk_level.value, "⚪"
                    )
                    print(f"{emoji} {w.ts_code} {w.stock_name}: {w.message}")
                    print(f"   建议：{w.suggestion}")

    def print_portfolio_risk(
        self,
        portfolio_risk: PortfolioRisk,
    ):
        """打印组合风险评估"""
        emoji = {"danger": "🔴", "warning": "⚠️", "watch": "🟡", "normal": "✅"}.get(
            portfolio_risk.risk_level.value, "⚪"
        )

        print(f"\n【组合风险评估】{emoji}")
        print(f"总风险评分：{portfolio_risk.total_risk_score:.1f} - {portfolio_risk.risk_level.value}")
        
        if portfolio_risk.top_risk_stocks:
            print("\n风险最高的股票：")
            for code, name, score in portfolio_risk.top_risk_stocks:
                print(f"  • {name} ({code}): {score:.1f}")
        
        if portfolio_risk.sector_exposure:
            print("\n行业暴露：")
            for sector, ratio in sorted(portfolio_risk.sector_exposure.items(), 
                                     key=lambda x: x[1], reverse=True)[:5]:
                print(f"  • {sector}: {ratio:.1%}")
        
        if portfolio_risk.recommendations:
            print("\n风险建议：")
            for rec in portfolio_risk.recommendations:
                print(f"  • {rec}")


def create_risk_monitor() -> RiskMonitor:
    """创建风险监控器实例"""
    return RiskMonitor()
