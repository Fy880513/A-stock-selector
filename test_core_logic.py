"""
测试龙头战法策略核心逻辑
"""
import random
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional


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


class MockDragonStrategy:
    """模拟龙头战法策略"""

    def __init__(self):
        self._stock_info_cache = {}
        self._board_performance_cache = {}

    def get_industry_board_list(self) -> List[str]:
        """获取行业板块列表"""
        return ['人工智能', '新能源', '半导体', '医药', '大消费']

    def get_board_stocks(self, board_name: str) -> List[str]:
        """获取板块成分股"""
        # 模拟每个板块有20只股票
        return [f'{i:06d}' for i in range(1, 21)]

    def get_board_performance(self, board_name: str) -> Dict:
        """获取板块涨跌幅表现"""
        # 检查缓存
        if board_name in self._board_performance_cache:
            return self._board_performance_cache[board_name]

        # 模拟板块表现数据
        change_pct = random.uniform(-5, 10)
        change_5d = random.uniform(-10, 30)
        board_strength = min((change_pct + change_5d / 5) * 2, 100)

        result = {
            "board_name": board_name,
            "change_1d": change_pct,
            "change_5d": change_5d,
            "volume": random.uniform(10000000, 100000000),
            "amount": random.uniform(100000000, 1000000000),
            "board_strength": board_strength
        }

        # 缓存结果
        self._board_performance_cache[board_name] = result
        return result

    def _get_stock_info(self, ts_code: str) -> Optional[Dict]:
        """获取股票实时信息"""
        # 检查缓存
        if ts_code in self._stock_info_cache:
            return self._stock_info_cache[ts_code]

        # 模拟股票信息
        info = {
            "ts_code": ts_code,
            "name": f"股票{ts_code}",
            "price": random.uniform(10, 100),
            "change_pct": random.uniform(-10, 10),
            "volume": random.uniform(1000000, 10000000),
            "amount": random.uniform(10000000, 100000000),
            "market_value": random.uniform(1000000000, 10000000000),
            "volume_ratio": random.uniform(0.5, 5),
            "turn_over_rate": random.uniform(0, 30),
            "industry": "人工智能",
        }

        # 缓存结果
        self._stock_info_cache[ts_code] = info
        return info

    def _count_limit_up_days(self, ts_code: str, days: int = 30) -> int:
        """统计连板天数"""
        # 模拟连板数
        return random.randint(0, 5)

    def _get_first_limit_time(self, ts_code: str) -> Optional[str]:
        """获取首次涨停时间"""
        # 模拟9:30-14:59之间的涨停时间
        hour = random.randint(9, 14)
        minute = random.randint(0, 59)
        if hour == 9 and minute < 30:
            minute = 30
        return f"{hour:02d}:{minute:02d}"

    def _get_limit_up_volume(self, ts_code: str) -> float:
        """获取封单金额"""
        # 模拟封单金额（1000万-10亿）
        return random.uniform(10000000, 1000000000)

    def _guess_limit_up_reason(self, ts_code: str) -> str:
        """猜测涨停原因"""
        reasons = [
            "板块龙头",
            "题材驱动",
            "业绩超预期",
            "政策利好",
            "资金追捧",
            "技术突破"
        ]
        return random.choice(reasons)

    def identify_dragon_stocks(self, board_name: str, top_n: int = 3) -> List[DragonStock]:
        """识别板块龙头股"""
        # 获取板块成分股
        stock_codes = self.get_board_stocks(board_name)
        if not stock_codes:
            return []

        # 限制处理数量
        stock_codes = stock_codes[:100]

        # 获取板块强度
        board_performance = self.get_board_performance(board_name)
        board_strength = board_performance.get("board_strength", 50)

        # 获取股票信息
        dragon_candidates = []
        for code in stock_codes:
            info = self._get_stock_info(code)
            if not info:
                continue

            # 计算龙头特征
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

    def analyze_limit_up(self, ts_code: str) -> Optional[LimitUpInfo]:
        """分析涨停板"""
        # 获取股票信息
        info = self._get_stock_info(ts_code)
        if not info:
            return None

        # 检查是否涨停
        change_pct = info.get("change_pct", 0)
        if change_pct < 9.5:
            print(f"{ts_code} 当前涨幅 {change_pct:.2f}%, 未达到涨停")
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

    def find_dragon_switch(self, board_name: str) -> Dict:
        """寻找龙头切换机会"""
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


