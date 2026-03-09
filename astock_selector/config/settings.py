"""
系统配置模块
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据目录
DATA_DIR = BASE_DIR / "data_files"
DATA_DIR.mkdir(exist_ok=True)

# 输出目录
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 数据库配置
DATABASE_URL = f"sqlite:///{DATA_DIR}/astock.db"

# Tushare 配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_API_URL = "http://api.tushare.pro"

# 选股配置
STOCK_SELECTION_CONFIG = {
    # 各维度权重
    "weights": {
        "fundamental": 0.25,
        "technical": 0.35,
        "capital_flow": 0.25,
        "hotspot": 0.15,
    },
    # 选股数量
    "top_n": 10,
    # 资金规模（用于仓位建议）
    "total_capital": 200000,
    # 单只股票最小仓位
    "min_position_per_stock": 20000,
    # 单只股票最大仓位
    "max_position_per_stock": 40000,
}

# 基本面筛选阈值
FUNDAMENTAL_THRESHOLDS = {
    "pe_ttm_min": 0,
    "pe_ttm_max": 60,
    "peg_min": 0.5,
    "peg_max": 2,
    "revenue_growth_min": 0.15,
    "net_profit_growth_min": 0.20,
    "roe_min": 0.10,
    "gross_margin_min": 0.20,
    "debt_to_asset_max": 0.60,
    "current_ratio_min": 1.2,
}

# 技术指标配置
TECHNICAL_CONFIG = {
    "ma_periods": [5, 10, 20, 60],
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "kdj_period": 9,
    "rsi_periods": [6, 12, 24],
    "boll_period": 20,
    "boll_std": 2,
    "atr_period": 14,
    "adx_period": 14,
}

# 交易日配置
TRADING_DAYS_CACHE_DAYS = 365  # 缓存交易日天数

# 日志配置
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
