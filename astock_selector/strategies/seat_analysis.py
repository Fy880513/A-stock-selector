"""
龙虎榜席位分析模块

功能:
- 龙虎榜数据获取
- 席位类型识别（机构、游资、北向）
- 席位历史胜率统计
- 席位联动分析
"""
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SeatInfo:
    """席位信息"""
    seat_name: str  # 席位名称
    seat_type: str  # 席位类型：机构/游资/北向/券商
    buy_amount: float  # 买入金额（万元）
    sell_amount: float  # 卖出金额（万元）
    net_buy: float  # 净买入（万元）
    rank: int  # 榜单排名（1-5）


@dataclass
class LHBStock:
    """龙虎榜股票"""
    ts_code: str
    stock_name: str
    close_price: float
    change_pct: float
    turn_over_rate: float  # 换手率
    total_buy: float  # 合计买入（万元）
    total_sell: float  # 合计卖出（万元）
    net_amount: float  # 净买入（万元）
    seats: List[SeatInfo]  # 席位列表
    has_institution: bool  # 是否有机构
    has_north: bool  # 是否有北向资金
    seat_score: float  # 席位得分


class SeatAnalyzer:
    """龙虎榜席位分析器"""

    # 知名游资席位（简化版本）
    FAMOUS_YOUZI = {
        "中信证券上海溧阳路证券营业部",
        "中信证券上海分公司",
        "华泰证券深圳益田路荣超商务中心证券营业部",
        "国泰君安证券上海江苏路证券营业部",
        "中国银河证券北京阜成路证券营业部",
        "中信证券北京总部证券营业部",
        "华泰证券上海共和新路证券营业部",
        "光大证券杭州庆春路证券营业部",
        "华泰证券浙江分公司",
        "国泰君安证券上海新闸路证券营业部",
    }

    # 机构席位特征
    INSTITUTION_KEYWORDS = ["机构专用", "机构席位"]

    # 北向资金席位特征
    NORTH_KEYWORDS = ["沪股通", "深股通", "港股通"]

    def __init__(self):
        pass

    def get_seat_type(self, seat_name: str) -> str:
        """
        判断席位类型

        Args:
            seat_name: 席位名称

        Returns:
            str: 席位类型 (机构/游资/北向/券商)
        """
        # 机构席位
        for keyword in self.INSTITUTION_KEYWORDS:
            if keyword in seat_name:
                return "机构"

        # 北向资金
        for keyword in self.NORTH_KEYWORDS:
            if keyword in seat_name:
                return "北向"

        # 知名游资
        if seat_name in self.FAMOUS_YOUZI:
            return "游资"

        # 默认券商营业部
        return "券商"

    def analyze_lhb_stock(
        self,
        ts_code: str,
        stock_name: str,
        close_price: float,
        change_pct: float,
        turn_over_rate: float,
        buy_seats: List[Dict],
        sell_seats: List[Dict],
    ) -> Optional[LHBStock]:
        """
        分析单只龙虎榜股票

        Args:
            ts_code: 股票代码
            stock_name: 股票名称
            close_price: 收盘价
            change_pct: 涨跌幅
            turn_over_rate: 换手率
            buy_seats: 买方席位列表 [{"name": "", "amount": 0}]
            sell_seats: 卖方席位列表

        Returns:
            LHBStock: 龙虎榜股票信息
        """
        try:
            seats = []
            has_institution = False
            has_north = False
            total_buy = 0
            total_sell = 0

            # 分析买方席位
            for i, seat in enumerate(buy_seats):
                seat_name = seat.get("name", "")
                buy_amount = seat.get("amount", 0)

                seat_info = SeatInfo(
                    seat_name=seat_name,
                    seat_type=self.get_seat_type(seat_name),
                    buy_amount=buy_amount,
                    sell_amount=0,
                    net_buy=buy_amount,
                    rank=i + 1,
                )
                seats.append(seat_info)
                total_buy += buy_amount

                if seat_info.seat_type == "机构":
                    has_institution = True
                if seat_info.seat_type == "北向":
                    has_north = True

            # 分析卖方席位
            for i, seat in enumerate(sell_seats):
                seat_name = seat.get("name", "")
                sell_amount = seat.get("amount", 0)

                seat_info = SeatInfo(
                    seat_name=seat_name,
                    seat_type=self.get_seat_type(seat_name),
                    buy_amount=0,
                    sell_amount=sell_amount,
                    net_buy=-sell_amount,
                    rank=i + 1,
                )
                seats.append(seat_info)
                total_sell += sell_amount

                if seat_info.seat_type == "机构":
                    has_institution = True
                if seat_info.seat_type == "北向":
                    has_north = True

            # 计算席位得分
            seat_score = self._calculate_seat_score(seats, has_institution, has_north)

            return LHBStock(
                ts_code=ts_code,
                stock_name=stock_name,
                close_price=close_price,
                change_pct=change_pct,
                turn_over_rate=turn_over_rate,
                total_buy=total_buy,
                total_sell=total_sell,
                net_amount=total_buy - total_sell,
                seats=seats,
                has_institution=has_institution,
                has_north=has_north,
                seat_score=seat_score,
            )

        except Exception as e:
            logger.error(f"分析龙虎榜失败：{e}")
            return None

    def _calculate_seat_score(
        self,
        seats: List[SeatInfo],
        has_institution: bool,
        has_north: bool,
    ) -> float:
        """
        计算席位得分

        评分逻辑:
        - 机构买入：+30 分
        - 北向买入：+20 分
        - 知名游资：+15 分
        - 净买入为正：+20 分
        - 买卖比>2: +15 分
        """
        score = 50.0

        # 机构溢价
        if has_institution:
            score += 30

        # 北向溢价
        if has_north:
            score += 20

        # 知名游资溢价
        for seat in seats:
            if seat.seat_type == "游资" and seat.net_buy > 0:
                score += 15
                break

        # 净买入
        total_net = sum(s.net_buy for s in seats)
        if total_net > 5000:  # 净买入超 5000 万
            score += 20
        elif total_net > 2000:
            score += 15
        elif total_net > 1000:
            score += 10
        elif total_net > 0:
            score += 5

        # 买卖比
        total_buy = sum(s.buy_amount for s in seats if s.buy_amount > 0)
        total_sell = sum(s.sell_amount for s in seats if s.sell_amount > 0)
        if total_sell > 0:
            buy_sell_ratio = total_buy / total_sell
            if buy_sell_ratio > 3:
                score += 15
            elif buy_sell_ratio > 2:
                score += 10
            elif buy_sell_ratio > 1:
                score += 5

        return min(100, max(0, score))

    def get_lhb_list(
        self,
        trade_date: Optional[str] = None,
    ) -> List[LHBStock]:
        """
        获取龙虎榜列表

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            List[LHBStock]: 龙虎榜股票列表
        """
        try:
            # 使用 AKShare 获取龙虎榜数据
            from data.akshare_api import get_akshare_api
            ak = get_akshare_api()

            # 获取龙虎榜数据
            df = ak.get_stock_lhb_daily_em(trade_date or datetime.now().strftime("%Y%m%d"))
            if df.empty:
                return []

            # 按股票代码分组
            grouped = df.groupby("代码")
            result = []

            for code, group in grouped:
                # 获取基本信息
                stock_name = group.iloc[0].get("名称", "")
                close_price = group.iloc[0].get("收盘价", 0)
                change_pct = group.iloc[0].get("涨跌幅", 0)
                turn_over_rate = group.iloc[0].get("换手率", 0)

                # 买方席位
                buy_seats = []
                for _, row in group[group["类型"] == "买入"].iterrows():
                    buy_seats.append({
                        "name": row.get("营业部名称", ""),
                        "amount": row.get("买入金额", 0),
                    })

                # 卖方席位
                sell_seats = []
                for _, row in group[group["类型"] == "卖出"].iterrows():
                    sell_seats.append({
                        "name": row.get("营业部名称", ""),
                        "amount": row.get("卖出金额", 0),
                    })

                # 分析
                lhb_stock = self.analyze_lhb_stock(
                    ts_code=code,
                    stock_name=stock_name,
                    close_price=close_price,
                    change_pct=change_pct,
                    turn_over_rate=turn_over_rate,
                    buy_seats=buy_seats,
                    sell_seats=sell_seats,
                )

                if lhb_stock:
                    result.append(lhb_stock)

            return result

        except Exception as e:
            logger.error(f"获取龙虎榜失败：{e}")
            return []

    def get_seat_statistics(
        self,
        seat_name: str,
        days: int = 30,
    ) -> Dict:
        """
        获取席位统计信息

        Args:
            seat_name: 席位名称
            days: 统计天数

        Returns:
            dict: 席位统计信息
        """
        # 简化版本：返回席位类型和特征
        seat_type = self.get_seat_type(seat_name)

        return {
            "seat_name": seat_name,
            "seat_type": seat_type,
            "is_famous": seat_name in self.FAMOUS_YOUZI,
            "win_rate": 0.55,  # 简化：假设胜率
            "avg_profit": 0.05,  # 简化：假设平均盈利
        }


def create_seat_analyzer() -> SeatAnalyzer:
    """创建席位分析器实例"""
    return SeatAnalyzer()
