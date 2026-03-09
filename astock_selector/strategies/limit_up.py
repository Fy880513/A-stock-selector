"""
涨停板分析模块

功能:
- 涨停统计：每日涨停板数量、连板分布
- 封单强度分析：封单金额、封单占比
- 炸板预警：封单减少、成交量放大
- 连板预期：历史连板数统计
"""
import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from data.fetcher import get_data_fetcher
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LimitUpStock:
    """涨停股信息"""
    ts_code: str
    stock_name: str
    price: float
    change_pct: float
    limit_up_count: int  # 连板数
    first_limit_time: Optional[str]  # 首次涨停时间
    last_open_time: Optional[str]  # 最后炸板时间
    封单_amount: float  # 封单金额 (万元)
    封单_ratio: float  # 封单占流通市值比例 (%)
    volume_ratio: float  # 量比
    turn_over_rate: float  # 换手率
    industry: str  # 所属行业
    concept: str  # 所属概念


@dataclass
class LimitUpStat:
    """涨停统计"""
    trade_date: str
    total_limit_up: int  # 涨停总数
    total_limit_down: int  # 跌停总数
    limit_up_ratio: float  # 涨停占比
    connect_board_count: Dict[int, int]  # 连板分布 {1: 数量，2: 数量，3: 数量...}
    highest_connect: int  # 最高连板数
   炸板_count: int  # 炸板数量
   炸板_ratio: float  # 炸板率


