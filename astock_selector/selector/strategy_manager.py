"""
策略管理器模块

实现策略切换和组合功能
支持多种策略模式：
- 单一策略：仅使用原有综合评分、龙头战法、ML 选股等
- 组合策略：多个策略加权融合
"""
import pandas as pd
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class StrategyMode(Enum):
    """策略模式"""
    COMPREHENSIVE = "comprehensive"  # 综合评分（原有系统）
    DRAGON = "dragon"  # 龙头战法
    LIMIT_UP = "limit_up"  # 涨停板
    ML = "ml"  # ML 选股
    SEAT = "seat"  # 龙虎榜席位
    COMBINED = "combined"  # 组合策略


@dataclass
class StrategyConfig:
    """策略配置"""
    mode: StrategyMode
    weight: float = 1.0  # 策略权重
    enabled: bool = True
    params: Optional[Dict] = None  # 策略特定参数


@dataclass
class StockCandidate:
    """股票候选"""
    ts_code: str
    stock_name: str
    comprehensive_score: float = 50.0  # 综合评分
    dragon_score: float = 50.0  # 龙头评分
    limit_up_score: float = 50.0  # 涨停评分
    ml_score: float = 50.0  # ML 评分
    seat_score: float = 50.0  # 席位评分
    final_score: float = 50.0  # 最终得分
    rank: int = 0
    selected_strategies: List[str] = None

    def __post_init__(self):
        if self.selected_strategies is None:
            self.selected_strategies = []


