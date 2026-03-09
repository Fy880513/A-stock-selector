"""
数据获取统一接口模块
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from data.tushare_api import get_tushare_api, TushareAPI
from data.akshare_api import get_akshare_api, AKShareAPI
from utils.logger import get_logger

logger = get_logger(__name__)


class DataFetcher:
    """数据获取统一接口"""

    def __init__(self):
        self.tushare = get_tushare_api()
        self.akshare = get_akshare_api()

    def get_all_stock_codes(self) -> pd.DataFrame:
        """
        获取所有 A 股代码

        Returns:
            DataFrame: 股票代码列表
        """
        return self.tushare.get_stock_list()

    def get_stock_prices(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        获取股票历史价格

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            count: 获取最近 N 天数据（优先于日期范围）

        Returns:
            DataFrame: 价格和成交量数据
        """
        df = self.tushare.get_daily_price(ts_code, start_date, end_date)

        if count and not df.empty:
            df = df.tail(count)

        return df

    def get_market_data(self, trade_date: str) -> pd.DataFrame:
        """
        获取全市场日线数据

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame: 全市场数据
        """
        return self.tushare.get_market_daily(trade_date)

    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """
        获取每日基本指标

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame: PE/PB 等基本指标
        """
        return self.tushare.get_daily_basic(trade_date)

    def get_financial_indicators(self, ts_code: str) -> pd.DataFrame:
        """
        获取财务指标

        Args:
            ts_code: 股票代码

        Returns:
            DataFrame: 财务指标数据
        """
        return self.tushare.get_fina_indicator(ts_code)

    def get_concept_stocks(self) -> pd.DataFrame:
        """
        获取概念板块成分

        Returns:
            DataFrame: 概念板块及成分股
        """
        return self.tushare.get_concept_detail()

    def get_industry_list(self) -> pd.DataFrame:
        """
        获取行业板块列表

        Returns:
            DataFrame: 行业板块
        """
        return self.akshare.get_stock_board_industry_name_em()

    def get_industry_stocks(self, board: str) -> pd.DataFrame:
        """
        获取行业板块成分股

        Args:
            board: 板块名称

        Returns:
            DataFrame: 成分股
        """
        return self.akshare.get_stock_board_industry_cons_em(board)

    def get_industry_history(
        self,
        board: str,
        period: str = "日",
    ) -> pd.DataFrame:
        """
        获取行业板块历史行情

        Args:
            board: 板块名称
            period: 周期

        Returns:
            DataFrame: 板块历史行情
        """
        return self.akshare.get_stock_board_industry_hist_em(board, period)

    def get_realtime_quotes(self) -> pd.DataFrame:
        """
        获取实时行情（所有 A 股）

        Returns:
            DataFrame: 实时行情
        """
        return self.akshare.get_stock_individual_spot_em()

    def get_capital_flow(self, stock: str) -> pd.DataFrame:
        """
        获取个股资金流向

        Args:
            stock: 股票代码

        Returns:
            DataFrame: 资金流向数据
        """
        return self.akshare.get_stock_main_force_em(stock)

    def get_industry_capital_flow(self) -> pd.DataFrame:
        """
        获取行业资金流向

        Returns:
            DataFrame: 行业资金流向
        """
        return self.akshare.get_stock_board_main_force_em()

    def get_lhb_list(
        self,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取龙虎榜列表

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame: 龙虎榜数据
        """
        return self.akshare.get_stock_lhb_detail_em(start_date, end_date)

    def get_north_flow(self) -> pd.DataFrame:
        """
        获取北向资金流向

        Returns:
            DataFrame: 北向资金流向
        """
        return self.akshare.get_stock_hsgt_north_net_flow_in_em()

    def get_north_holdings(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        获取北向资金持仓

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 北向资金持仓
        """
        return self.akshare.get_stock_hsgt_hold_stock_em(date)

    def get_hot_rank(self) -> pd.DataFrame:
        """
        获取股票热度排行

        Returns:
            DataFrame: 热度排行
        """
        return self.akshare.get_stock_hot_rank_em()

    def get_financial_news(self, date: str) -> pd.DataFrame:
        """
        获取财经新闻

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 新闻列表
        """
        return self.akshare.get_news_economic_baidu(date)

    def get_index_prices(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取指数价格

        Args:
            ts_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            DataFrame: 指数价格
        """
        return self.tushare.get_index_daily(ts_code, start_date, end_date)

    def get_trade_calendar(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        获取交易日历

        Returns:
            DataFrame: 交易日历
        """
        return self.tushare.get_tradecal(year)


# 单例模式
_fetcher_instance: Optional[DataFetcher] = None


def get_data_fetcher() -> DataFetcher:
    """获取数据获取器单例"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DataFetcher()
    return _fetcher_instance
