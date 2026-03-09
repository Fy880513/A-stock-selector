"""
热点分析因子计算模块

权重：15%
包含板块热度、新闻事件、概念题材、涨停梯队等因子

增强功能:
- 支持 BERT 深度学习情绪分析 (可选)
- 多源新闻聚合集成
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta

from utils.logger import get_logger
from utils.helpers import normalize_score

logger = get_logger(__name__)

# 延迟导入，避免不必要的依赖
try:
    from factors.news_sentiment import (
        EnhancedSentimentAnalyzer,
        create_sentiment_analyzer,
        analyze_stock
    )
    BERT_AVAILABLE = True
except ImportError:
    BERT_AVAILABLE = False
    EnhancedSentimentAnalyzer = None
    create_sentiment_analyzer = None
    analyze_stock = None


# 热门概念关键词（需要根据市场动态更新）
HOT_CONCEPT_KEYWORDS = {
    "AI 人工智能": ["AI", "人工智能", "大模型", "AIGC", "ChatGPT", "机器学习", "深度学习"],
    "芯片半导体": ["芯片", "半导体", "集成电路", "光刻机", "EDA", "存储芯片"],
    "新能源": ["新能源", "光伏", "风电", "储能", "氢能", "电池"],
    "新能源汽车": ["新能源汽车", "锂电池", "宁德时代", "比亚迪", "充电桩"],
    "医药生物": ["医药", "生物", "疫苗", "创新药", "医疗器械", "CXO"],
    "数字经济": ["数字经济", "数据要素", "信创", "国产替代", "信创"],
    "5G 通信": ["5G", "通信", "基站", "光模块", "卫星互联网"],
    "消费电子": ["消费电子", "苹果", "华为", "VR", "AR", "元宇宙"],
    "机器人": ["机器人", "人形机器人", "工业自动化", "减速器"],
    "国防军工": ["军工", "航天", "航空", "船舶", "兵器"],
    "金融科技": ["金融科技", "数字货币", "区块链", "数字货币"],
    "资源周期": ["资源", "有色", "煤炭", "石油", "黄金", "稀土"],
    "大消费": ["消费", "白酒", "食品", "零售", "旅游", "酒店"],
    "房地产": ["房地产", "物业", "建材", "家居"],
    "中特估": ["中特估", "央企", "国企", "中字头"],
}


class SentimentAnalyzer:
    """舆情情绪分析器"""

    def __init__(self, use_enhanced: bool = False, use_gpu: bool = False):
        self.use_enhanced = use_enhanced
        self.use_gpu = use_gpu

        # 如果启用增强版且可用，初始化 BERT 分析器
        if use_enhanced and BERT_AVAILABLE:
            self.enhanced_analyzer = create_sentiment_analyzer(
                use_bert=True,
                use_gpu=use_gpu
            )
        else:
            self.enhanced_analyzer = None

        # 正面情绪词
        self.positive_words = {
            "利好", "增长", "突破", "创新", "签约", "中标", "合作", "重组",
            "扭亏", "预增", "大单", "订单", "扩产", "提价", "畅销", "热销",
            "领先", "第一", "垄断", "稀缺", "唯一", "龙头", "金牌", "强势"
        }

        # 负面情绪词
        self.negative_words = {
            "利空", "下降", "下滑", "亏损", "重组失败", "诉讼", "处罚", "调查",
            "减持", "解禁", "退市", "ST", "违约", "暴雷", "跌停", "暴跌",
            "风险", "警示", "年报问询", "关注函", "监管函"
        }

        # 情绪权重
        self.positive_weight = 1.0
        self.negative_weight = 1.2  # 负面情绪影响更大

    def analyze_news_sentiment(self, news_list: List[Dict], ts_code: Optional[str] = None) -> Dict:
        """
        分析新闻情绪

        Args:
            news_list: 新闻列表 [{"title": "", "content": "", "source": ""}]
            ts_code: 股票代码（可选），用于增强版分析

        Returns:
            dict: 情绪分析结果
        """
        # 如果启用增强版且可用，使用 BERT 分析
        if self.use_enhanced and self.enhanced_analyzer and ts_code:
            try:
                # 使用增强版分析器分析个股情绪
                result = self.enhanced_analyzer.analyze_stock_sentiment(
                    ts_code=ts_code,
                    news_limit=len(news_list) if news_list else 10
                )
                return {
                    "news_count": result.get("news_count", 0),
                    "positive_count": int(result.get("positive_ratio", 0.5) * result.get("news_count", 0)),
                    "negative_count": int((1 - result.get("positive_ratio", 0.5)) * result.get("news_count", 0) * 0.3),
                    "neutral_count": int((1 - result.get("positive_ratio", 0.5)) * result.get("news_count", 0) * 0.7),
                    "positive_ratio": result.get("positive_ratio", 0.5),
                    "sentiment_score": result.get("sentiment_score", 50.0),
                    "sentiment_level": result.get("sentiment_level", "中性"),
                    "trend": result.get("trend", "稳定"),
                }
            except Exception as e:
                logger.warning(f"增强版舆情分析失败，降级到基础分析：{e}")
                # 降级到基础分析

        # 基础版分析（原有逻辑）
        if not news_list:
            return {
                "news_count": 0,
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "positive_ratio": 0.5,
                "sentiment_score": 50.0,
                "sentiment_level": "中性",
            }

        positive_count = 0
        negative_count = 0
        neutral_count = 0
        total_score = 0.0

        for news in news_list:
            title = news.get("title", "")
            content = news.get("content", "")
            text = title + " " + content

            # 计算情绪得分
            score = self._calculate_sentiment_score(text)

            if score > 55:
                positive_count += 1
            elif score < 45:
                negative_count += 1
            else:
                neutral_count += 1

            total_score += score

        total = len(news_list)
        avg_score = total_score / total

        # 判断情绪等级
        if avg_score >= 70:
            level = "强烈看好"
        elif avg_score >= 60:
            level = "看好"
        elif avg_score >= 40:
            level = "中性"
        elif avg_score >= 30:
            level = "看空"
        else:
            level = "强烈看空"

        return {
            "news_count": total,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "positive_ratio": positive_count / total,
            "sentiment_score": avg_score,
            "sentiment_level": level,
        }

    def _calculate_sentiment_score(self, text: str) -> float:
        """
        计算单条文本情绪得分

        Args:
            text: 文本内容

        Returns:
            float: 情绪得分 0-100
        """
        score = 50.0  # 基准分

        # 统计正面词
        for word in self.positive_words:
            if word in text:
                score += 5 * self.positive_weight

        # 统计负面词
        for word in self.negative_words:
            if word in text:
                score -= 5 * self.negative_weight

        return min(100, max(0, score))

    def stock_bar_sentiment(self, bar_posts: List[Dict]) -> Dict:
        """
        分析股吧情绪

        Args:
            bar_posts: 股吧帖子列表 [{"title": "", "content": "", "reply_count": 0}]

        Returns:
            dict: 股吧情绪分析结果
        """
        if not bar_posts:
            return {
                "post_count": 0,
                "sentiment_score": 50.0,
                "hot_level": "低",
                "bull_bear_ratio": 1.0,
            }

        # 热度分析
        total_replies = sum(p.get("reply_count", 0) for p in bar_posts)
        if len(bar_posts) >= 20 or total_replies >= 500:
            hot_level = "高"
        elif len(bar_posts) >= 10 or total_replies >= 200:
            hot_level = "中"
        else:
            hot_level = "低"

        # 情绪分析
        bull_count = 0
        bear_count = 0

        for post in bar_posts:
            text = post.get("title", "") + " " + post.get("content", "")
            score = self._calculate_sentiment_score(text)

            if score > 55:
                bull_count += 1
            elif score < 45:
                bear_count += 1

        total = bull_count + bear_count
        bull_bear_ratio = bull_count / bear_count if bear_count > 0 else float('inf')

        # 股吧情绪得分（考虑热度加权）
        if total > 0:
            base_score = 50 + (bull_count - bear_count) / total * 25
            hot_multiplier = 1.2 if hot_level == "高" else 1.0
            sentiment_score = min(100, max(0, base_score * hot_multiplier))
        else:
            sentiment_score = 50.0

        return {
            "post_count": len(bar_posts),
            "sentiment_score": sentiment_score,
            "hot_level": hot_level,
            "bull_bear_ratio": bull_bear_ratio if bull_bear_ratio != float('inf') else 999,
        }

    def analyze_hot_topic(self, topic: str, mention_count: int, trend: str = "up") -> float:
        """
        分析热点话题情绪

        Args:
            topic: 话题名称
            mention_count: 提及次数
            trend: 趋势 (up/down/flat)

        Returns:
            float: 话题热度得分
        """
        base_score = 50.0

        # 提及次数
        if mention_count >= 100:
            base_score += 25
        elif mention_count >= 50:
            base_score += 20
        elif mention_count >= 20:
            base_score += 15
        elif mention_count >= 10:
            base_score += 10

        # 趋势
        if trend == "up":
            base_score += 15
        elif trend == "flat":
            base_score += 5

        # 是否属于核心热点
        if topic in HOT_CONCEPT_KEYWORDS:
            base_score += 10

        return min(100, max(0, base_score))


# 更新 HotspotFactor 类，增加舆情分析
class HotspotFactor:
    """热点分析因子计算器"""

    def __init__(self, use_enhanced: bool = False, use_gpu: bool = False):
        self.concept_keywords = HOT_CONCEPT_KEYWORDS
        self.sentiment_analyzer = SentimentAnalyzer(
            use_enhanced=use_enhanced,
            use_gpu=use_gpu
        )

    def score_industry_heat(
        self,
        industry_change_1d: float,
        industry_change_5d: float,
        industry_rank_5d: int,
        total_industries: int,
    ) -> float:
        """
        行业热度得分

        Args:
            industry_change_1d: 行业当日涨跌幅
            industry_change_5d: 行业 5 日涨跌幅
            industry_rank_5d: 行业 5 日涨幅排名
            total_industries: 行业总数

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 当日表现
        if industry_change_1d > 3:
            score += 15
        elif industry_change_1d > 1:
            score += 10
        elif industry_change_1d > 0:
            score += 5
        elif industry_change_1d < -2:
            score -= 10

        # 5 日表现（更重要）
        if industry_change_5d > 10:
            score += 25
        elif industry_change_5d > 5:
            score += 20
        elif industry_change_5d > 0:
            score += 10
        elif industry_change_5d < -5:
            score -= 10

        # 排名
        if total_industries > 0:
            rank_percent = industry_rank_5d / total_industries
            if rank_percent < 0.1:  # 前 10%
                score += 20
            elif rank_percent < 0.2:
                score += 15
            elif rank_percent < 0.3:
                score += 10

        return min(100, max(0, score))

    def score_concept_heat(
        self,
        concept_changes: List[float],
        concept_ranks: Optional[List[int]] = None,
    ) -> float:
        """
        概念热度得分

        Args:
            concept_changes: 概念板块涨跌幅列表（所属概念的涨幅）
            concept_ranks: 概念排名

        Returns:
            float: 得分 0-100
        """
        if not concept_changes:
            return 50.0

        score = 50.0

        # 取最好的几个概念
        concept_changes = sorted(concept_changes, reverse=True)[:3]

        # 最强概念的涨幅
        if concept_changes[0] > 5:
            score += 25
        elif concept_changes[0] > 3:
            score += 20
        elif concept_changes[0] > 1:
            score += 10

        # 概念平均表现
        avg_change = sum(concept_changes) / len(concept_changes)
        if avg_change > 3:
            score += 15
        elif avg_change > 1:
            score += 10

        return min(100, max(0, score))

    def score_hot_money(
        self,
        limit_up_count: int,
        limit_up_ratio: float,
        consecutive_limit_up: int,
    ) -> float:
        """
        涨停梯队得分

        Args:
            limit_up_count: 所属板块涨停股数量
            limit_up_ratio: 涨停股占板块比例
            consecutive_limit_up: 连续涨停天数

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 板块涨停数量
        if limit_up_count >= 5:
            score += 25  # 板块强势
        elif limit_up_count >= 3:
            score += 15
        elif limit_up_count >= 1:
            score += 5

        # 涨停比例
        if limit_up_ratio > 0.1:  # 10% 涨停
            score += 20
        elif limit_up_ratio > 0.05:
            score += 10

        # 连板
        if consecutive_limit_up >= 3:
            score += 20  # 龙头相
        elif consecutive_limit_up >= 2:
            score += 10

        return min(100, max(0, score))

    def score_news_sentiment(
        self,
        news_count: int,
        positive_ratio: float,
        has_major_news: bool = False,
        sentiment_score: Optional[float] = None,
    ) -> float:
        """
        新闻情绪得分（增强版）

        Args:
            news_count: 相关新闻数量
            positive_ratio: 正面新闻比例
            has_major_news: 是否有重大新闻
            sentiment_score: 舆情分析器计算的情绪得分（0-100）

        Returns:
            float: 得分 0-100
        """
        score = 50.0

        # 如果有舆情分析器得分，优先使用
        if sentiment_score is not None:
            # 直接映射舆情得分
            score = sentiment_score
        else:
            # 使用原有逻辑
            # 新闻数量（代表关注度）
            if news_count >= 10:
                score += 10
            elif news_count >= 5:
                score += 5

            # 正面新闻比例
            if positive_ratio > 0.8:
                score += 25
            elif positive_ratio > 0.6:
                score += 15
            elif positive_ratio > 0.4:
                score += 5
            elif positive_ratio < 0.2:
                score -= 15

        # 重大新闻加分
        if has_major_news:
            score += 15

        return min(100, max(0, score))

    def score_policy_support(
        self,
        has_policy_news: bool,
        policy_level: str = "local",
    ) -> float:
        """
        政策支持得分

        Args:
            has_policy_news: 是否有相关政策新闻
            policy_level: 政策级别 (national/provincial/local)

        Returns:
            float: 得分 0-100
        """
        if not has_policy_news:
            return 50.0

        if policy_level == "national":
            return 90.0  # 国家级政策
        elif policy_level == "provincial":
            return 70.0  # 省级政策
        else:
            return 60.0  # 地方政策

    def match_concepts(self, stock_name: str, stock_industry: str) -> List[str]:
        """
        匹配股票所属热点概念

        Args:
            stock_name: 股票名称
            stock_industry: 所属行业

        Returns:
            List[str]: 匹配的概念列表
        """
        matched_concepts = []
        text = stock_name + stock_industry

        for concept, keywords in self.concept_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    matched_concepts.append(concept)
                    break

        return matched_concepts

    def is_hot_concept(self, concept: str, hot_concepts: Set[str]) -> bool:
        """判断是否属于当前热点概念"""
        return concept in hot_concepts

    def calculate_composite_score(
        self,
        industry_change_1d: float = 0,
        industry_change_5d: float = 0,
        industry_rank_5d: int = 0,
        total_industries: int = 30,
        concept_changes: Optional[List[float]] = None,
        limit_up_count: int = 0,
        limit_up_ratio: float = 0,
        consecutive_limit_up: int = 0,
        news_count: int = 0,
        news_positive_ratio: float = 0.5,
        has_policy_news: bool = False,
        policy_level: str = "local",
        is_main_theme: bool = False,
    ) -> Dict[str, float]:
        """
        计算热点综合得分

        Returns:
            dict: 各维度得分和综合得分
        """
        # 各维度得分
        industry_score = self.score_industry_heat(
            industry_change_1d,
            industry_change_5d,
            industry_rank_5d,
            total_industries,
        )

        concept_score = self.score_concept_heat(
            concept_changes or [],
        )

        hot_money_score = self.score_hot_money(
            limit_up_count,
            limit_up_ratio,
            consecutive_limit_up,
        )

        news_score = self.score_news_sentiment(
            news_count,
            news_positive_ratio,
        )

        policy_score = self.score_policy_support(
            has_policy_news,
            policy_level,
        )

        # 综合得分（行业 25% + 概念 25% + 资金 25% + 新闻 15% + 政策 10%）
        # 如果是市场主线题材，额外加分
        composite = (
            industry_score * 0.25 +
            concept_score * 0.25 +
            hot_money_score * 0.25 +
            news_score * 0.15 +
            policy_score * 0.10
        )

        if is_main_theme:
            composite = min(100, composite + 15)

        return {
            "industry_score": industry_score,
            "concept_score": concept_score,
            "hot_money_score": hot_money_score,
            "news_score": news_score,
            "policy_score": policy_score,
            "hotspot_score": composite,
        }


def calculate_hotspot_score(
    industry_change_1d: float = 0,
    industry_change_5d: float = 0,
    industry_rank_5d: int = 0,
    total_industries: int = 30,
    concept_changes: Optional[List[float]] = None,
    limit_up_count: int = 0,
    limit_up_ratio: float = 0,
    consecutive_limit_up: int = 0,
    news_count: int = 0,
    news_positive_ratio: float = 0.5,
    has_policy_news: bool = False,
    policy_level: str = "local",
    is_main_theme: bool = False,
) -> Dict[str, float]:
    """计算热点综合得分（便捷函数）"""
    factor = HotspotFactor()
    return factor.calculate_composite_score(
        industry_change_1d,
        industry_change_5d,
        industry_rank_5d,
        total_industries,
        concept_changes,
        limit_up_count,
        limit_up_ratio,
        consecutive_limit_up,
        news_count,
        news_positive_ratio,
        has_policy_news,
        policy_level,
        is_main_theme,
    )


def calculate_hotspot_score_enhanced(
    ts_code: str,
    industry_change_1d: float = 0,
    industry_change_5d: float = 0,
    industry_rank_5d: int = 0,
    total_industries: int = 30,
    concept_changes: Optional[List[float]] = None,
    limit_up_count: int = 0,
    limit_up_ratio: float = 0,
    consecutive_limit_up: int = 0,
    has_policy_news: bool = False,
    policy_level: str = "local",
    is_main_theme: bool = False,
    use_bert: bool = True,
    use_gpu: bool = False,
) -> Dict[str, float]:
    """
    计算热点综合得分（增强版，使用 BERT 舆情分析）

    Args:
        ts_code: 股票代码
        use_bert: 是否使用 BERT 深度学习模型
        use_gpu: 是否使用 GPU 加速

    Returns:
        dict: 各维度得分和综合得分
    """
    factor = HotspotFactor(use_enhanced=use_bert, use_gpu=use_gpu)

    # 如果使用增强版，直接通过股票代码获取舆情得分
    sentiment_result = None
    news_count = 0
    news_positive_ratio = 0.5

    if use_bert and BERT_AVAILABLE:
        try:
            sentiment_result = analyze_stock(ts_code, use_bert=True)
            news_count = sentiment_result.get("news_count", 0)
            news_positive_ratio = sentiment_result.get("positive_ratio", 0.5)
        except Exception as e:
            logger.warning(f"BERT 舆情分析失败：{e}，使用基础分析")

    return factor.calculate_composite_score(
        industry_change_1d,
        industry_change_5d,
        industry_rank_5d,
        total_industries,
        concept_changes,
        limit_up_count,
        limit_up_ratio,
        consecutive_limit_up,
        news_count,
        news_positive_ratio,
        has_policy_news,
        policy_level,
        is_main_theme,
        sentiment_score=sentiment_result.get("sentiment_score") if sentiment_result else None,
    )


def analyze_stock_sentiment_enhanced(
    ts_code: str,
    use_bert: bool = True,
    use_gpu: bool = False,
) -> Dict:
    """
    直接使用增强版舆情分析器分析个股情绪

    Args:
        ts_code: 股票代码
        use_bert: 是否使用 BERT 深度学习模型
        use_gpu: 是否使用 GPU 加速

    Returns:
        dict: 情绪分析结果
    """
    if not BERT_AVAILABLE:
        logger.warning("增强版舆情分析模块不可用，请安装依赖：pip install transformers torch aiohttp")
        return {"error": "BERT module not available"}

    try:
        analyzer = create_sentiment_analyzer(use_bert=use_bert, use_gpu=use_gpu)
        return analyzer.analyze_stock_sentiment(ts_code=ts_code)
    except Exception as e:
        logger.error(f"舆情分析失败：{e}")
        return {"error": str(e)}
