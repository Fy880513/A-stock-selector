"""
Tushare API 封装模块

Tushare Pro: https://tushare.pro/
注册送 100 积分，基础数据足够使用
"""
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import Optional
import time
import json
from pathlib import Path

from config.settings import TUSHARE_TOKEN, TUSHARE_API_URL, DATA_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


class TushareAPI:
    """Tushare API 封装类"""

    def __init__(self, token: Optional[str] = None):
        self.token = token or TUSHARE_TOKEN
        self.api_url = TUSHARE_API_URL
        self.cache_dir = DATA_DIR / "tushare_cache"
        self.cache_dir.mkdir(exist_ok=True)

        if not self.token:
            logger.warning("Tushare Token 未配置，部分功能可能无法使用")

        # 积分限制控制
        self.last_call_time = 0
        self.min_call_interval = 0.1  # 最小调用间隔（秒）

    def _request(self, api_name: str, params: dict) -> Optional[dict]:
        """发送 API 请求"""
        # 限流控制
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_call_interval:
            time.sleep(self.min_call_interval - elapsed)

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "api_name": api_name,
            "token": self.token,
            "params": params,
            "fields": ""
        }

        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            self.last_call_time = time.time()

            if result.get("code") != 0:
                logger.error(f"Tushare API 错误：{result.get('msg')}")
                return None

            return result.get("data")

        except requests.exceptions.RequestException as e:
            logger.error(f"请求失败：{e}")
            return None

    def _get_cached_data(self, cache_key: str, days: int = 1) -> Optional[pd.DataFrame]:
        """获取缓存数据"""
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        if cache_file.exists():
            try:
                df = pd.read_pickle(cache_file)
                # 检查缓存是否过期
                mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if datetime.now() - mtime < timedelta(days=days):
                    return df
            except Exception as e:
                logger.warning(f"读取缓存失败：{e}")
        return None

    def _save_cached_data(self, cache_key: str, df: pd.DataFrame):
        """保存缓存数据"""
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        try:
            df.to_pickle(cache_file)
        except Exception as e:
            logger.warning(f"保存缓存失败：{e}")

    def get_stock_list(self) -> pd.DataFrame:
        """
        获取 A 股列表

        Returns:
            DataFrame: ts_code, symbol, name, area, industry, list_date, etc.
        """
        cache_key = "stock_list"
        cached = self._get_cached_data(cache_key, days=7)
        if cached is not None:
            return cached

        data = self._request("stock_basic", {"exchange": "", "curr_status": "1"})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()

    def get_daily_price(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取日线行情

        Args:
            ts_code: 股票代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame: ts_code, trade_date, open, high, low, close, vol, amount, etc.
        """
        cache_key = f"daily_{ts_code}"
        cached = self._get_cached_data(cache_key, days=1)
        if cached is not None:
            df = cached
        else:
            # 获取最近 300 天的数据
            if end_date is None:
                end_dt = datetime.now()
            else:
                end_dt = datetime.strptime(end_date, "%Y%m%d")

            if start_date is None:
                start_dt = end_dt - timedelta(days=300)
                start_date = start_dt.strftime("%Y%m%d")
            if end_date is None:
                end_date = end_dt.strftime("%Y%m%d")

            data = self._request("daily", {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date,
            })

            if data and "fields" in data and "items" in data:
                df = pd.DataFrame(data["items"], columns=data["fields"])
                self._save_cached_data(cache_key, df)
            else:
                return pd.DataFrame()

        # 筛选日期范围
        if start_date or end_date:
            if not df.empty:
                df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
                if start_date:
                    df = df[df["trade_date"] >= pd.to_datetime(start_date, format="%Y%m%d")]
                if end_date:
                    df = df[df["trade_date"] <= pd.to_datetime(end_date, format="%Y%m%d")]

        return df

    def get_market_daily(
        self,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        获取全市场日线数据（用于批量选股）

        Args:
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame: 全市场股票日线数据
        """
        if end_date is None:
            end_date = start_date

        data = self._request("daily", {
            "trade_date": start_date,
        })

        if data and "fields" in data and "items" in data:
            return pd.DataFrame(data["items"], columns=data["fields"])

        return pd.DataFrame()

    def get_fina_indicator(self, ts_code: str) -> pd.DataFrame:
        """
        获取财务指标数据

        Returns:
            DataFrame: 主要财务指标
        """
        cache_key = f"fina_{ts_code}"
        cached = self._get_cached_data(cache_key, days=30)
        if cached is not None:
            return cached

        data = self._request("fina_indicator", {"ts_code": ts_code})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()

    def get_fina_mainbz(self, ts_code: str) -> pd.DataFrame:
        """
        获取主营业务财务数据

        Returns:
            DataFrame: 主营业务财务指标
        """
        data = self._request("fina_mainbz", {
            "ts_code": ts_code,
            "report_type": "4",  # 年报
        })

        if data and "fields" in data and "items" in data:
            return pd.DataFrame(data["items"], columns=data["fields"])

        return pd.DataFrame()

    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """
        获取每日基本行情（市盈率、市净率等）

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            DataFrame: 全市场基本行情
        """
        cache_key = f"daily_basic_{trade_date}"
        cached = self._get_cached_data(cache_key, days=1)
        if cached is not None:
            return cached

        data = self._request("daily_basic", {"trade_date": trade_date})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()

    def get_concept_detail(self) -> pd.DataFrame:
        """
        获取概念板块成分

        Returns:
            DataFrame: 概念板块及成分股
        """
        cache_key = "concept_detail"
        cached = self._get_cached_data(cache_key, days=7)
        if cached is not None:
            return cached

        data = self._request("concept_detail", {})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()

    def get_index_basic(self) -> pd.DataFrame:
        """
        获取指数基本信息

        Returns:
            DataFrame: 指数列表
        """
        cache_key = "index_basic"
        cached = self._get_cached_data(cache_key, days=30)
        if cached is not None:
            return cached

        data = self._request("index_basic", {"market": "SSE,SZSE"})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()

    def get_index_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取指数行情

        Args:
            ts_code: 指数代码
            start_date: 开始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            DataFrame: 指数日线数据
        """
        data = self._request("index_daily", {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date,
        })

        if data and "fields" in data and "items" in data:
            return pd.DataFrame(data["items"], columns=data["fields"])

        return pd.DataFrame()

    def get_tradecal(self, year: Optional[int] = None) -> pd.DataFrame:
        """
        获取交易日历

        Returns:
            DataFrame: 交易日历
        """
        if year is None:
            year = datetime.now().year

        cache_key = f"tradecal_{year}"
        cached = self._get_cached_data(cache_key, days=365)
        if cached is not None:
            return cached

        data = self._request("tradecal", {"year": year, "is_open": "1"})

        if data and "fields" in data and "items" in data:
            df = pd.DataFrame(data["items"], columns=data["fields"])
            self._save_cached_data(cache_key, df)
            return df

        return pd.DataFrame()


# 单例模式
_api_instance: Optional[TushareAPI] = None


def get_tushare_api() -> TushareAPI:
    """获取 Tushare API 单例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = TushareAPI()
    return _api_instance