class StrategyManager:
    """策略管理器"""

    def __init__(self):
        self.strategies: Dict[str, StrategyConfig] = {}
        self.default_weights = {
            "comprehensive": 0.40,
            "dragon": 0.25,
            "limit_up": 0.15,
            "ml": 0.10,
            "seat": 0.10,
        }

    def add_strategy(self, name: str, config: StrategyConfig):
        """添加策略"""
        self.strategies[name] = config
        logger.info(f"添加策略：{name} - {config.mode.value}")

    def remove_strategy(self, name: str):
        """移除策略"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info(f"移除策略：{name}")

    def enable_strategy(self, name: str):
        """启用策略"""
        if name in self.strategies:
            self.strategies[name].enabled = True

    def disable_strategy(self, name: str):
        """禁用策略"""
        if name in self.strategies:
            self.strategies[name].enabled = False

    def set_strategy_weight(self, name: str, weight: float):
        """设置策略权重"""
        if name in self.strategies:
            self.strategies[name].weight = weight

    def get_enabled_strategies(self) -> List[str]:
        """获取已启用的策略列表"""
        return [
            name for name, config in self.strategies.items()
            if config.enabled
        ]

    def calculate_combined_score(
        self,
        comprehensive_score: float = 50.0,
        dragon_score: float = 50.0,
        limit_up_score: float = 50.0,
        ml_score: float = 50.0,
        seat_score: float = 50.0,
    ) -> float:
        """
        计算组合得分

        Args:
            comprehensive_score: 综合评分
            dragon_score: 龙头评分
            limit_up_score: 涨停评分
            ml_score: ML 评分
            seat_score: 席位评分

        Returns:
            float: 组合得分
        """
        enabled = self.get_enabled_strategies()

        if not enabled:
            # 默认使用综合评分
            return comprehensive_score

        total_score = 0.0
        total_weight = 0.0

        if "comprehensive" in enabled:
            w = self.strategies.get("comprehensive", StrategyConfig(StrategyMode.COMPREHENSIVE)).weight
            total_score += comprehensive_score * w
            total_weight += w

        if "dragon" in enabled:
            w = self.strategies.get("dragon", StrategyConfig(StrategyMode.DRAGON)).weight
            total_score += dragon_score * w
            total_weight += w

        if "limit_up" in enabled:
            w = self.strategies.get("limit_up", StrategyConfig(StrategyMode.LIMIT_UP)).weight
            total_score += limit_up_score * w
            total_weight += w

        if "ml" in enabled:
            w = self.strategies.get("ml", StrategyConfig(StrategyMode.ML)).weight
            total_score += ml_score * w
            total_weight += w

        if "seat" in enabled:
            w = self.strategies.get("seat", StrategyConfig(StrategyMode.SEAT)).weight
            total_score += seat_score * w
            total_weight += w

        # 归一化
        if total_weight > 0:
            return total_score / total_weight
        return comprehensive_score

    def merge_stock_lists(
        self,
        comprehensive_stocks: List[Dict],
        dragon_stocks: Optional[List[Dict]] = None,
        limit_up_stocks: Optional[List[Dict]] = None,
        ml_stocks: Optional[List[Dict]] = None,
        seat_stocks: Optional[List[Dict]] = None,
    ) -> List[StockCandidate]:
        """
        合并多个策略的股票列表

        Args:
            comprehensive_stocks: 综合选股结果
            dragon_stocks: 龙头股列表
            limit_up_stocks: 涨停股列表
            ml_stocks: ML 选股列表
            seat_stocks: 龙虎榜股票列表

        Returns:
            List[StockCandidate]: 合并后的候选股票列表
        """
        # 收集所有股票代码
        all_codes: Set[str] = set()

        for s in comprehensive_stocks:
            all_codes.add(s.get("ts_code", ""))
        if dragon_stocks:
            for s in dragon_stocks:
                all_codes.add(s.get("ts_code", ""))
        if limit_up_stocks:
            for s in limit_up_stocks:
                all_codes.add(s.get("ts_code", ""))
        if ml_stocks:
            for s in ml_stocks:
                all_codes.add(s.get("ts_code", ""))
        if seat_stocks:
            for s in seat_stocks:
                all_codes.add(s.get("ts_code", ""))

        # 创建股票候选
        candidates = []

        for code in all_codes:
            if not code:
                continue

            candidate = StockCandidate(ts_code=code, stock_name="")

            # 查找各策略中的数据
            for s in comprehensive_stocks:
                if s.get("ts_code") == code:
                    candidate.stock_name = s.get("stock_name", "")
                    candidate.comprehensive_score = s.get("total_score", 50.0)
                    candidate.selected_strategies.append("comprehensive")
                    break

            if dragon_stocks:
                for s in dragon_stocks:
                    if s.get("ts_code") == code:
                        if not candidate.stock_name:
                            candidate.stock_name = s.get("stock_name", "")
                        candidate.dragon_score = s.get("dragon_score", 50.0)
                        candidate.selected_strategies.append("dragon")
                        break

            if limit_up_stocks:
                for s in limit_up_stocks:
                    if s.get("ts_code") == code:
                        if not candidate.stock_name:
                            candidate.stock_name = s.get("stock_name", "")
                        candidate.limit_up_score = s.get("limit_up_score", 50.0)
                        candidate.selected_strategies.append("limit_up")
                        break

            if ml_stocks:
                for s in ml_stocks:
                    if s.get("ts_code") == code:
                        if not candidate.stock_name:
                            candidate.stock_name = s.get("stock_name", "")
                        candidate.ml_score = s.get("ml_score", 50.0)
                        candidate.selected_strategies.append("ml")
                        break

            if seat_stocks:
                for s in seat_stocks:
                    if s.get("ts_code") == code:
                        if not candidate.stock_name:
                            candidate.stock_name = s.get("stock_name", "")
                        candidate.seat_score = s.get("seat_score", 50.0)
                        candidate.selected_strategies.append("seat")
                        break

            # 计算最终得分
            candidate.final_score = self.calculate_combined_score(
                candidate.comprehensive_score,
                candidate.dragon_score,
                candidate.limit_up_score,
                candidate.ml_score,
                candidate.seat_score,
            )

            candidates.append(candidate)

        # 排序
        candidates.sort(key=lambda x: x.final_score, reverse=True)

        # 设置排名
        for i, c in enumerate(candidates):
            c.rank = i + 1

        return candidates

    def get_preset_config(self, preset_name: str) -> Dict[str, StrategyConfig]:
        """
        获取预设策略配置

        Args:
            preset_name: 预设名称

        Returns:
            Dict[str, StrategyConfig]: 策略配置
        """
        presets = {
            # 稳健型：仅使用综合评分
            "conservative": {
                "comprehensive": StrategyConfig(
                    mode=StrategyMode.COMPREHENSIVE,
                    weight=1.0,
                    enabled=True,
                ),
            },

            # 激进型：龙头战法 + 涨停板
            "aggressive": {
                "dragon": StrategyConfig(
                    mode=StrategyMode.DRAGON,
                    weight=0.6,
                    enabled=True,
                ),
                "limit_up": StrategyConfig(
                    mode=StrategyMode.LIMIT_UP,
                    weight=0.4,
                    enabled=True,
                ),
            },

            # 平衡型：综合 + 龙头+ML
            "balanced": {
                "comprehensive": StrategyConfig(
                    mode=StrategyMode.COMPREHENSIVE,
                    weight=0.5,
                    enabled=True,
                ),
                "dragon": StrategyConfig(
                    mode=StrategyMode.DRAGON,
                    weight=0.3,
                    enabled=True,
                ),
                "ml": StrategyConfig(
                    mode=StrategyMode.ML,
                    weight=0.2,
                    enabled=True,
                ),
            },

            # 全策略：所有策略融合
            "all_in": {
                "comprehensive": StrategyConfig(
                    mode=StrategyMode.COMPREHENSIVE,
                    weight=0.4,
                    enabled=True,
                ),
                "dragon": StrategyConfig(
                    mode=StrategyMode.DRAGON,
                    weight=0.25,
                    enabled=True,
                ),
                "limit_up": StrategyConfig(
                    mode=StrategyMode.LIMIT_UP,
                    weight=0.15,
                    enabled=True,
                ),
                "ml": StrategyConfig(
                    mode=StrategyMode.ML,
                    weight=0.1,
                    enabled=True,
                ),
                "seat": StrategyConfig(
                    mode=StrategyMode.SEAT,
                    weight=0.1,
                    enabled=True,
                ),
            },

            # 龙虎榜：席位分析为主
            "seat_focus": {
                "seat": StrategyConfig(
                    mode=StrategyMode.SEAT,
                    weight=0.5,
                    enabled=True,
                ),
                "comprehensive": StrategyConfig(
                    mode=StrategyMode.COMPREHENSIVE,
                    weight=0.3,
                    enabled=True,
                ),
                "dragon": StrategyConfig(
                    mode=StrategyMode.DRAGON,
                    weight=0.2,
                    enabled=True,
                ),
            },
        }

        return presets.get(preset_name, presets["conservative"])

    def load_preset(self, preset_name: str):
        """
        加载预设策略

        Args:
            preset_name: 预设名称
        """
        config = self.get_preset_config(preset_name)
        self.strategies = config
        logger.info(f"加载预设策略：{preset_name}")


def create_strategy_manager() -> StrategyManager:
    """创建策略管理器实例"""
    return StrategyManager()
