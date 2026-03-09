"""
策略管理器模块

实现策略切换和组合功能
支持多种策略模式：
- 单一策略：仅使用原有综合评分、龙头战法、ML 选股等
- 组合策略：多个策略加权融合
- 自定义权重：用户可根据市场环境调整各策略权重
"""
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

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
    min_score: float = 0.0  # 最低得分要求
    max_score: float = 100.0  # 最高得分要求
    performance: float = 0.0  # 策略性能指标
    last_updated: str = ""  # 最后更新时间


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
    selected_strategies: List[str] = field(default_factory=list)
    selection_reasons: List[str] = field(default_factory=list)  # 入选理由


@dataclass
class RotationConfig:
    """策略轮动配置"""
    enabled: bool = True  # 是否启用轮动
    evaluation_period: int = 30  # 评估周期（天）
    top_n: int = 3  # 选择前 N 个策略
    performance_metric: str = "sharpe_ratio"  # 性能指标
    min_weight: float = 0.1  # 最小权重
    max_weight: float = 0.6  # 最大权重
    adjustment_factor: float = 0.1  # 调整因子


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
        # 市场环境配置（用于动态调整权重）
        self.market_condition = "normal"  # bull/bear/normal/volatile
        # 策略轮动配置
        self.rotation_config = RotationConfig()
        # 策略历史性能
        self.strategy_performance = {}
        # 轮动历史
        self.rotation_history = []

    def set_market_condition(self, condition: str):
        """
        设置市场环境，自动调整权重

        Args:
            condition: 市场环境 (bull/bear/normal/volatile)
        """
        self.market_condition = condition
        logger.info(f"市场环境设置为：{condition}")

        # 根据市场环境自动调整权重
        if condition == "bull":  # 牛市：增加激进策略权重
            self.default_weights["dragon"] = 0.35
            self.default_weights["limit_up"] = 0.20
            self.default_weights["comprehensive"] = 0.30
        elif condition == "bear":  # 熊市：增加稳健策略权重
            self.default_weights["comprehensive"] = 0.60
            self.default_weights["dragon"] = 0.15
            self.default_weights["limit_up"] = 0.05
        elif condition == "volatile":  # 震荡市：平衡配置
            self.default_weights["comprehensive"] = 0.40
            self.default_weights["dragon"] = 0.25
            self.default_weights["ml"] = 0.20
        # normal: 使用默认权重

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

    def set_custom_weights(
        self,
        comprehensive: float = 0.40,
        dragon: float = 0.25,
        limit_up: float = 0.15,
        ml: float = 0.10,
        seat: float = 0.10,
    ):
        """
        自定义策略权重

        Args:
            comprehensive: 综合评分权重
            dragon: 龙头战法权重
            limit_up: 涨停板权重
            ml: ML 选股权重
            seat: 龙虎榜席位权重
        """
        total = comprehensive + dragon + limit_up + ml + seat
        if abs(total - 1.0) > 0.01:
            logger.warning(f"权重总和为{total:.2f}，已归一化为 1.0")
            comprehensive /= total
            dragon /= total
            limit_up /= total
            ml /= total
            seat /= total

        self.strategies = {
            "comprehensive": StrategyConfig(
                mode=StrategyMode.COMPREHENSIVE,
                weight=comprehensive,
                enabled=comprehensive > 0,
            ),
            "dragon": StrategyConfig(
                mode=StrategyMode.DRAGON,
                weight=dragon,
                enabled=dragon > 0,
            ),
            "limit_up": StrategyConfig(
                mode=StrategyMode.LIMIT_UP,
                weight=limit_up,
                enabled=limit_up > 0,
            ),
            "ml": StrategyConfig(
                mode=StrategyMode.ML,
                weight=ml,
                enabled=ml > 0,
            ),
            "seat": StrategyConfig(
                mode=StrategyMode.SEAT,
                weight=seat,
                enabled=seat > 0,
            ),
        }
        logger.info(f"设置自定义权重：综合={comprehensive:.2f}, 龙头={dragon:.2f}, "
                    f"涨停={limit_up:.2f}, ML={ml:.2f}, 席位={seat:.2f}")

    def generate_selection_reasons(self, candidate: StockCandidate) -> List[str]:
        """
        生成选股理由

        Args:
            candidate: 股票候选

        Returns:
            List[str]: 选股理由列表
        """
        reasons = []

        # 综合评分高
        if candidate.comprehensive_score >= 75:
            reasons.append(f"综合评分优秀 ({candidate.comprehensive_score:.1f}分)")
        elif candidate.comprehensive_score >= 60:
            reasons.append(f"综合评分良好 ({candidate.comprehensive_score:.1f}分)")

        # 龙头股特征
        if candidate.dragon_score >= 80:
            reasons.append("板块龙头，连板数高")
        elif candidate.dragon_score >= 65:
            reasons.append("板块强势股")

        # 涨停强度
        if candidate.limit_up_score >= 80:
            reasons.append("涨停强度强，封单充足")
        elif candidate.limit_up_score >= 65:
            reasons.append("涨停强度中等")

        # ML 预测
        if candidate.ml_score >= 75:
            reasons.append("ML 模型预测收益高")
        elif candidate.ml_score >= 60:
            reasons.append("ML 模型预测正向收益")

        # 龙虎榜席位
        if candidate.seat_score >= 80:
            reasons.append("龙虎榜机构/北向买入")
        elif candidate.seat_score >= 65:
            reasons.append("龙虎榜席位良好")

        # 多策略共振
        if len(candidate.selected_strategies) >= 3:
            reasons.append(f"多策略共振 ({len(candidate.selected_strategies)}个策略推荐)")

        candidate.selection_reasons = reasons
        return reasons

    def update_strategy_performance(self, strategy_name: str, performance: float):
        """
        更新策略性能（带衰减）

        Args:
            strategy_name: 策略名称
            performance: 性能指标值
        """
        # 获取旧性能并应用衰减
        old_perf = self.strategy_performance.get(strategy_name, {}).get("performance", 0)
        decay_factor = 0.95  # 每月衰减 5%

        # 新性能 = 旧性能 * 衰减 + 新性能 * (1 - 衰减)
        if old_perf > 0:
            performance = old_perf * decay_factor + performance * (1 - decay_factor)

        self.strategy_performance[strategy_name] = {
            "performance": performance,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # 更新策略配置中的性能
        if strategy_name in self.strategies:
            self.strategies[strategy_name].performance = performance
            self.strategies[strategy_name].last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def run_strategy_rotation(self):
        """
        执行策略轮动

        基于历史性能选择表现最好的策略组合
        """
        if not self.rotation_config.enabled:
            logger.info("策略轮动已禁用")
            return

        # 获取所有策略的性能（新策略给予基础分 50，避免永远无法被选中）
        strategy_perfs = []
        for strategy_name, config in self.strategies.items():
            if config.enabled:
                perf_data = self.strategy_performance.get(strategy_name, {})
                if perf_data:
                    perf = perf_data.get("performance", 50)
                else:
                    # 新策略没有性能数据，给予平均分数
                    perf = 50.0
                strategy_perfs.append((strategy_name, perf))

        if not strategy_perfs:
            logger.warning("没有启用的策略，无法执行轮动")
            return

        # 按性能排序
        strategy_perfs.sort(key=lambda x: x[1], reverse=True)

        # 选择前 N 个策略
        top_strategies = strategy_perfs[:self.rotation_config.top_n]
        logger.info(f"轮动选择策略：{[s[0] for s in top_strategies]}")

        # 计算新权重
        total_perf = sum(p[1] for p in top_strategies)
        new_weights = {}

        if total_perf > 0:
            # 基于性能分配权重
            for strategy_name, perf in top_strategies:
                weight = (perf / total_perf) * (1 - (self.rotation_config.top_n - 1) * self.rotation_config.min_weight)
                weight = max(self.rotation_config.min_weight, min(self.rotation_config.max_weight, weight))
                new_weights[strategy_name] = weight
        else:
            # 等权重分配
            weight = 1.0 / len(top_strategies)
            for strategy_name, _ in top_strategies:
                new_weights[strategy_name] = weight

        # 归一化权重
        total_weight = sum(new_weights.values())
        for strategy_name in new_weights:
            new_weights[strategy_name] /= total_weight

        # 更新权重
        for strategy_name, weight in new_weights.items():
            if strategy_name in self.strategies:
                old_weight = self.strategies[strategy_name].weight
                # 平滑过渡
                new_weight = old_weight * (1 - self.rotation_config.adjustment_factor) + weight * self.rotation_config.adjustment_factor
                self.strategies[strategy_name].weight = new_weight
                logger.info(f"调整策略 {strategy_name} 权重：{old_weight:.2f} → {new_weight:.2f}")

        # 记录轮动历史
        self.rotation_history.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "selected_strategies": [s[0] for s in top_strategies],
            "weights": new_weights,
            "market_condition": self.market_condition
        })

    def set_rotation_config(self, config: RotationConfig):
        """
        设置轮动配置

        Args:
            config: 轮动配置
        """
        self.rotation_config = config
        logger.info(f"更新轮动配置：{config}")

    def get_rotation_history(self, limit: int = 10) -> List[Dict]:
        """
        获取轮动历史

        Args:
            limit: 历史记录数量

        Returns:
            List[Dict]: 轮动历史记录
        """
        return self.rotation_history[-limit:]

    def get_strategy_performance(self) -> Dict[str, Dict]:
        """
        获取策略性能

        Returns:
            Dict[str, Dict]: 策略性能字典
        """
        return self.strategy_performance


def create_strategy_manager() -> StrategyManager:
    """创建策略管理器实例"""
    return StrategyManager()
