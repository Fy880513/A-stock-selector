"""
easytrader API 封装模块

通过 easytrader 库接入同花顺，获取持仓数据
注意：需要 Windows 系统和同花顺客户端

GitHub: https://github.com/shidenggui/easytrader
"""
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from config.trading_config import TRADING_CONFIG, get_broker_config
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PositionInfo:
    """持仓信息"""
    ts_code: str
    stock_name: str
    volume: int  # 持股数量
    cost_price: float  # 成本价
    current_price: float  # 当前价
    market_value: float  # 市值
    profit: float  # 盈亏金额
    profit_ratio: float  # 盈亏比例


@dataclass
class AccountInfo:
    """账户信息"""
    total_assets: float  # 总资产
    available_cash: float  # 可用资金
    frozen_cash: float  # 冻结资金
    market_value: float  # 持仓市值
    total_profit: float  # 总盈亏
    total_profit_ratio: float  # 总盈亏比例


class EasyTraderAPI:
    """easytrader API 封装类"""

    def __init__(self):
        self._trader = None
        self._logged_in = False
        self.broker_config = get_broker_config()

    def _init_trader(self):
        """初始化 trader"""
        try:
            import easytrader
        except ImportError:
            logger.error("easytrader 未安装，请运行：pip install easytrader pywinauto")
            raise ImportError("easytrader 未安装")

        broker = self.broker_config.get("broker", "ths")

        if broker == "ths":
            # 同花顺
            self._trader = easytrader.use("ths")
        elif broker == "ht":
            # 华泰证券
            self._trader = easytrader.use("ht")
        elif broker == "yhzq":
            # 银河证券
            self._trader = easytrader.use("yhzq")
        elif broker == "gtja":
            # 国泰君安
            self._trader = easytrader.use("gtja")
        else:
            logger.warning(f"未知券商类型：{broker}，使用同花顺")
            self._trader = easytrader.use("ths")

    def login(
        self,
        user: Optional[str] = None,
        account: Optional[str] = None,
        password: Optional[str] = None,
        exe_path: Optional[str] = None,
    ) -> bool:
        """
        登录交易账户

        Args:
            user: 用户名
            account: 资金账号
            password: 通讯密码
            exe_path: 同花顺客户端路径

        Returns:
            bool: 是否登录成功
        """
        if self._logged_in:
            logger.info("已登录，跳过登录")
            return True

        try:
            self._init_trader()
        except ImportError as e:
            logger.error(f"初始化失败：{e}")
            return False

        # 获取配置
        user = user or TRADING_CONFIG.get("user", "")
        account = account or TRADING_CONFIG.get("account", "")
        password = password or TRADING_CONFIG.get("password", "")
        exe_path = exe_path or TRADING_CONFIG.get("ths_exe_path", "")

        # 准备登录参数
        prepare_params = {
            "user": user,
            "account": account,
            "password": password,
        }

        # 检查是否需要手动登录
        if not exe_path:
            logger.warning("未配置客户端路径，需要手动登录同花顺")
            try:
                # 尝试连接已运行的同花顺
                self._trader.connect()
                self._logged_in = True
                logger.info("成功连接到同花顺")
                return True
            except Exception as e:
                logger.error(f"连接失败：{e}")
                logger.info("请使用手动模式：先登录同花顺，再运行程序")
                return False

        # 自动登录模式
        try:
            # 设置客户端路径
            self._trader.prepare(exe_path)

            # 等待初始化
            import time
            time.sleep(3)

            # 填入账号信息
            self._trader.connect()

            # 测试连接
            balance = self._trader.balance
            if balance:
                self._logged_in = True
                logger.info("登录成功")
                return True
            else:
                logger.error("登录后获取账户信息失败")
                return False

        except Exception as e:
            logger.error(f"登录失败：{e}")
            logger.info("建议：1.检查同花顺路径 2.使用手动模式（先登录同花顺）")
            return False

    @property
    def is_logged_in(self) -> bool:
        """检查是否已登录"""
        return self._logged_in and self._trader is not None

    def get_balance(self) -> Optional[Dict]:
        """
        获取账户资金

        Returns:
            dict: 账户资金信息
        """
        if not self.is_logged_in:
            logger.error("未登录")
            return None

        try:
            balance = self._trader.balance
            if balance and len(balance) > 0:
                return balance[0] if isinstance(balance, list) else balance
            return None
        except Exception as e:
            logger.error(f"获取资金失败：{e}")
            return None

    def get_position(self) -> List[Dict]:
        """
        获取持仓列表

        Returns:
            List[Dict]: 持仓列表
        """
        if not self.is_logged_in:
            logger.error("未登录")
            return []

        try:
            position = self._trader.position
            if position:
                return position if isinstance(position, list) else [position]
            return []
        except Exception as e:
            logger.error(f"获取持仓失败：{e}")
            return []

    def get_entry_list(self) -> List[Dict]:
        """
        获取当日委托

        Returns:
            List[Dict]: 委托列表
        """
        if not self.is_logged_in:
            logger.error("未登录")
            return []

        try:
            return self._trader.entrust
        except Exception as e:
            logger.error(f"获取委托失败：{e}")
            return []

    def get_today_trades(self) -> List[Dict]:
        """
        获取当日成交

        Returns:
            List[Dict]: 成交列表
        """
        if not self.is_logged_in:
            logger.error("未登录")
            return []

        try:
            return self._trader.today_trades
        except Exception as e:
            logger.error(f"获取成交失败：{e}")
            return []

    def get_account_info(self) -> Optional[AccountInfo]:
        """
        获取账户完整信息

        Returns:
            AccountInfo: 账户信息
        """
        balance = self.get_balance()
        if not balance:
            return None

        try:
            # 标准化字段（不同券商可能字段名不同）
            total_assets = float(balance.get("总资产", balance.get("total_assets", 0)))
            available_cash = float(balance.get("可用金额", balance.get("available_cash", 0)))
            frozen_cash = float(balance.get("冻结金额", balance.get("frozen_cash", 0)))
            market_value = total_assets - available_cash - frozen_cash

            # 计算总盈亏（需要成本信息）
            position = self.get_position()
            total_cost = 0.0
            total_market = 0.0

            for pos in position:
                cost_price = float(pos.get("成本价", pos.get("cost_price", 0)))
                volume = int(pos.get("股份余额", pos.get("volume", 0)))
                current_price = float(pos.get("市价", pos.get("current_price", 0)))

                total_cost += cost_price * volume
                total_market += current_price * volume

            total_profit = total_market - total_cost if total_cost > 0 else 0
            total_profit_ratio = total_profit / total_cost if total_cost > 0 else 0

            return AccountInfo(
                total_assets=total_assets,
                available_cash=available_cash,
                frozen_cash=frozen_cash,
                market_value=market_value,
                total_profit=total_profit,
                total_profit_ratio=total_profit_ratio,
            )

        except Exception as e:
            logger.error(f"解析账户信息失败：{e}")
            return None

    def get_positions(self) -> List[PositionInfo]:
        """
        获取标准化持仓列表

        Returns:
            List[PositionInfo]: 持仓信息列表
        """
        position_list = self.get_position()
        if not position_list:
            return []

        result = []
        for pos in position_list:
            try:
                # 标准化字段
                ts_code = pos.get("证券代码", pos.get("ts_code", pos.get("stock_code", "")))
                stock_name = pos.get("证券名称", pos.get("stock_name", pos.get("name", "")))
                volume = int(pos.get("股份余额", pos.get("volume", pos.get("shares", 0))))
                cost_price = float(pos.get("成本价", pos.get("cost_price", 0)))
                current_price = float(pos.get("市价", pos.get("current_price", 0)))
                market_value = float(pos.get("市值", pos.get("market_value", 0)))

                # 如果没有当前价，用市值/数量计算
                if current_price <= 0 and volume > 0:
                    current_price = market_value / volume

                # 计算盈亏
                profit = (current_price - cost_price) * volume
                profit_ratio = (current_price - cost_price) / cost_price if cost_price > 0 else 0

                result.append(PositionInfo(
                    ts_code=ts_code,
                    stock_name=stock_name,
                    volume=volume,
                    cost_price=cost_price,
                    current_price=current_price,
                    market_value=market_value,
                    profit=profit,
                    profit_ratio=profit_ratio,
                ))

            except Exception as e:
                logger.warning(f"解析持仓失败：{pos}, 错误：{e}")

        return result

    def buy(
        self,
        ts_code: str,
        price: float,
        volume: int,
    ) -> Dict[str, Any]:
        """
        买入股票

        Args:
            ts_code: 股票代码
            price: 买入价格
            volume: 买入数量

        Returns:
            dict: 委托结果
        """
        if not self.is_logged_in:
            return {"success": False, "message": "未登录"}

        try:
            result = self._trader.buy(ts_code, price, volume)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def sell(
        self,
        ts_code: str,
        price: float,
        volume: int,
    ) -> Dict[str, Any]:
        """
        卖出股票

        Args:
            ts_code: 股票代码
            price: 卖出价格
            volume: 卖出数量

        Returns:
            dict: 委托结果
        """
        if not self.is_logged_in:
            return {"success": False, "message": "未登录"}

        try:
            result = self._trader.sell(ts_code, price, volume)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def cancel_entrust(self, entrust_no: str) -> Dict[str, Any]:
        """
        撤单

        Args:
            entrust_no: 委托编号

        Returns:
            dict: 撤单结果
        """
        if not self.is_logged_in:
            return {"success": False, "message": "未登录"}

        try:
            result = self._trader.cancel_entrust(entrust_no)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "message": str(e)}


# 单例模式
_api_instance: Optional[EasyTraderAPI] = None


def get_trading_api() -> EasyTraderAPI:
    """获取交易 API 单例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = EasyTraderAPI()
    return _api_instance


def create_trading_api() -> EasyTraderAPI:
    """创建新的交易 API 实例"""
    return EasyTraderAPI()
