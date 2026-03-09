"""
选股引擎核心模块

整合数据获取、因子计算、综合评分，执行完整选股流程
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from data.fetcher import get_data_fetcher, DataFetcher
from factors.fundamentals import calculate_fundamental_score
from factors.technicals import calculate_technical_score
from factors.capital_flow import calculate_capital_flow_score
from factors.hotspots import calculate_hotspot_score
from selector.scorer import create_scorer, StockScore
from selector.portfolio import create_portfolio_manager
from utils.logger import get_logger
from utils.helpers import is_st_stock, is_new_stock

logger = get_logger(__name__)


@dataclass
class SelectionResult:
    """选股结果"""
    select_date: str
    stocks: List[StockScore]
    total_count: int
    message: str


class StockScreener:
    """选股引擎"""

    def __init__(self):
        self.fetcher = get_data_fetcher()
        self.scorer = create_scorer()
        self.portfolio = create_portfolio_manager()

    def get_trade_date(self, target_date: Optional[str] = None) -> str:
        """
        获取交易日期

        如果目标日期不是交易日，返回前一个交易日
        """
        if target_date is None:
            target_date = datetime.now().strftime("%Y%m%d")

        # 简单处理：假设工作日为交易日
        # 实际使用中可以调用交易日历 API
        try:
            dt = datetime.strptime(target_date, "%Y%m%d")
            if dt.weekday() >= 5:  # 周末
                dt -= timedelta(days=dt.weekday() - 4)
            return dt.strftime("%Y%m%d")
        except ValueError:
            return datetime.now().strftime("%Y%m%d")

    def filter_basic(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        基础筛选

        排除：
        - ST/*ST 股票
        - 上市不满 1 年的新股
        - 停牌股票
        """
        if df.empty:
            return df

        # 排除 ST 股票
        if "name" in df.columns:
            df = df[~df["name"].apply(lambda x: "ST" in str(x) or "*ST" in str(x))]

        # 排除停牌（涨跌幅为 0 且成交量为 0）
        if "pct_chg" in df.columns and "vol" in df.columns:
            df = df[(df["pct_chg"] != 0) | (df["vol"] != 0)]

        return df

    def calculate_fundamental(
        self,
        ts_code: str,
        daily_basic: Optional[pd.Series] = None,
        fina_data: Optional[pd.DataFrame] = None,
    ) -> Dict[str, float]:
        """计算基本面得分"""
        # 从 daily_basic 获取估值数据
        pe_ttm = None
        pb = None

        if daily_basic is not None and not daily_basic.empty:
            pe_ttm = daily_basic.get("pe_ttm")
            pb = daily_basic.get("pb")

        # 从财务数据获取成长性和盈利性指标
        revenue_growth = None
        net_profit_growth = None
        roe = None
        gross_margin = None
        net_margin = None
        debt_to_asset = None
        current_ratio = None

        if fina_data is not None and not fina_data.empty:
            latest = fina_data.iloc[0] if len(fina_data) > 0 else None
            if latest is not None:
                revenue_growth = latest.get("revenue_gr")
                net_profit_growth = latest.get("netprofit_gr")
                roe = latest.get("roe")
                gross_margin = latest.get("gross_margin")
                net_margin = latest.get("net_margin")
                debt_to_asset = latest.get("debt_to_assets")
                current_ratio = latest.get("current_ratio")

        # 计算 PEG
        peg = None
        if pe_ttm and net_profit_growth and net_profit_growth > 0:
            peg = pe_ttm / (net_profit_growth * 100)  # 增长率转百分比

        return calculate_fundamental_score(
            pe_ttm=pe_ttm,
            peg=peg,
            revenue_growth=revenue_growth,
            net_profit_growth=net_profit_growth,
            roe=roe,
            gross_margin=gross_margin,
            debt_to_asset=debt_to_asset,
            current_ratio=current_ratio,
            net_margin=net_margin,
        )

    def calculate_technical(
        self,
        ts_code: str,
        price_data: pd.DataFrame,
    ) -> Dict[str, float]:
        """计算技术面得分"""
        if price_data is None or price_data.empty or len(price_data) < 30:
            return {"technical_score": 50.0, "signal_count": 0}

        # 准备数据格式
        df = price_data.copy()
        if "trade_date" in df.columns:
            df = df.sort_values("trade_date")

        return calculate_technical_score(df)

    def calculate_capital_flow(
        self,
        ts_code: str,
    ) -> Dict[str, float]:
        """计算资金面得分"""
        # 由于实时数据获取成本高，这里先返回基础分数
        # 实际使用中可以调用 AKShare 获取真实数据
        return calculate_capital_flow_score(
            main_force_net_inflows=[],
            north_hold_ratio=None,
            north_hold_change=None,
            north_consecutive_days=0,
            lhb_count_5d=0,
            lhb_net_buy=0,
            has_institution=False,
            margin_change=None,
            large_order_ratio=0,
            super_order_ratio=0,
        )

    def calculate_hotspot(
        self,
        ts_code: str,
        stock_name: str,
        industry: str = "",
    ) -> Dict[str, float]:
        """计算热点面得分"""
        # 简化版本，返回基础分数
        return calculate_hotspot_score(
            industry_change_1d=0,
            industry_change_5d=0,
            industry_rank_5d=0,
            total_industries=30,
            concept_changes=[],
            limit_up_count=0,
            limit_up_ratio=0,
            consecutive_limit_up=0,
            news_count=0,
            news_positive_ratio=0.5,
            has_policy_news=False,
            policy_level="local",
            is_main_theme=False,
        )

    def select(
        self,
        trade_date: Optional[str] = None,
        top_n: int = 10,
        min_score: float = 60.0,
    ) -> SelectionResult:
        """
        执行选股

        Args:
            trade_date: 交易日期 YYYYMMDD
            top_n: 选出股票数量
            min_score: 最低综合得分

        Returns:
            SelectionResult: 选股结果
        """
        trade_date = self.get_trade_date(trade_date)
        logger.info(f"开始选股，日期：{trade_date}")

        # 1. 获取全市场数据
        daily_basic = self.fetcher.get_daily_basic(trade_date)
        if daily_basic is None or daily_basic.empty:
            return SelectionResult(
                select_date=trade_date,
                stocks=[],
                total_count=0,
                message="获取市场数据失败",
            )

        # 2. 基础筛选
        daily_basic = self.filter_basic(daily_basic)
        logger.info(f"基础筛选后剩余 {len(daily_basic)} 只股票")

        # 3. 对每只股票计算得分
        all_scores: List[StockScore] = []

        for _, row in daily_basic.iterrows():
            ts_code = row.get("ts_code", "")
            stock_name = row.get("name", "")

            if not ts_code:
                continue

            # 获取价格数据（最近 60 天）
            price_data = self.fetcher.get_stock_prices(ts_code, count=60)

            # 计算各维度得分
            fundamental_data = self.calculate_fundamental(ts_code, row)
            technical_data = self.calculate_technical(ts_code, price_data)
            capital_flow_data = self.calculate_capital_flow(ts_code)
            hotspot_data = self.calculate_hotspot(ts_code, stock_name)

            # 创建得分对象
            stock_score = self.scorer.create_stock_score(
                ts_code=ts_code,
                stock_name=stock_name,
                fundamental_data=fundamental_data,
                technical_data=technical_data,
                capital_flow_data=capital_flow_data,
                hotspot_data=hotspot_data,
            )

            all_scores.append(stock_score)

        logger.info(f"完成 {len(all_scores)} 只股票评分")

        # 4. 筛选和排名
        selected = self.scorer.filter_stocks(
            all_scores,
            min_total_score=min_score,
            min_signal_count=3,
            top_n=top_n,
        )

        # 5. 设置排名
        for i, stock in enumerate(selected):
            stock.rank = i + 1

        # 6. 添加价格和仓位信息
        for stock in selected:
            # 获取最新价格
            price_row = daily_basic[daily_basic["ts_code"] == stock.ts_code]
            if not price_row.empty:
                stock.buy_price = price_row.iloc[0].get("close", 0)
                stock.ma20 = None  # 可以从 price_data 获取
                stock.ma60 = None

        result_stocks = selected

        message = f"选出 {len(result_stocks)} 只股票，最高得分：{result_stocks[0].total_score if result_stocks else 0}"

        return SelectionResult(
            select_date=trade_date,
            stocks=result_stocks,
            total_count=len(result_stocks),
            message=message,
        )

    def select_with_portfolio(
        self,
        trade_date: Optional[str] = None,
        top_n: int = 10,
    ) -> Dict:
        """
        执行选股并生成仓位建议

        Returns:
            dict: 选股结果和仓位建议
        """
        result = self.select(trade_date, top_n)

        if not result.stocks:
            return {
                "select_date": result.select_date,
                "message": result.message,
                "stocks": [],
                "portfolio": {},
            }

        # 准备仓位计算数据
        stocks_data = []
        for stock in result.stocks:
            stocks_data.append({
                "ts_code": stock.ts_code,
                "stock_name": stock.stock_name,
                "close_price": getattr(stock, "buy_price", 0),
            })

        # 计算仓位
        positions = self.portfolio.calculate_positions(stocks_data)
        portfolio_report = self.portfolio.generate_position_report(positions)

        # 合并结果
        output_stocks = []
        for i, stock in enumerate(result.stocks):
            stock_dict = {
                "rank": stock.rank,
                "ts_code": stock.ts_code,
                "stock_name": stock.stock_name,
                "total_score": stock.total_score,
                "fundamental_score": stock.fundamental_score,
                "technical_score": stock.technical_score,
                "capital_flow_score": stock.capital_flow_score,
                "hotspot_score": stock.hotspot_score,
                "signal_count": stock.signal_count,
            }

            if i < len(positions):
                pos = positions[i]
                stock_dict.update({
                    "buy_price": pos.buy_price,
                    "target_shares": pos.target_shares,
                    "target_amount": pos.target_amount,
                    "stop_loss": pos.stop_loss_price,
                    "stop_profit": pos.stop_profit_price,
                    "position_ratio": round(pos.position_ratio * 100, 1),
                })

            output_stocks.append(stock_dict)

        return {
            "select_date": result.select_date,
            "message": result.message,
            "stocks": output_stocks,
            "portfolio": portfolio_report,
        }


def get_screener() -> StockScreener:
    """获取选股引擎单例"""
    return StockScreener()
