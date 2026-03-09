"""
通用工具函数
"""
import pandas as pd
from datetime import datetime, timedelta


def is_valid_stock_code(code: str) -> bool:
    """验证股票代码格式"""
    if not code:
        return False
    # A 股代码：600/601/603/605/000/001/002/003/300/301 开头
    valid_prefixes = ['600', '601', '603', '605', '000', '001', '002', '003', '300', '301']
    return any(code.startswith(prefix) for prefix in valid_prefixes)


def is_st_stock(code: str, name: str = "") -> bool:
    """判断是否为 ST 股票"""
    st_markers = ['ST', '*ST', '退']
    return any(marker in name for marker in st_markers)


def is_new_stock(list_date: str, years: int = 1) -> bool:
    """判断是否为新股"""
    if not list_date:
        return False
    list_dt = datetime.strptime(list_date, "%Y%m%d")
    return datetime.now() - list_dt < timedelta(days=365 * years)


def format_currency(value: float) -> str:
    """格式化货币显示"""
    if value >= 100000000:
        return f"{value / 100000000:.2f}亿"
    elif value >= 10000:
        return f"{value / 10000:.2f}万"
    else:
        return f"{value:.2f}"


def calculate_position_size(
    total_capital: float,
    stock_price: float,
    min_position: float,
    max_position: float,
) -> tuple[int, float]:
    """
    计算建议仓位

    Returns:
        (股数，金额)
    """
    # 默认每只股票分配资金
    target_position = (min_position + max_position) / 2

    # 计算股数（100 股的整数倍）
    shares = int(target_position / stock_price / 100) * 100

    # 确保在最小和最大仓位之间
    if shares * stock_price < min_position:
        shares = int(min_position / stock_price / 100) * 100
    elif shares * stock_price > max_position:
        shares = int(max_position / stock_price / 100) * 100

    return max(shares, 100), shares * stock_price


def get_previous_trading_day(date: str, days: int = 1) -> str:
    """获取前 N 个交易日（简单实现，不考虑节假日）"""
    dt = datetime.strptime(date, "%Y-%m-%d")
    result = dt - timedelta(days=days)
    # 跳过周末
    while result.weekday() >= 5:
        result -= timedelta(days=1)
    return result.strftime("%Y-%m-%d")


def normalize_score(
    value: float,
    min_val: float,
    max_val: float,
    reverse: bool = False,
) -> float:
    """
    将值标准化到 0-100 分

    Args:
        value: 原始值
        min_val: 最小值
        max_val: 最大值
        reverse: 是否反向（越小分越高）

    Returns:
        标准化分数 (0-100)
    """
    if max_val == min_val:
        return 50.0

    if reverse:
        score = 100 * (max_val - value) / (max_val - min_val)
    else:
        score = 100 * (value - min_val) / (max_val - min_val)

    return max(0, min(100, score))
