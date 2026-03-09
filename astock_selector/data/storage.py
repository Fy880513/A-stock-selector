"""
数据存储模块

使用 SQLite 存储历史数据，支持增量更新
"""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import Optional, List

from config.settings import DATABASE_URL, DATA_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


class Storage:
    """数据存储类"""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DATABASE_URL
        self.db_path = self.db_url.replace("sqlite:///", "")
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 股票价格表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    pre_close REAL,
                    change REAL,
                    pct_chg REAL,
                    vol REAL,
                    amount REAL,
                    UNIQUE(ts_code, trade_date)
                )
            """)

            # 基本面数据表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fundamentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    pe_ttm REAL,
                    pb REAL,
                    ps_ttm REAL,
                    total_mv REAL,
                    circ_mv REAL,
                    turn_over_rate REAL,
                    volume_ratio REAL,
                    UNIQUE(ts_code, report_date)
                )
            """)

            # 财务指标表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS financial_indicators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    ann_date TEXT NOT NULL,
                    revenue_gr REAL,
                    netprofit_gr REAL,
                    roe REAL,
                    gross_margin REAL,
                    net_margin REAL,
                    debt_to_assets REAL,
                    current_ratio REAL,
                    UNIQUE(ts_code, ann_date)
                )
            """)

            # 资金流向表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS capital_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    main_net_inflow REAL,
                    sm_net_inflow REAL,
                    md_net_inflow REAL,
                    lg_net_inflow REAL,
                    super_net_inflow REAL,
                    UNIQUE(ts_code, trade_date)
                )
            """)

            # 北向资金持仓表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS north_holdings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    hold_vol REAL,
                    hold_ratio REAL,
                    UNIQUE(ts_code, trade_date)
                )
            """)

            # 行业板块表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS industry_board (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    board_name TEXT NOT NULL,
                    UNIQUE(ts_code, board_name)
                )
            """)

            # 概念板块表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concept_board (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    board_name TEXT NOT NULL,
                    UNIQUE(ts_code, board_name)
                )
            """)

            # 选股结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS selection_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    select_date TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    stock_name TEXT,
                    total_score REAL,
                    fundamental_score REAL,
                    technical_score REAL,
                    capital_score REAL,
                    hotspot_score REAL,
                    buy_price REAL,
                    target_position INT,
                    stop_loss REAL,
                    stop_profit REAL,
                    UNIQUE(select_date, ts_code)
                )
            """)

            # 追踪结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tracking_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    select_date TEXT NOT NULL,
                    ts_code TEXT NOT NULL,
                    track_date TEXT NOT NULL,
                    close_price REAL,
                    change_pct REAL,
                    holding_return REAL,
                    is_out INT DEFAULT 0,
                    out_reason TEXT,
                    UNIQUE(select_date, ts_code, track_date)
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_code ON stock_prices(ts_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON stock_prices(trade_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_code ON fundamentals(ts_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_fina_code ON financial_indicators(ts_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_selection_date ON selection_result(select_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tracking_dates ON tracking_result(select_date, track_date)")

            conn.commit()

        logger.info(f"数据库初始化完成：{self.db_path}")

    def save_stock_prices(self, df: pd.DataFrame):
        """保存股票价格数据"""
        if df.empty:
            return

        required_cols = ["ts_code", "trade_date"]
        if not all(col in df.columns for col in required_cols):
            logger.warning("缺少必要列")
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("stock_prices", conn, if_exists="append", index=False)

        logger.debug(f"保存 {len(df)} 条价格数据")

    def save_fundamentals(self, df: pd.DataFrame):
        """保存基本面数据"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("fundamentals", conn, if_exists="append", index=False)

    def save_financial_indicators(self, df: pd.DataFrame):
        """保存财务指标数据"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("financial_indicators", conn, if_exists="append", index=False)

    def save_capital_flow(self, df: pd.DataFrame):
        """保存资金流向数据"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("capital_flow", conn, if_exists="append", index=False)

    def save_north_holdings(self, df: pd.DataFrame):
        """保存北向资金持仓数据"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("north_holdings", conn, if_exists="append", index=False)

    def save_selection_result(self, df: pd.DataFrame):
        """保存选股结果"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("selection_result", conn, if_exists="append", index=False)

    def save_tracking_result(self, df: pd.DataFrame):
        """保存追踪结果"""
        if df.empty:
            return

        with sqlite3.connect(self.db_path) as conn:
            df.to_sql("tracking_result", conn, if_exists="append", index=False)

    def get_stock_prices(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取股票价格数据"""
        query = "SELECT * FROM stock_prices WHERE ts_code = ?"
        params = [ts_code]

        if start_date:
            query += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND trade_date <= ?"
            params.append(end_date)

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)

        return df

    def get_latest_prices(self, trade_date: str) -> pd.DataFrame:
        """获取某日全部股票价格"""
        query = "SELECT * FROM stock_prices WHERE trade_date = ?"

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=[trade_date])

        return df

    def get_selection_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取选股历史"""
        query = "SELECT * FROM selection_result WHERE 1=1"
        params = []

        if start_date:
            query += " AND select_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND select_date <= ?"
            params.append(end_date)

        query += " ORDER BY select_date DESC, total_score DESC"

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)

        return df

    def get_tracking_data(
        self,
        select_date: str,
        ts_code: str,
    ) -> pd.DataFrame:
        """获取单只股票的追踪数据"""
        query = """
            SELECT * FROM tracking_result
            WHERE select_date = ? AND ts_code = ?
            ORDER BY track_date
        """

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=[select_date, ts_code])

        return df

    def clear_old_data(self, table: str, days: int = 365):
        """清理旧数据"""
        cutoff_date = (pd.Timestamp.now() - pd.Timedelta(days=days)).strftime("%Y%m%d")

        query = f"DELETE FROM {table} WHERE trade_date < ? OR select_date < ? OR track_date < ?"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_date, cutoff_date, cutoff_date))
            deleted = cursor.rowcount
            conn.commit()

        if deleted > 0:
            logger.info(f"清理 {table} 表 {deleted} 条旧数据")


# 单例模式
_storage_instance: Optional[Storage] = None


def get_storage() -> Storage:
    """获取存储单例"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance
