"""
龙头战法策略模块

灵感来源：daily_stock_analysis 等热门项目

核心功能:
- 龙头股识别：板块内涨幅第一、连板数最高、涨停时间最早
- 龙二龙三挖掘：龙头高位时低位补涨股
- 龙头切换预警：老龙头走弱、新龙头崛起
- 涨停板分析：封单强度、涨停原因、连板预期
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from data.fetcher import get_data_fetcher
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DragonStock:
    """龙头股信息"""
    ts_code: str
    stock_name: str
    board_name: str  # 所属板块
    rank: int  # 龙头排名 (1=龙头，2=龙二，3=龙三)
    price: float
    change_pct: float  # 涨跌幅
    limit_up_count: int  # 连板数
    limit_up_time: Optional[str]  # 涨停时间
    market_value: float  # 流通市值
    volume_ratio: float  # 量比
    turn_over_rate: float  # 换手率
    confidence: str  # 龙头置信度：高/中/低


@dataclass
class LimitUpInfo:
    """涨停板信息"""
    ts_code: str
    stock_name: str
    board_name: str  # 所属板块
    price: float
    limit_up_count: int  # 连板数
    limit_up_reason: str  # 涨停原因
    封单_amount: float  # 封单金额
    封单_ratio: float  # 封单占流通市值比例
    first_limit_time: str  # 首次涨停时间
    last_open_time: Optional[str]  # 最后炸板时间 (如果有)
    strength: str  # 强度：强/中/弱


class DragonStrategy:
    """龙头战法策略"""

    def __init__(self):
        self.fetcher = get_data_fetcher()

    def get_industry_board_list(self) -> List[str]:
        """获取行业板块列表"""
        df = self.fetcher.get_industry_list()
        if df.empty:
            return []
        # 返回板块名称列表
        return df.iloc[:, 0].tolist() if len(df.columns) > 0 else []

    def get_board_stocks(self, board_name: str) -> List[str]:
        """获取板块成分股"""
        df = self.fetcher.get_industry_stocks(board_name)
        if df.empty:
            return []
        return df.iloc[:, 0].tolist() if len(df.columns) > 0 else []

    def get_board_performance(self, board_name: str) -> Dict:
        """
        获取板块涨跌幅表现

        Returns:
            dict: 板块表现数据
        """
        try:
            # 获取板块历史行情
            df = self.fetcher.get_industry_history(board_name, period="日")
            if df.empty:
                return {}

            # 计算涨跌幅
            df = df.sort_values("交易日", ascending=False)
            if len(df) < 2:
                return {}

            latest = df.iloc[0]
            prev = df.iloc[1]

            change_pct = (latest["收盘价"] - prev["收盘价"]) / prev["收盘价"] * 100

            # 5 日涨跌幅
            if len(df) >= 6:
                change_5d = (latest["收盘价"] - df.iloc[5]["收盘价"]) / df.iloc[5]["收盘价"] * 100
            else:
                change_5d = change_pct

            return {
                "board_name": board_name,
                "change_1d": change_pct,
                "change_5d": change_5d,
                "volume": latest.get("成交量", 0),
                "amount": latest.get("成交额", 0),
            }

        except Exception as e:
            logger.error(f"获取板块表现失败：{e}")
            return {}

    def identify_dragon_stocks(
        self,
        board_name: str,
        top_n: int = 3,
    ) -> List[DragonStock]:
        """
        识别板块龙头股

        Args:
            board_name: 板块名称
            top_n: 返回前 N 只龙头股

        Returns:
            List[DragonStock]: 龙头股列表
        """
        # 获取板块成分股
        stock_codes = self.get_board_stocks(board_name)
        if not stock_codes:
            return []

        # 获取成分股表现
        dragon_candidates = []

        for code in stock_codes[:50]:  # 限制处理数量
            info = self._get_stock_info(code)
            if not info:
                continue

            # 计算龙头特征
            limit_up_count = self._count_limit_up_days(code)
            limit_up_time = self._get_first_limit_time(code)

            dragon_candidates.append({
                "ts_code": code,
                "stock_name": info.get("name", ""),
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0),
                "limit_up_count": limit_up_count,
                "limit_up_time": limit_up_time,
                "market_value": info.get("market_value", 0),
                "volume_ratio": info.get("volume_ratio", 1),
                "turn_over_rate": info.get("turn_over_rate", 0),
            })

        # 龙头评分：连板数 (40%) + 涨幅 (30%) + 涨停时间 (20%) + 量比 (10%)
        for candidate in dragon_candidates:
            score = 0

            # 连板数评分
            score += min(candidate["limit_up_count"] * 20, 40)

            # 涨幅评分
            if candidate["change_pct"] >= 9.5:  # 涨停
                score += 30
            elif candidate["change_pct"] >= 5:
                score += 20
            elif candidate["change_pct"] >= 0:
                score += 10

            # 涨停时间评分（越早越好）
            if candidate["limit_up_time"]:
                hour = int(candidate["limit_up_time"][:2])
                if hour < 10:  # 10 点前涨停
                    score += 20
                elif hour < 11:
                    score += 15
                else:
                    score += 10

            # 量比评分
            if candidate["volume_ratio"] > 3:
                score += 10
            elif candidate["volume_ratio"] > 1:
                score += 5

            candidate["dragon_score"] = score

        # 排序
        dragon_candidates.sort(key=lambda x: x["dragon_score"], reverse=True)

        # 生成结果
        result = []
        for i, c in enumerate(dragon_candidates[:top_n]):
            # 确定置信度
            if c["dragon_score"] >= 80:
                confidence = "高"
            elif c["dragon_score"] >= 60:
                confidence = "中"
            else:
                confidence = "低"

            result.append(DragonStock(
                ts_code=c["ts_code"],
                stock_name=c["stock_name"],
                board_name=board_name,
                rank=i + 1,
                price=c["price"],
                change_pct=c["change_pct"],
                limit_up_count=c["limit_up_count"],
                limit_up_time=c["limit_up_time"],
                market_value=c["market_value"],
                volume_ratio=c["volume_ratio"],
                turn_over_rate=c["turn_over_rate"],
                confidence=confidence,
            ))

        return result

    def analyze_limit_up(self, ts_code: str) -> Optional[LimitUpInfo]:
        """
        分析涨停板

        Args:
            ts_code: 股票代码

        Returns:
            LimitUpInfo: 涨停板信息
        """
        try:
            # 获取股票信息
            info = self._get_stock_info(ts_code)
            if not info:
                return None

            # 检查是否涨停
            change_pct = info.get("change_pct", 0)
            if change_pct < 9.5:
                logger.warning(f"{ts_code} 当前涨幅 {change_pct:.2f}%, 未达到涨停")
                return None

            # 计算连板数
            limit_up_count = self._count_limit_up_days(ts_code)

            # 获取封单数据（简化版本）
            封单_amount = self._get_limit_up_volume(ts_code)
            market_value = info.get("market_value", 10000000000)
            封单_ratio = 封单_amount / market_value * 100 if market_value > 0 else 0

            # 判断强度
            if 封单_ratio > 1:
                strength = "强"
            elif 封单_ratio > 0.5:
                strength = "中"
            else:
                strength = "弱"

            # 涨停原因（简化：根据板块热点）
            limit_up_reason = self._guess_limit_up_reason(ts_code)

            return LimitUpInfo(
                ts_code=ts_code,
                stock_name=info.get("name", ""),
                board_name=info.get("industry", ""),
                price=info.get("price", 0),
                limit_up_count=limit_up_count,
                limit_up_reason=limit_up_reason,
                封单_amount=封单_amount,
                封单_ratio=封单_ratio,
                first_limit_time=self._get_first_limit_time(ts_code),
                last_open_time=None,
                strength=strength,
            )

        except Exception as e:
            logger.error(f"分析涨停失败：{e}")
            return None

    def find_dragon_switch(self, board_name: str) -> Dict:
        """
        寻找龙头切换机会

        Args:
            board_name: 板块名称

        Returns:
            dict: 龙头切换分析
        """
        dragons = self.identify_dragon_stocks(board_name, top_n=5)
        if not dragons:
            return {}

        result = {
            "current_dragon": None,
            "potential_dragon": None,
            "switch_signal": False,
            "analysis": "",
        }

        # 当前龙头
        current = dragons[0]
        result["current_dragon"] = current

        # 检查老龙头是否走弱
        if current.change_pct < 0 and current.limit_up_count >= 3:
            # 龙头高位回调，可能有切换
            result["switch_signal"] = True

            # 寻找潜在新龙头
            for d in dragons[1:]:
                if d.change_pct >= 5 and d.limit_up_count >= 1:
                    result["potential_dragon"] = d
                    result["analysis"] = f"老龙头{current.stock_name}高位回调，{d.stock_name}可能接力"
                    break

        if not result["switch_signal"]:
            result["analysis"] = f"当前龙头{current.stock_name}地位稳固，连板{current.limit_up_count}个"

        return result

    # ==================== 辅助方法 ====================

    def _get_stock_info(self, ts_code: str) -> Optional[Dict]:
        """获取股票实时信息"""
        try:
            # 获取实时行情
            df = self.fetcher.get_stock_prices(ts_code, count=1)
            if df.empty:
                return None

            latest = df.iloc[0]
            return {
                "ts_code": ts_code,
                "name": ts_code,  # 简化
                "price": latest.get("close", 0),
                "change_pct": latest.get("pct_chg", 0),
                "volume": latest.get("vol", 0),
                "amount": latest.get("amount", 0),
                "market_value": latest.get("circ_mv", 0) * 1000000,  # 转为元
                "volume_ratio": 1,  # 简化
                "turn_over_rate": 0,
                "industry": "",
            }

        except Exception as e:
            logger.error(f"获取股票信息失败：{e}")
            return None

    def _count_limit_up_days(self, ts_code: str, days: int = 30) -> int:
        """统计连板天数"""
        try:
            df = self.fetcher.get_stock_prices(ts_code, count=days)
            if df.empty:
                return 0

            # 连续涨停计数
            count = 0
            for _, row in df.iterrows():
                pct_chg = row.get("pct_chg", 0)
                if pct_chg >= 9.5:
                    count += 1
                else:
                    break

            return count

        except Exception:
            return 0

    def _get_first_limit_time(self, ts_code: str) -> Optional[str]:
        """获取首次涨停时间（简化版本）"""
        # 实际需要从更细粒度的数据获取
        # 这里返回 None
        return None

    def _get_limit_up_volume(self, ts_code: str) -> float:
        """获取封单金额（简化版本）"""
        # 实际需要从盘口数据获取
        # 这里返回 0
        return 0.0

    def _guess_limit_up_reason(self, ts_code: str) -> str:
        """猜测涨停原因"""
        # 简化版本
        return "题材驱动"


def create_dragon_strategy() -> DragonStrategy:
    """创建龙头战法策略实例"""
    return DragonStrategy()