def test_dragon_strategy():
    """测试龙头战法策略"""
    print("测试龙头战法策略...")
    
    # 创建策略实例
    strategy = MockDragonStrategy()
    
    # 测试获取行业板块列表
    print("\n1. 测试获取行业板块列表:")
    boards = strategy.get_industry_board_list()
    print(f"获取到 {len(boards)} 个板块")
    if boards:
        print(f"前5个板块: {boards[:5]}")
    
    # 测试获取板块成分股
    print("\n2. 测试获取板块成分股:")
    test_board = "人工智能"
    stocks = strategy.get_board_stocks(test_board)
    print(f"{test_board} 板块有 {len(stocks)} 只股票")
    if stocks:
        print(f"前5只股票: {stocks[:5]}")
    
    # 测试识别龙头股
    print(f"\n3. 测试识别 {test_board} 板块龙头股:")
    dragons = strategy.identify_dragon_stocks(test_board, top_n=3)
    print(f"识别到 {len(dragons)} 只龙头股")
    
    if dragons:
        print("\n龙头股列表:")
        print(f"{'排名':<6}{'代码':<10}{'名称':<12}{'涨幅':<10}{'连板':<8}{'置信度':<8}{'板块强度':<10}")
        print("-" * 70)
        
        for d in dragons:
            print(f"#{d.rank:<5}{d.ts_code:<10}{d.stock_name:<12}{d.change_pct:>8.2f}%" 
                  f"{d.limit_up_count:>6}板     {d.confidence:<8}{d.board_strength:>9.1f}")
    
    # 测试龙头切换分析
    print(f"\n4. 测试 {test_board} 板块龙头切换分析:")
    switch_info = strategy.find_dragon_switch(test_board)
    
    if switch_info:
        current_dragon = switch_info.get("current_dragon")
        potential_dragon = switch_info.get("potential_dragon")
        switch_signal = switch_info.get("switch_signal")
        analysis = switch_info.get("analysis")
        confidence = switch_info.get("confidence", "低")
        
        print(f"分析结果: {analysis}")
        print(f"切换信号: {'有' if switch_signal else '无'}")
        print(f"置信度: {confidence}")
        
        if current_dragon:
            print(f"当前龙头: {current_dragon.stock_name} ({current_dragon.ts_code})")
        if potential_dragon:
            print(f"潜在新龙头: {potential_dragon.stock_name} ({potential_dragon.ts_code})")
    
    # 测试涨停板分析
    print("\n5. 测试涨停板分析:")
    if stocks:
        # 模拟一个涨停的股票
        test_stock = stocks[0]
        # 修改股票信息使其涨停
        info = strategy._get_stock_info(test_stock)
        info['change_pct'] = 10.0  # 涨停
        
        limit_up_info = strategy.analyze_limit_up(test_stock)
        if limit_up_info:
            print(f"股票: {limit_up_info.stock_name} ({limit_up_info.ts_code})")
            print(f"涨停原因: {limit_up_info.limit_up_reason}")
            print(f"强度: {limit_up_info.strength}")
            print(f"封单金额: {limit_up_info.封单_amount:.2f}")
            print(f"封单比例: {limit_up_info.封单_ratio:.2f}%")
            print(f"板块强度: {limit_up_info.board_strength:.1f}")
        else:
            print(f"{test_stock} 未达到涨停或分析失败")
    
    print("\n测试完成！")


if __name__ == "__main__":
    test_dragon_strategy()
