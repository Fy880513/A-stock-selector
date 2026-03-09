"""
AKShare API 封装模块

AKShare: 开源财经数据接口库
GitHub: https://github.com/akfamily/akshare
完全免费，但稳定性依赖于源网站
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
import warnings

from utils.logger import get_logger

logger = get_logger(__name__)

# 忽略警告
warnings.filterwarnings("ignore")


class AKShareAPI:
    """AKShare API 封装类"""

    def __init__(self):
        self._akshare = None

    def _import_akshare(self):
        """延迟导入 akshare"""
        if self._akshare is None:
            try:
                import akshare as ak
                self._akshare = ak
                logger.info("AKShare 加载成功")
            except ImportError:
                logger.error("AKShare 未安装，请运行：pip install akshare")
                raise
        return self._akshare

    def get_stock_board_industry_name_em(self) -> pd.DataFrame:
        """
        获取行业板块名称

        Returns:
            DataFrame: 行业板块列表
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            logger.error(f"获取行业板块失败：{e}")
            return pd.DataFrame()

    def get_stock_board_industry_cons_em(self, board: str) -> pd.DataFrame:
        """
        获取行业板块成分股

        Args:
            board: 板块名称

        Returns:
            DataFrame: 成分股列表
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_board_industry_cons_em(symbol=board)
            return df
        except Exception as e:
            logger.error(f"获取板块成分失败：{e}")
            return pd.DataFrame()

    def get_stock_board_industry_hist_em(
        self,
        board: str,
        period: str = "日",
    ) -> pd.DataFrame:
        """
        获取行业板块历史行情

        Args:
            board: 板块名称
            period: 周期 (日/周/月)

        Returns:
            DataFrame: 板块历史行情
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_board_industry_hist_em(
                symbol=board,
                period=period,
            )
            return df
        except Exception as e:
            logger.error(f"获取板块行情失败：{e}")
            return pd.DataFrame()

    def get_stock_individual_spot_em(self) -> pd.DataFrame:
        """
        获取个股实时行情（所有股票）

        Returns:
            DataFrame: 实时行情数据
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            logger.error(f"获取实时行情失败：{e}")
            return pd.DataFrame()

    def get_stock_individual_info_em(self, stock: str) -> dict:
        """
        获取个股基本信息

        Args:
            stock: 股票代码 (如 "000001")

        Returns:
            dict: 股票基本信息
        """
        try:
            ak = self._import_akshare()
            result = ak.stock_individual_info_em(symbol=stock)
            return result
        except Exception as e:
            logger.error(f"获取个股信息失败：{e}")
            return {}

    def get_stock_main_force_em(self, stock: str) -> pd.DataFrame:
        """
        获取个股主力资金流向

        Args:
            stock: 股票代码

        Returns:
            DataFrame: 主力资金流向
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_individual_fund_flow(
                stock=stock,
                market="sh" if stock.startswith("6") else "sz",
            )
            return df
        except Exception as e:
            logger.error(f"获取资金流向失败：{e}")
            return pd.DataFrame()

    def get_stock_board_main_force_em(self) -> pd.DataFrame:
        """
        获取板块主力资金流向

        Returns:
            DataFrame: 板块资金流向
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_board_industry_fund_flow_em()
            return df
        except Exception as e:
            logger.error(f"获取板块资金流向失败：{e}")
            return pd.DataFrame()

    def get_stock_lhb_detail_em(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取龙虎榜详情

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame: 龙虎榜数据
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_lhb_detail_em(
                start_date=start_date,
                end_date=end_date,
            )
            return df
        except Exception as e:
            logger.error(f"获取龙虎榜失败：{e}")
            return pd.DataFrame()

    def get_stock_lhb_stock_detail_em(
        self,
        stock: str,
        indicator: str = "日",
    ) -> pd.DataFrame:
        """
        获取个股龙虎榜详情

        Args:
            stock: 股票代码
            indicator: 周期

        Returns:
            DataFrame: 个股龙虎榜数据
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_lhb_stock_detail_em(
                symbol=stock,
                indicator=indicator,
            )
            return df
        except Exception as e:
            logger.error(f"获取个股龙虎榜失败：{e}")
            return pd.DataFrame()

    def get_stock_margin_underlying_info_szse(
        self,
        stock: str,
    ) -> pd.DataFrame:
        """
        获取融资融券数据（深市）

        Args:
            stock: 股票代码

        Returns:
            DataFrame: 融资融券数据
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_margin_underlying_info_szse(symbol=stock)
            return df
        except Exception as e:
            logger.error(f"获取融资融券失败：{e}")
            return pd.DataFrame()

    def get_stock_margin_sse(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取融资融券汇总（沪市）

        Returns:
            DataFrame: 融资融券汇总
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_margin_sse(
                start_date=start_date,
                end_date=end_date,
            )
            return df
        except Exception as e:
            logger.error(f"获取融资融券汇总失败：{e}")
            return pd.DataFrame()

    def get_news_economic_baidu(self, date: str) -> pd.DataFrame:
        """
        获取财经新闻（百度）

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 财经新闻列表
        """
        try:
            ak = self._import_akshare()
            df = ak.news_economic_baidu(date=date)
            return df
        except Exception as e:
            logger.error(f"获取财经新闻失败：{e}")
            return pd.DataFrame()

    def get_news_sentiment_baidu(self, symbol: str = "市场快讯") -> pd.DataFrame:
        """
        获取新闻情绪分析

        Returns:
            DataFrame: 新闻情绪
        """
        try:
            ak = self._import_akshare()
            df = ak.news_sentiment_baidu(symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"获取新闻情绪失败：{e}")
            return pd.DataFrame()

    def get_stock_hot_rank_em(self) -> pd.DataFrame:
        """
        获取个股热度排行榜

        Returns:
            DataFrame: 股票热度排行
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_hot_rank_em()
            return df
        except Exception as e:
            logger.error(f"获取股票热度失败：{e}")
            return pd.DataFrame()

    def get_stock_concept_fund_flow_hist(self) -> pd.DataFrame:
        """
        获取概念板块资金流向历史

        Returns:
            DataFrame: 概念资金流向
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_concept_fund_flow_hist()
            return df
        except Exception as e:
            logger.error(f"获取概念资金流向失败：{e}")
            return pd.DataFrame()

    def get_stock_hsgt_north_net_flow_in_em(
        self,
        symbol: str = "北向资金",
    ) -> pd.DataFrame:
        """
        获取北向资金净流入

        Args:
            symbol: 北向资金/沪股通/深股通

        Returns:
            DataFrame: 北向资金流向
        """
        try:
            ak = self._import_akshare()
            df = ak.stock_hsgt_north_net_flow_in_em(symbol=symbol)
            return df
        except Exception as e:
            logger.error(f"获取北向资金失败：{e}")
            return pd.DataFrame()

    def get_stock_hsgt_hold_stock_em(
        self,
        date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取北向资金持仓

        Args:
            date: 日期 YYYYMMDD

        Returns:
            DataFrame: 北向资金持仓
        """
        try:
            ak = self._import_akshare()
            if date:
                df = ak.stock_hsgt_hold_stock_em(date=date)
            else:
                df = ak.stock_hsgt_hold_stock_em()
            return df
        except Exception as e:
            logger.error(f"获取北向资金持仓失败：{e}")
            return pd.DataFrame()


# 单例模式
_api_instance: Optional[AKShareAPI] = None


def get_akshare_api() -> AKShareAPI:
    """获取 AKShare API 单例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = AKShareAPI()
    return _api_instance
