"""
交易配置模块

配置券商 API、止损止盈参数等
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 券商配置
TRADING_CONFIG = {
    # 券商类型：ths(同花顺), ht(华泰), yhzq(银河), gtja(国泰君安)
    "broker": os.getenv("TRADING_BROKER", "ths"),

    # 同花顺配置
    "ths_exe_path": os.getenv("THS_EXE_PATH", ""),

    # 账号配置（建议通过环境变量设置）
    "user": os.getenv("TRADING_USER", ""),
    "account": os.getenv("TRADING_ACCOUNT", ""),
    "password": os.getenv("TRADING_PASSWORD", ""),

    # 持仓分析配置
    "stop_loss_ratio": 0.08,      # 止损比例 8%
    "stop_profit_ratio": 0.20,    # 止盈比例 20%
    "ma_stop_loss_days": 20,      # MA 止损周期
    "trail_stop_ratio": 0.10,     # 移动止盈回撤比例 10%

    # 仓位配置
    "max_position_ratio": 0.25,   # 单只股票最大仓位 25%
    "min_position_ratio": 0.05,   # 单只股票最小仓位 5%
}

# 风险预警配置
RISK_CONFIG = {
    # 预警级别
    "warning_levels": {
        "normal": "正常",
        "watch": "观察",
        "warning": "预警",
        "danger": "危险",
    },

    # 止损预警阈值（距离止损价百分比）
    "stop_loss_warning_threshold": 0.05,  # 5%

    # 止盈预警阈值
    "stop_profit_warning_threshold": 0.05,  # 5%

    # 技术破位检测
    "ma_breakdown_days": [20, 60],  # 检测 MA20 和 MA60
}

# 操作建议配置
SUGGESTION_CONFIG = {
    # 建议类型
    "action_types": {
        "buy": "买入",
        "hold": "持有",
        "reduce": "减仓",
        "sell": "卖出",
        "watch": "观察",
    },

    # 建议触发条件
    "conditions": {
        # 减仓条件
        "reduce_profit_threshold": 0.20,  # 盈利 20% 以上考虑减仓
        "reduce_ma_breakdown": True,       # 跌破 MA20 减仓

        # 卖出条件
        "sell_loss_threshold": -0.08,     # 亏损 8% 以上卖出
        "sell_profit_threshold": 0.30,    # 盈利 30% 以上考虑卖出
        "sell_ma60_breakdown": True,       # 跌破 MA60 卖出

        # 加仓条件
        "add_profit_required": True,       # 要求当前盈利
        "add_technical_score_min": 70,    # 技术面得分 70 以上
    },
}


def get_broker_config() -> dict:
    """获取券商配置"""
    return {
        "broker": TRADING_CONFIG["broker"],
        "exe_path": TRADING_CONFIG.get("ths_exe_path", ""),
    }


def get_risk_thresholds() -> dict:
    """获取风险阈值"""
    return {
        "stop_loss": TRADING_CONFIG["stop_loss_ratio"],
        "stop_profit": TRADING_CONFIG["stop_profit_ratio"],
        "trail_stop": TRADING_CONFIG["trail_stop_ratio"],
    }


def validate_config() -> tuple[bool, str]:
    """
    验证配置是否完整

    Returns:
        (是否有效，错误信息)
    """
    broker = TRADING_CONFIG["broker"]

    if broker == "ths":
        if not TRADING_CONFIG.get("ths_exe_path"):
            return False, "同花顺路径未配置，请设置 THS_EXE_PATH 环境变量"
        if not Path(TRADING_CONFIG["ths_exe_path"]).exists():
            return False, f"同花顺路径不存在：{TRADING_CONFIG['ths_exe_path']}"

    # 账号密码为可选（可以使用手动登录模式）
    return True, "配置验证通过"
