"""
数据获取统一接口模块
"""
import pandas as pd
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import functools

from data.tushare_api import get_tushare_api, TushareAPI
from data.akshare_api import get_akshare_api, AKShareAPI
from utils.logger import get_logger

logger = get_logger(__name__)


# 重试装饰器
def retry(max_attempts: int = 3, delay_seconds: float = 1.0):
    """重试装饰器"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"尝试 {attempt+1}/{max_attempts} 失败: {e}")
                    if attempt < max_attempts - 1:
                        import time
                        time.sleep(delay_seconds)
            logger.error(f"所有尝试都失败: {last_exception}")
            raise last_exception
        return wrapper
    return decorator

# 改进的缓存装饰器
def cache_result(expire_seconds: int = 3600, max_size: int = 1000):
    """缓存结果装饰器"""
    def decorator(func):
        cache = {}
        cache_order = []  # 用于LRU缓存管理
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key = str(args) + str(sorted(kwargs.items()))
            now = datetime.now().timestamp()
            
            # 检查缓存是否有效
            if key in cache:
                value, timestamp = cache[key]
                if now - timestamp < expire_seconds:
                    # 更新访问顺序
                    if key in cache_order:
                        cache_order.remove(key)
                    cache_order.append(key)
                    return value
                else:
                    # 缓存过期，删除
                    del cache[key]
                    if key in cache_order:
                        cache_order.remove(key)
            
            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            
            # 缓存大小管理
            if len(cache) >= max_size:
                # 删除最久未使用的
                oldest_key = cache_order.pop(0)
                if oldest_key in cache:
                    del cache[oldest_key]
            
            # 存储新结果
            cache[key] = (result, now)
            cache_order.append(key)
            return result
        
        return wrapper
    return decorator


class DataFetcher:
    """数据获取统一接口"""

    def __init__(self):
        self.tushare = get_tushare_api()
        self.akshare = get_akshare_api()
        self._cache = {}

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
    def get_all_stock_codes(self) -> pd.DataFrame:
        """
        获取所有 A 股代码

        Returns:
            DataFrame: 股票代码列表
        """
        try:
            return self.tushare.get_stock_list()
        except Exception as e:
            logger.error(f"获取股票列表失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=1800)
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
        try:
            df = self.tushare.get_daily_price(ts_code, start_date, end_date)

            if count and not df.empty:
                df = df.tail(count)

            return df
        except Exception as e:
            logger.error(f"获取股票价格失败 {ts_code}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
    def get_market_data(self, trade_date: str) -> pd.DataFrame:
        """
        获取全市场日线数据

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame: 全市场数据
        """
        try:
            return self.tushare.get_market_daily(trade_date)
        except Exception as e:
            logger.error(f"获取市场数据失败 {trade_date}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """
        获取每日基本指标

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame: PE/PB 等基本指标
        """
        try:
            return self.tushare.get_daily_basic(trade_date)
        except Exception as e:
            logger.error(f"获取每日基本指标失败 {trade_date}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=7200)
    def get_financial_indicators(self, ts_code: str) -> pd.DataFrame:
        """
        获取财务指标

        Args:
            ts_code: 股票代码

        Returns:
            DataFrame: 财务指标数据
        """
        try:
            return self.tushare.get_fina_indicator(ts_code)
        except Exception as e:
            logger.error(f"获取财务指标失败 {ts_code}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=7200)
    def get_concept_stocks(self) -> pd.DataFrame:
        """
        获取概念板块成分

        Returns:
            DataFrame: 概念板块及成分股
        """
        try:
            return self.tushare.get_concept_detail()
        except Exception as e:
            logger.error(f"获取概念板块失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=7200)
    def get_industry_list(self) -> pd.DataFrame:
        """
        获取行业板块列表

        Returns:
            DataFrame: 行业板块
        """
        try:
            return self.akshare.get_stock_board_industry_name_em()
        except Exception as e:
            logger.error(f"获取行业板块列表失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=7200)
    def get_industry_stocks(self, board: str) -> pd.DataFrame:
        """
        获取行业板块成分股

        Args:
            board: 板块名称

        Returns:
            DataFrame: 成分股
        """
        try:
            return self.akshare.get_stock_board_industry_cons_em(board)
        except Exception as e:
            logger.error(f"获取板块成分股失败 {board}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
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
        try:
            return self.akshare.get_stock_board_industry_hist_em(board, period)
        except Exception as e:
            logger.error(f"获取板块历史行情失败 {board}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=300)
    def get_realtime_quotes(self) -> pd.DataFrame:
        """
        获取实时行情（所有 A 股）

        Returns:
            DataFrame: 实时行情
        """
        try:
            return self.akshare.get_stock_individual_spot_em()
        except Exception as e:
            logger.error(f"获取实时行情失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=600)
    def get_capital_flow(self, stock: str) -> pd.DataFrame:
        """
        获取个股资金流向

        Args:
            stock: 股票代码

        Returns:
            DataFrame: 资金流向数据
        """
        try:
            return self.akshare.get_stock_main_force_em(stock)
        except Exception as e:
            logger.error(f"获取资金流向失败 {stock}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=600)
    def get_industry_capital_flow(self) -> pd.DataFrame:
        """
        获取行业资金流向

        Returns:
            DataFrame: 行业资金流向
        """
        try:
            return self.akshare.get_stock_board_main_force_em()
        except Exception as e:
            logger.error(f"获取行业资金流向失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
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
        try:
            return self.akshare.get_stock_lhb_detail_em(start_date, end_date)
        except Exception as e:
            logger.error(f"获取龙虎榜数据失败 {start_date}-{end_date}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=300)
    def get_north_flow(self) -> pd.DataFrame:
        """
        获取北向资金流向

        Returns:
            DataFrame: 北向资金流向
        """
        try:
            return self.akshare.get_stock_hsgt_north_net_flow_in_em()
        except Exception as e:
            logger.error(f"获取北向资金流向失败：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=3600)
    def get_north_holdings(self, date: Optional[str] = None) -> pd.DataFrame:
        """
        获取北向资金持仓

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 北向资金持仓
        """
        try:
            return self.akshare.get_stock_hsgt_hold_stock_em(date)
        except Exception as e:
            logger.error(f"获取北向资金持仓失败 {date}：{e}")
            return pd.DataFrame()

    @retry(max_attempts=3, delay_seconds=1.0)
    @cache_result(expire_seconds=600)
    def get_hot_rank(self) -> pd.DataFrame:
        """
        获取股票热度排行

        Returns:
            DataFrame: 热度排行
        """
        try:
            return self.akshare.get_stock_hot_rank_em()
        except Exception as e:
            logger.error(f"获取热度排行失败：{e}")
            return pd.DataFrame()

    @cache_result(expire_seconds=3600)
    def get_financial_news(self, date: str) -> pd.DataFrame:
        """
        获取财经新闻

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 新闻列表
        """
        try:
            return self.akshare.get_news_economic_baidu(date)
        except Exception as e:
            logger.error(f"获取财经新闻失败 {date}：{e}")
            return pd.DataFrame()

    @cache_result(expire_seconds=3600)
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
        try:
            return self.tushare.get_index_daily(ts_code, start_date, end_date)
        except Exception as e:
            logger.error(f"获取指数价格失败 {ts_code}：{e}")
            return pd.DataFrame()

    @cache_result(expire_seconds=86400)
    def get_trade_calendar(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        获取交易日历

        Returns:
            DataFrame: 交易日历
        """
        try:
            return self.tushare.get_tradecal(year)
        except Exception as e:
            logger.error(f"获取交易日历失败 {year}：{e}")
            return pd.DataFrame()

    async def get_stock_prices_async(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        异步获取股票历史价格

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            count: 获取最近 N 天数据（优先于日期范围）

        Returns:
            DataFrame: 价格和成交量数据
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.get_stock_prices,
            ts_code,
            start_date,
            end_date,
            count
        )

    async def get_multiple_stock_prices(
        self,
        stock_codes: List[str],
        count: int = 30,
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个股票的历史价格

        Args:
            stock_codes: 股票代码列表
            count: 获取最近 N 天数据

        Returns:
            Dict[str, DataFrame]: 股票代码到价格数据的映射
        """
        tasks = []
        for code in stock_codes:
            task = self.get_stock_prices_async(code, count=count)
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return dict(zip(stock_codes, results))


# 单例模式
_fetcher_instance: Optional[DataFetcher] = None


def get_data_fetcher() -> DataFetcher:
    """获取数据获取器单例"""
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DataFetcher()
    return _fetcher_instance