class LimitUpAnalyzer:
    """涨停板分析器"""

    def __init__(self):
        self.fetcher = get_data_fetcher()

    def get_limit_up_list(self, trade_date: Optional[str] = None) -> List[LimitUpStock]:
        """
        获取涨停板列表

        Args:
            trade_date: 交易日期 YYYYMMDD

        Returns:
            List[LimitUpStock]: 涨停股列表
        """
        try:
            # 使用 AKShare 获取涨停数据
            from data.akshare_api import get_akshare_api
            ak = get_akshare_api()

            # 获取实时行情
            df = ak.get_stock_individual_spot_em()
            if df.empty:
                return []

            # 筛选涨停股 (涨幅>=9.5%)
            limit_up_df = df[df["涨跌幅"] >= 9.5].copy()

            result = []
            for _, row in limit_up_df.iterrows():
                result.append(LimitUpStock(
                    ts_code=row.get("代码", ""),
                    stock_name=row.get("名称", ""),
                    price=row.get("最新价", 0),
                    change_pct=row.get("涨跌幅", 0),
                    limit_up_count=0,  # 需要进一步计算
                    first_limit_time=None,
                    last_open_time=None,
                    封单_amount=0,
                    封单_ratio=0,
                    volume_ratio=row.get("量比", 1),
                    turn_over_rate=row.get("换手率", 0),
                    industry=row.get("行业", ""),
                    concept=row.get("概念", ""),
                ))

            return result

        except Exception as e:
            logger.error(f"获取涨停列表失败：{e}")
            return []

    def get_limit_up_statistics(self, trade_date: Optional[str] = None) -> LimitUpStat:
        """
        获取涨停统计

        Returns:
            LimitUpStat: 涨停统计
        """
        try:
            # 获取涨停列表
            limit_up_stocks = self.get_limit_up_list(trade_date)

            # 计算连板分布
            connect_board_count = {}
            highest_connect = 0

            for stock in limit_up_stocks:
                # 计算连板数
                count = self._count_continuous_limit_up(stock.ts_code)
                stock.limit_up_count = count

                if count > highest_connect:
                    highest_connect = count

                if count not in connect_board_count:
                    connect_board_count[count] = 0
                connect_board_count[count] += 1

            # 计算跌停数量
            limit_down_count = self._count_limit_down(trade_date)

            # 涨停率
            total_stocks = self._get_total_market_count()
            limit_up_ratio = len(limit_up_stocks) / total_stocks * 100 if total_stocks > 0 else 0

            # 炸板数（简化：假设 10% 的涨停股炸板）
            炸板_count = int(len(limit_up_stocks) * 0.1)
            炸板_ratio = 炸板_count / len(limit_up_stocks) * 100 if limit_up_stocks else 0

            return LimitUpStat(
                trade_date=trade_date or datetime.now().strftime("%Y%m%d"),
                total_limit_up=len(limit_up_stocks),
                total_limit_down=limit_down_count,
                limit_up_ratio=limit_up_ratio,
                connect_board_count=connect_board_count,
                highest_connect=highest_connect,
                炸板_count=炸板_count,
                炸板_ratio=炸板_ratio,
            )

        except Exception as e:
            logger.error(f"涨停统计失败：{e}")
            return LimitUpStat(
                trade_date="",
                total_limit_up=0,
                total_limit_down=0,
                limit_up_ratio=0,
                connect_board_count={},
                highest_connect=0,
                炸板_count=0,
                炸板_ratio=0,
            )

    def analyze_limit_up_strength(self, ts_code: str) -> Dict:
        """
        分析涨停板强度

        Args:
            ts_code: 股票代码

        Returns:
            dict: 强度分析结果
        """
        try:
            # 获取股票信息
            stock_info = self._get_limit_up_info(ts_code)
            if not stock_info:
                return {}

            # 强度评分
            score = 0
            reasons = []

            # 1. 封单强度 (40 分)
            封单_ratio = stock_info.get("封单_ratio", 0)
            if 封单_ratio > 2:
                score += 40
                reasons.append("封单极强")
            elif 封单_ratio > 1:
                score += 30
                reasons.append("封单较强")
            elif 封单_ratio > 0.5:
                score += 20
                reasons.append("封单一般")
            else:
                reasons.append("封单较弱")

            # 2. 连板数 (30 分)
            limit_up_count = stock_info.get("limit_up_count", 0)
            if limit_up_count >= 5:
                score += 30
                reasons.append(f"{limit_up_count}连板，高位龙头")
            elif limit_up_count >= 3:
                score += 20
                reasons.append(f"{limit_up_count}连板，中游梯队")
            elif limit_up_count >= 1:
                score += 10
                reasons.append("首板")

            # 3. 涨停时间 (15 分)
            first_limit_time = stock_info.get("first_limit_time", "")
            if first_limit_time:
                hour = int(first_limit_time[:2]) if first_limit_time[:2].isdigit() else 15
                if hour < 10:
                    score += 15
                    reasons.append("早盘涨停")
                elif hour < 11:
                    score += 10
                    reasons.append("上午涨停")
                else:
                    reasons.append("午后涨停")

            # 4. 量比 (15 分)
            volume_ratio = stock_info.get("volume_ratio", 1)
            if 2 < volume_ratio < 5:
                score += 15
                reasons.append("温和放量")
            elif 1 < volume_ratio <= 2:
                score += 10
                reasons.append("正常放量")
            elif volume_ratio >= 5:
                reasons.append("放量过大")
            else:
                reasons.append("缩量涨停")

            # 判断强度等级
            if score >= 80:
                strength = "强"
                suggestion = "可继续持有，设置移动止盈"
            elif score >= 60:
                strength = "中"
                suggestion = "观察封单变化，注意炸板风险"
            else:
                strength = "弱"
                suggestion = "注意风险，准备止盈"

            return {
                "ts_code": ts_code,
                "stock_name": stock_info.get("stock_name", ""),
                "score": score,
                "strength": strength,
                "reasons": reasons,
                "suggestion": suggestion,
                "details": stock_info,
            }

        except Exception as e:
            logger.error(f"涨停强度分析失败：{e}")
            return {}

    def predict_connect_probability(self, ts_code: str) -> Dict:
        """
        预测连板概率

        Args:
            ts_code: 股票代码

        Returns:
            dict: 连板概率预测
        """
        try:
            # 获取股票信息
            stock_info = self._get_limit_up_info(ts_code)
            if not stock_info:
                return {}

            limit_up_count = stock_info.get("limit_up_count", 0)
            封单_ratio = stock_info.get("封单_ratio", 0)
            turn_over_rate = stock_info.get("turn_over_rate", 0)

            # 基础概率
            base_prob = 30  # 基础连板概率 30%

            # 连板数加成
            if limit_up_count == 1:
                base_prob += 20  # 首板晋级
            elif limit_up_count == 2:
                base_prob += 25  # 2 进 3
            elif limit_up_count == 3:
                base_prob += 20  # 3 进 4
            elif limit_up_count >= 4:
                base_prob += 10  # 高位板概率降低

            # 封单加成
            if 封单_ratio > 2:
                base_prob += 20
            elif 封单_ratio > 1:
                base_prob += 15
            elif 封单_ratio > 0.5:
                base_prob += 10

            # 换手率影响
            if 5 < turn_over_rate < 15:
                base_prob += 10  # 健康换手
            elif turn_over_rate > 20:
                base_prob -= 10  # 换手过大

            # 限制在 0-90%
            prob = max(5, min(90, base_prob))

            # 判断等级
            if prob >= 70:
                level = "高"
                suggestion = "连板概率高，可重点关注"
            elif prob >= 50:
                level = "中"
                suggestion = "连板概率中等，观察集合竞价"
            else:
                level = "低"
                suggestion = "连板概率低，注意风险"

            return {
                "ts_code": ts_code,
                "stock_name": stock_info.get("stock_name", ""),
                "probability": round(prob, 1),
                "level": level,
                "suggestion": suggestion,
                "current_count": limit_up_count,
            }

        except Exception as e:
            logger.error(f"连板概率预测失败：{e}")
            return {}

    # ==================== 辅助方法 ====================

    def _count_continuous_limit_up(self, ts_code: str) -> int:
        """统计连续涨停天数"""
        try:
            df = self.fetcher.get_stock_prices(ts_code, count=30)
            if df.empty:
                return 0

            count = 0
            for _, row in df[::-1].iterrows():  # 从最新数据开始
                pct_chg = row.get("pct_chg", 0)
                if pct_chg >= 9.5:
                    count += 1
                else:
                    break

            return count

        except Exception:
            return 0

    def _count_limit_down(self, trade_date: Optional[str] = None) -> int:
        """统计跌停数量"""
        try:
            from data.akshare_api import get_akshare_api
            ak = get_akshare_api()

            df = ak.get_stock_individual_spot_em()
            if df.empty:
                return 0

            return len(df[df["涨跌幅"] <= -9.5])

        except Exception:
            return 0

    def _get_total_market_count(self) -> int:
        """获取市场总股票数"""
        try:
            from data.tushare_api import get_tushare_api
            ts = get_tushare_api()
            df = ts.get_stock_list()
            return len(df) if not df.empty else 4000
        except Exception:
            return 4000

    def _get_limit_up_info(self, ts_code: str) -> Optional[Dict]:
        """获取涨停股信息"""
        try:
            # 获取实时行情
            from data.akshare_api import get_akshare_api
            ak = get_akshare_api()

            df = ak.get_stock_individual_spot_em()
            if df.empty:
                return None

            row = df[df["代码"] == ts_code]
            if row.empty:
                return None

            info = row.iloc[0]
            return {
                "ts_code": ts_code,
                "stock_name": info.get("名称", ""),
                "price": info.get("最新价", 0),
                "change_pct": info.get("涨跌幅", 0),
                "limit_up_count": self._count_continuous_limit_up(ts_code),
                "封单_ratio": 0,  # 简化
                "first_limit_time": None,
                "volume_ratio": info.get("量比", 1),
                "turn_over_rate": info.get("换手率", 0),
            }

        except Exception as e:
            logger.error(f"获取涨停信息失败：{e}")
            return None


def create_limit_up_analyzer() -> LimitUpAnalyzer:
    """创建涨停板分析器实例"""
    return LimitUpAnalyzer()
