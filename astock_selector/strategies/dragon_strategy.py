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
import asyncio
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
    board_strength: float  # 板块强度


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
    board_strength: float  # 板块强度


class DragonStrategy:
    """龙头战法策略"""

    def __init__(self):
        self.fetcher = get_data_fetcher()
        self._stock_info_cache = {}
        self._board_performance_cache = {}

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
        # 检查缓存
        if board_name in self._board_performance_cache:
            return self._board_performance_cache[board_name]

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

            # 计算板块强度得分
            board_strength = min((change_pct + change_5d / 5) * 2, 100)

            result = {
                "board_name": board_name,
                "change_1d": change_pct,
                "change_5d": change_5d,
                "volume": latest.get("成交量", 0),
                "amount": latest.get("成交额", 0),
                "board_strength": board_strength
            }

            # 缓存结果
            self._board_performance_cache[board_name] = result
            return result

        except Exception as e:
            logger.error(f"获取板块表现失败：{e}")
            return {}

    async def identify_dragon_stocks_async(
        self,
        board_name: str,
        top_n: int = 3,
    ) -> List[DragonStock]:
        """
        异步识别板块龙头股

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

        # 限制处理数量，避免过多请求
        stock_codes = stock_codes[:100]

        # 获取板块强度
        board_performance = self.get_board_performance(board_name)
        board_strength = board_performance.get("board_strength", 50)

        # 异步获取股票信息
        tasks = [self._get_stock_info_async(code) for code in stock_codes]
        stock_infos = await asyncio.gather(*tasks)

        # 过滤无效信息
        valid_infos = [info for info in stock_infos if info]

        # 计算龙头特征
        dragon_candidates = []
        for info in valid_infos:
            code = info["ts_code"]
            limit_up_count = self._count_limit_up_days(code)
            limit_up_time = self._get_first_limit_time(code)

            dragon_candidates.append({
                "ts_code": code,
                "stock_name": info.get("name", code),
                "price": info.get("price", 0),
                "change_pct": info.get("change_pct", 0),
                "limit_up_count": limit_up_count,
                "limit_up_time": limit_up_time,
                "market_value": info.get("market_value", 0),
                "volume_ratio": info.get("volume_ratio", 1),
                "turn_over_rate": info.get("turn_over_rate", 0),
                "board_strength": board_strength
            })

        # 龙头评分：连板数 (35%) + 涨幅 (25%) + 涨停时间 (15%) + 量比 (10%) + 换手率 (10%) + 板块强度 (5%)
        for candidate in dragon_candidates:
            score = 0

            # 连板数评分
            score += min(candidate["limit_up_count"] * 17.5, 35)

            # 涨幅评分
            if candidate["change_pct"] >= 9.5:  # 涨停
                score += 25
            elif candidate["change_pct"] >= 7:
                score += 20
            elif candidate["change_pct"] >= 5:
                score += 15
            elif candidate["change_pct"] >= 3:
                score += 10
            elif candidate["change_pct"] >= 0:
                score += 5

            # 涨停时间评分（越早越好）
            if candidate["limit_up_time"]:
                try:
                    hour = int(candidate["limit_up_time"][:2])
                    minute = int(candidate["limit_up_time"][3:5])
                    # 计算分钟数，9:30为0分
                    total_minutes = (hour - 9) * 60 + (minute - 30) if hour >= 9 else 0
                    if total_minutes < 30:  # 10点前
                        score += 15
                    elif total_minutes < 90:  # 11点前
                        score += 10
                    elif total_minutes < 180:  # 13:30前
                        score += 5
                    else:
                        score += 2
                except:
                    score += 5

            # 量比评分
            volume_ratio = candidate["volume_ratio"]
            if volume_ratio > 5:
                score += 10
            elif volume_ratio > 3:
                score += 8
            elif volume_ratio > 2:
                score += 6
            elif volume_ratio > 1.5:
                score += 4
            elif volume_ratio > 1:
                score += 2

            # 换手率评分
            turn_over = candidate["turn_over_rate"]
            if turn_over > 15:
                score += 10
            elif turn_over > 10:
                score += 8
            elif turn_over > 5:
                score += 6
            elif turn_over > 2:
                score += 4
            elif turn_over > 1:
                score += 2

            # 板块强度评分
            score += candidate["board_strength"] * 0.05

            candidate["dragon_score"] = score

        # 排序
        dragon_candidates.sort(key=lambda x: x["dragon_score"], reverse=True)

        # 生成结果
        result = []
        for i, c in enumerate(dragon_candidates[:top_n]):
            # 确定置信度
            if c["dragon_score"] >= 85:
                confidence = "高"
            elif c["dragon_score"] >= 65:
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
                board_strength=c["board_strength"]
            ))

        return result

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
        return asyncio.run(self.identify_dragon_stocks_async(board_name, top_n))

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

            # 获取封单数据
            封单_amount = self._get_limit_up_volume(ts_code)
            market_value = info.get("market_value", 10000000000)
            封单_ratio = 封单_amount / market_value * 100 if market_value > 0 else 0

            # 判断强度
            if 封单_ratio > 1.5:
                strength = "强"
            elif 封单_ratio > 0.8:
                strength = "中强"
            elif 封单_ratio > 0.3:
                strength = "中"
            else:
                strength = "弱"

            # 涨停原因
            limit_up_reason = self._guess_limit_up_reason(ts_code)

            # 获取板块强度
            industry = info.get("industry", "")
            board_performance = self.get_board_performance(industry)
            board_strength = board_performance.get("board_strength", 50)

            return LimitUpInfo(
                ts_code=ts_code,
                stock_name=info.get("name", ts_code),
                board_name=industry,
                price=info.get("price", 0),
                limit_up_count=limit_up_count,
                limit_up_reason=limit_up_reason,
                封单_amount=封单_amount,
                封单_ratio=封单_ratio,
                first_limit_time=self._get_first_limit_time(ts_code),
                last_open_time=None,
                strength=strength,
                board_strength=board_strength
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
            "confidence": "低"
        }

        # 当前龙头
        current = dragons[0]
        result["current_dragon"] = current

        # 获取板块强度
        board_performance = self.get_board_performance(board_name)
        board_strength = board_performance.get("board_strength", 50)

        # 检查老龙头是否走弱的多种信号
        weak_signals = 0
        
        # 信号1：下跌
        if current.change_pct < 0:
            weak_signals += 1
        
        # 信号2：高位（连板数多）
        if current.limit_up_count >= 3:
            weak_signals += 1
        
        # 信号3：量比异常（放量下跌）
        if current.volume_ratio > 3 and current.change_pct < 0:
            weak_signals += 1
        
        # 信号4：换手率过高
        if current.turn_over_rate > 20:
            weak_signals += 1

        # 判断是否有切换信号
        if weak_signals >= 2:
            result["switch_signal"] = True

            # 寻找潜在新龙头，综合考虑多个因素
            potential_candidates = []
            for d in dragons[1:]:
                # 候选新龙头评分
                candidate_score = 0
                
                # 涨幅
                if d.change_pct >= 9.5:
                    candidate_score += 30
                elif d.change_pct >= 7:
                    candidate_score += 25
                elif d.change_pct >= 5:
                    candidate_score += 20
                
                # 连板数
                candidate_score += d.limit_up_count * 10
                
                # 量比
                if d.volume_ratio > 3:
                    candidate_score += 15
                elif d.volume_ratio > 1.5:
                    candidate_score += 10
                
                # 换手率
                if d.turn_over_rate > 10:
                    candidate_score += 10
                elif d.turn_over_rate > 5:
                    candidate_score += 5
                
                # 板块强度
                candidate_score += d.board_strength * 0.2
                
                potential_candidates.append((d, candidate_score))
            
            # 排序并选择最佳候选
            if potential_candidates:
                potential_candidates.sort(key=lambda x: x[1], reverse=True)
                best_candidate, score = potential_candidates[0]
                result["potential_dragon"] = best_candidate
                
                # 切换置信度
                if score >= 80:
                    result["confidence"] = "高"
                elif score >= 60:
                    result["confidence"] = "中"
                
                result["analysis"] = f"老龙头{current.stock_name}出现{weak_signals}个走弱信号，{best_candidate.stock_name}有望成为新龙头"

        if not result["switch_signal"]:
            result["analysis"] = f"当前龙头{current.stock_name}地位稳固，连板{current.limit_up_count}个，板块强度{board_strength:.1f}"

        return result

    # ==================== 辅助方法 ====================

    async def _get_stock_info_async(self, ts_code: str) -> Optional[Dict]:
        """异步获取股票实时信息"""
        # 检查缓存
        if ts_code in self._stock_info_cache:
            return self._stock_info_cache[ts_code]

        try:
            # 获取实时行情
            df = self.fetcher.get_stock_prices(ts_code, count=1)
            if df.empty:
                return None

            latest = df.iloc[0]
            
            # 尝试获取股票基本信息（如果API支持）
            stock_name = ts_code
            industry = ""
            volume_ratio = 1.0
            turn_over_rate = 0.0
            
            try:
                # 这里可以添加获取股票基本信息的代码
                # 例如：basic_info = self.fetcher.get_stock_basic(ts_code)
                # if basic_info:
                #     stock_name = basic_info.get("name", ts_code)
                #     industry = basic_info.get("industry", "")
                pass
            except Exception:
                pass

            info = {
                "ts_code": ts_code,
                "name": stock_name,
                "price": latest.get("close", 0),
                "change_pct": latest.get("pct_chg", 0),
                "volume": latest.get("vol", 0),
                "amount": latest.get("amount", 0),
                "market_value": latest.get("circ_mv", 0) * 1000000,  # 转为元
                "volume_ratio": volume_ratio,
                "turn_over_rate": turn_over_rate,
                "industry": industry,
            }

            # 缓存结果
            self._stock_info_cache[ts_code] = info
            return info

        except Exception as e:
            logger.error(f"获取股票信息失败：{e}")
            return None

    def _get_stock_info(self, ts_code: str) -> Optional[Dict]:
        """获取股票实时信息"""
        return asyncio.run(self._get_stock_info_async(ts_code))

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

        except Exception as e:
            logger.error(f"统计连板天数失败：{e}")
            return 0

    def _get_first_limit_time(self, ts_code: str) -> Optional[str]:
        """获取首次涨停时间"""
        try:
            # 实际项目中，这里应该从盘口数据或更细粒度的历史数据中获取
            # 这里使用模拟数据作为示例
            import random
            # 模拟9:30-14:59之间的涨停时间
            hour = random.randint(9, 14)
            minute = random.randint(0, 59)
            if hour == 9 and minute < 30:
                minute = 30
            return f"{hour:02d}:{minute:02d}"
        except Exception:
            return None

    def _get_limit_up_volume(self, ts_code: str) -> float:
        """获取封单金额"""
        try:
            # 实际项目中，这里应该从盘口数据中获取
            # 这里使用模拟数据作为示例
            import random
            # 模拟封单金额（1000万-10亿）
            return random.uniform(10000000, 1000000000)
        except Exception:
            return 0.0

    def _guess_limit_up_reason(self, ts_code: str) -> str:
        """猜测涨停原因"""
        try:
            # 实际项目中，这里应该基于新闻、公告、题材等多源数据分析
            # 这里使用模拟数据作为示例
            reasons = [
                "板块龙头",
                "题材驱动",
                "业绩超预期",
                "政策利好",
                "资金追捧",
                "技术突破"
            ]
            import random
            return random.choice(reasons)
        except Exception:
            return "题材驱动"


def create_dragon_strategy() -> DragonStrategy:
    """创建龙头战法策略实例"""
    return DragonStrategy()
