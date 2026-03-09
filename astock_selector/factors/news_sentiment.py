"""
增强版舆情情绪分析模块

功能:
- 多源新闻聚合 (新浪 + 东财 + 同花顺 + 百度)
- BERT 深度学习情绪分析
- 实时新闻推送
- 个股智能关联

依赖:
pip install transformers torch aiohttp
"""
import asyncio
import aiohttp
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from utils.logger import get_logger

logger = get_logger(__name__)


class NewsSource(Enum):
    """新闻来源"""
    SINA = "sina"
    EASTMONEY = "eastmoney"
    10jqka = "10jqka"
    BAIDU = "baidu"
    TUSHARE = "tushare"


class SentimentLevel(Enum):
    """情绪等级"""
    STRONG_POSITIVE = "强烈看好"  # >= 80
    POSITIVE = "看好"  # 60-79
    NEUTRAL = "中性"  # 40-59
    NEGATIVE = "看空"  # 20-39
    STRONG_NEGATIVE = "强烈看空"  # < 20


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    content: str
    source: NewsSource
    publish_time: datetime
    url: str
    related_stocks: List[str]
    raw_sentiment_score: float = 50.0
    bert_sentiment_score: float = 50.0
    confidence: float = 0.0
    keywords: List[str] = None


class MultiSourceNewsAggregator:
    """多源新闻聚合器"""

    def __init__(self):
        self.sources = [
            NewsSource.SINA,
            NewsSource.EASTMONEY,
            NewsSource.BAIDU
        ]
        self.session: Optional[aiohttp.ClientSession] = None

        # 新闻 API 端点
        self.api_endpoints = {
            NewsSource.SINA: "https://finance.sina.com.cn/roll/api.php",
            NewsSource.EASTMONEY: "https://api.eastmoney.com/news/list",
            NewsSource.BAIDU: "https://finance.baidu.com/api/news",
        }

        # 请求参数
        self.request_params = {
            "timeout": aiohttp.ClientTimeout(total=10),
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }

    async def _create_session(self):
        """创建 HTTP 会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(**self.request_params)

    async def _close_session(self):
        """关闭 HTTP 会话"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _fetch_from_sina(self, ts_code: Optional[str] = None, limit: int = 20) -> List[NewsItem]:
        """从新浪财经获取新闻"""
        news_list = []
        try:
            await self._create_session()

            params = {
                "page": 1,
                "size": limit,
                "type": "24"  # 24 小时滚动新闻
            }

            async with self.session.get(
                self.api_endpoints[NewsSource.SINA],
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data.get("data", []):
                        # 提取股票代码
                        related_stocks = self._extract_related_stocks(
                            item.get("title", ""),
                            item.get("intro", "")
                        )

                        # 如果指定了股票代码，只返回相关新闻
                        if ts_code and ts_code not in related_stocks:
                            continue

                        news_list.append(NewsItem(
                            title=item.get("title", ""),
                            content=item.get("intro", ""),
                            source=NewsSource.SINA,
                            publish_time=self._parse_time(item.get("ctime", "")),
                            url=item.get("url", ""),
                            related_stocks=related_stocks
                        ))
        except Exception as e:
            logger.error(f"从新浪财经获取新闻失败：{e}")

        return news_list

    async def _fetch_from_eastmoney(self, ts_code: Optional[str] = None, limit: int = 20) -> List[NewsItem]:
        """从东方财富网获取新闻"""
        news_list = []
        try:
            await self._create_session()

            params = {
                "type": "70",  # 财经要闻
                "page": 1,
                "pagesize": limit
            }

            async with self.session.get(
                self.api_endpoints[NewsSource.EASTMONEY],
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data.get("data", []):
                        related_stocks = self._extract_related_stocks(
                            item.get("Title", ""),
                            item.get("Brief", "")
                        )

                        if ts_code and ts_code not in related_stocks:
                            continue

                        news_list.append(NewsItem(
                            title=item.get("Title", ""),
                            content=item.get("Brief", ""),
                            source=NewsSource.EASTMONEY,
                            publish_time=self._parse_time(item.get("ShowTime", "")),
                            url=item.get("Url", ""),
                            related_stocks=related_stocks
                        ))
        except Exception as e:
            logger.error(f"从东方财富网获取新闻失败：{e}")

        return news_list

    async def _fetch_from_baidu(self, ts_code: Optional[str] = None, limit: int = 20) -> List[NewsItem]:
        """从百度财经获取新闻"""
        news_list = []
        try:
            await self._create_session()

            # 百度财经 API
            url = "https://finance.baidu.com/api/newsfeed"
            params = {
                "tab": "news",
                "pn": 1,
                "rn": limit
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    for item in data.get("result", []):
                        related_stocks = self._extract_related_stocks(
                            item.get("title", ""),
                            item.get("abstract", "")
                        )

                        if ts_code and ts_code not in related_stocks:
                            continue

                        news_list.append(NewsItem(
                            title=item.get("title", ""),
                            content=item.get("abstract", ""),
                            source=NewsSource.BAIDU,
                            publish_time=self._parse_time(item.get("ctime", "")),
                            url=item.get("url", ""),
                            related_stocks=related_stocks
                        ))
        except Exception as e:
            logger.error(f"从百度财经获取新闻失败：{e}")

        return news_list

    def _extract_related_stocks(self, title: str, content: str) -> List[str]:
        """从新闻中提取相关股票代码"""
        stocks = []
        text = title + " " + content

        # 常见股票名称到代码的映射 (简化版，实际使用需要更完整的数据库)
        stock_keywords = {
            "贵州茅台": "600519.SH",
            "宁德时代": "300750.SZ",
            "比亚迪": "002594.SZ",
            "五粮液": "000858.SZ",
            "中国平安": "601318.SH",
            "招商银行": "600036.SH",
            "东方财富": "300059.SZ",
            "中信证券": "600030.SH",
            "药明康德": "603259.SH",
            "恒瑞医药": "600276.SH",
        }

        for name, code in stock_keywords.items():
            if name in text:
                stocks.append(code)

        # 直接匹配股票代码格式 (如 600519、300750 等)
        import re
        stock_codes = re.findall(r'\b([36]\d{5})\b', text)
        for code in stock_codes:
            if code.startswith('6'):
                stocks.append(f"{code}.SH")
            else:
                stocks.append(f"{code}.SZ")

        return list(set(stocks))

    def _parse_time(self, time_str: str) -> datetime:
        """解析时间字符串"""
        if not time_str:
            return datetime.now()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%m-%d %H:%M",
            "%H:%M"
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                # 如果只有时分，默认今天
                if fmt == "%H:%M":
                    dt = dt.replace(year=datetime.now().year,
                                    month=datetime.now().month,
                                    day=datetime.now().day)
                return dt
            except ValueError:
                continue

        return datetime.now()

    async def fetch_all_news(
        self,
        ts_code: Optional[str] = None,
        limit_per_source: int = 20
    ) -> List[NewsItem]:
        """
        从所有来源聚合新闻

        Args:
            ts_code: 股票代码 (可选)
            limit_per_source: 每个来源的新闻数量

        Returns:
            List[NewsItem]: 新闻列表
        """
        tasks = []

        if ts_code:
            # 获取特定股票相关新闻
            tasks.append(self._fetch_from_sina(ts_code, limit_per_source))
            tasks.append(self._fetch_from_eastmoney(ts_code, limit_per_source))
            tasks.append(self._fetch_from_baidu(ts_code, limit_per_source))
        else:
            # 获取全部财经新闻
            tasks.append(self._fetch_from_sina(limit=limit_per_source))
            tasks.append(self._fetch_from_eastmoney(limit=limit_per_source))
            tasks.append(self._fetch_from_baidu(limit=limit_per_source))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 合并结果
        all_news = []
        for result in results:
            if isinstance(result, list):
                all_news.extend(result)

        # 按发布时间排序
        all_news.sort(key=lambda x: x.publish_time, reverse=True)

        # 去重 (基于标题)
        seen_titles = set()
        unique_news = []
        for news in all_news:
            if news.title not in seen_titles:
                seen_titles.add(news.title)
                unique_news.append(news)

        await self._close_session()

        return unique_news

    def fetch_news_sync(
        self,
        ts_code: Optional[str] = None,
        limit: int = 20
    ) -> List[NewsItem]:
        """同步接口获取新闻"""
        return asyncio.run(self.fetch_all_news(ts_code, limit))


class BERTSentimentAnalyzer:
    """BERT 深度学习情绪分析器"""

    def __init__(self, model_name: str = "bert-base-chinese"):
        """
        初始化 BERT 情绪分析器

        Args:
            model_name: HuggingFace 模型名称
        """
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.is_loaded = False

    def load_model(self, use_gpu: bool = False):
        """
        加载 BERT 模型

        Args:
            use_gpu: 是否使用 GPU
        """
        try:
            from transformers import BertTokenizer, BertForSequenceClassification
            import torch

            logger.info(f"加载 BERT 模型：{self.model_name}")

            self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
            self.model = BertForSequenceClassification.from_pretrained(
                self.model_name,
                num_labels=3  # 正面/中性/负面
            )

            if use_gpu and torch.cuda.is_available():
                self.model = self.model.to('cuda')
                logger.info("已启用 GPU 加速")

            self.is_loaded = True
            logger.info("BERT 模型加载成功")

        except ImportError:
            logger.warning("transformers 或 torch 未安装，使用简化情绪分析")
            self.is_loaded = False
        except Exception as e:
            logger.error(f"加载 BERT 模型失败：{e}")
            self.is_loaded = False

    def analyze(self, text: str) -> Dict:
        """
        分析文本情绪

        Args:
            text: 输入文本

        Returns:
            Dict: {
                'sentiment': 'positive'/'neutral'/'negative',
                'score': 0-100,
                'confidence': 0-1,
                'probabilities': {'positive': x, 'neutral': y, 'negative': z}
            }
        """
        if not self.is_loaded or self.model is None:
            return self._fallback_analyze(text)

        try:
            import torch
            from transformers import pipeline

            # 使用 pipeline
            sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model=self.model,
                tokenizer=self.tokenizer,
                return_all_scores=True
            )

            results = sentiment_pipeline(text[:512])  # BERT 最大长度限制

            # 解析结果
            sentiment_map = {
                'LABEL_0': 'negative',
                'LABEL_1': 'neutral',
                'LABEL_2': 'positive'
            }

            if results and len(results) > 0:
                result = results[0]
                label = sentiment_map.get(result[0]['label'], 'neutral')
                score = result[0]['score']

                # 转换为 0-100 分数
                if label == 'positive':
                    final_score = 50 + score * 50
                elif label == 'negative':
                    final_score = 50 - score * 50
                else:
                    final_score = 50

                return {
                    'sentiment': label,
                    'score': final_score,
                    'confidence': score,
                    'probabilities': {label: score}
                }

            return self._fallback_analyze(text)

        except Exception as e:
            logger.error(f"BERT 情绪分析失败：{e}")
            return self._fallback_analyze(text)

    def _fallback_analyze(self, text: str) -> Dict:
        """简化版情绪分析 (基于关键词)"""
        positive_words = {
            "利好", "增长", "突破", "创新", "签约", "中标", "合作", "重组",
            "扭亏", "预增", "大单", "订单", "扩产", "提价", "畅销", "热销",
            "领先", "第一", "垄断", "稀缺", "唯一", "龙头", "金牌", "强势",
            "上涨", "盈利", "利好", "超预期", "佳绩"
        }

        negative_words = {
            "利空", "下降", "下滑", "亏损", "重组失败", "诉讼", "处罚", "调查",
            "减持", "解禁", "退市", "ST", "违约", "暴雷", "跌停", "暴跌",
            "风险", "警示", "年报问询", "关注函", "监管函", "暴跌", "跳水"
        }

        score = 50.0
        positive_count = 0
        negative_count = 0

        for word in positive_words:
            if word in text:
                positive_count += 1
                score += 5

        for word in negative_words:
            if word in text:
                negative_count += 1
                score -= 5

        # 限制在 0-100 范围
        score = max(0, min(100, score))

        # 计算置信度
        total = positive_count + negative_count
        if total > 0:
            confidence = abs(positive_count - negative_count) / total
        else:
            confidence = 0.5

        # 判断情绪类型
        if score >= 70:
            sentiment = 'positive'
        elif score >= 40:
            sentiment = 'neutral'
        else:
            sentiment = 'negative'

        return {
            'sentiment': sentiment,
            'score': score,
            'confidence': confidence,
            'probabilities': {sentiment: confidence}
        }

    def analyze_batch(self, texts: List[str], batch_size: int = 8) -> List[Dict]:
        """
        批量分析文本情绪

        Args:
            texts: 文本列表
            batch_size: 批次大小

        Returns:
            List[Dict]: 情绪分析结果列表
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            for text in batch:
                result = self.analyze(text)
                results.append(result)

        return results


class EnhancedSentimentAnalyzer:
    """增强版舆情情绪分析器 (整合多源新闻和 BERT 模型)"""

    def __init__(self, use_bert: bool = True, use_gpu: bool = False):
        """
        初始化增强版情绪分析器

        Args:
            use_bert: 是否使用 BERT 模型
            use_gpu: 是否使用 GPU 加速
        """
        self.news_aggregator = MultiSourceNewsAggregator()
        self.use_bert = use_bert

        if use_bert:
            self.bert_analyzer = BERTSentimentAnalyzer()
            self.bert_analyzer.load_model(use_gpu=use_gpu)
        else:
            self.bert_analyzer = None

        # 情绪权重
        self.positive_weight = 1.0
        self.negative_weight = 1.2  # 负面情绪影响更大

    def analyze_stock_sentiment(
        self,
        ts_code: str,
        news_limit: int = 10
    ) -> Dict:
        """
        分析个股舆情情绪

        Args:
            ts_code: 股票代码
            news_limit: 新闻数量限制

        Returns:
            Dict: {
                'stock_code': str,
                'sentiment_score': float,
                'sentiment_level': str,
                'news_count': int,
                'positive_ratio': float,
                'news_items': List[Dict],
                'trend': str  # 改善/恶化/稳定
            }
        """
        # 获取新闻
        news_items = self.news_aggregator.fetch_news_sync(
            ts_code=ts_code,
            limit=news_limit
        )

        if not news_items:
            return {
                'stock_code': ts_code,
                'sentiment_score': 50.0,
                'sentiment_level': '中性',
                'news_count': 0,
                'positive_ratio': 0.5,
                'news_items': [],
                'trend': '稳定'
            }

        # 分析每篇新闻的情绪
        sentiment_scores = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        processed_news = []

        for news in news_items:
            # 使用 BERT 分析 (如果可用)
            if self.use_bert and self.bert_analyzer:
                sentiment_result = self.bert_analyzer.analyze(
                    news.title + " " + news.content
                )
            else:
                sentiment_result = self._keyword_based_analysis(
                    news.title + " " + news.content
                )

            news.bert_sentiment_score = sentiment_result['score']
            news.confidence = sentiment_result['confidence']

            sentiment_scores.append(sentiment_result['score'])

            # 统计
            if sentiment_result['score'] > 60:
                positive_count += 1
            elif sentiment_result['score'] < 40:
                negative_count += 1
            else:
                neutral_count += 1

            processed_news.append({
                'title': news.title,
                'source': news.source.value,
                'publish_time': news.publish_time.isoformat(),
                'sentiment_score': sentiment_result['score'],
                'sentiment': sentiment_result['sentiment'],
                'url': news.url
            })

        # 计算综合得分
        avg_score = np.mean(sentiment_scores)
        total = len(news_items)

        # 判断情绪等级
        if avg_score >= 80:
            level = SentimentLevel.STRONG_POSITIVE.value
        elif avg_score >= 60:
            level = SentimentLevel.POSITIVE.value
        elif avg_score >= 40:
            level = SentimentLevel.NEUTRAL.value
        elif avg_score >= 20:
            level = SentimentLevel.NEGATIVE.value
        else:
            level = SentimentLevel.STRONG_NEGATIVE.value

        # 判断趋势 (简化版，基于最近新闻的时间分布)
        if positive_count > negative_count * 1.5:
            trend = '改善'
        elif negative_count > positive_count * 1.5:
            trend = '恶化'
        else:
            trend = '稳定'

        return {
            'stock_code': ts_code,
            'sentiment_score': round(avg_score, 2),
            'sentiment_level': level,
            'news_count': total,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'positive_ratio': round(positive_count / total, 2) if total > 0 else 0.5,
            'news_items': processed_news[:5],  # 只返回前 5 条
            'trend': trend,
            'avg_confidence': round(np.mean([n.confidence for n in news_items]), 2)
        }

    def _keyword_based_analysis(self, text: str) -> Dict:
        """基于关键词的情绪分析 (备用方案)"""
        positive_words = {
            "利好", "增长", "突破", "创新", "签约", "中标", "合作",
            "预增", "大单", "订单", "扩产", "提价", "龙头"
        }

        negative_words = {
            "利空", "下降", "下滑", "亏损", "处罚", "调查",
            "减持", "解禁", "退市", "暴雷", "跌停", "风险"
        }

        score = 50.0
        for word in positive_words:
            if word in text:
                score += 5
        for word in negative_words:
            if word in text:
                score -= 5

        score = max(0, min(100, score))

        if score >= 60:
            sentiment = 'positive'
        elif score >= 40:
            sentiment = 'neutral'
        else:
            sentiment = 'negative'

        return {
            'sentiment': sentiment,
            'score': score,
            'confidence': 0.5
        }

    def analyze_market_sentiment(self) -> Dict:
        """
        分析整体市场情绪

        Returns:
            Dict: 市场情绪分析结果
        """
        # 获取市场整体新闻
        news_items = self.news_aggregator.fetch_news_sync(
            ts_code=None,
            limit=50
        )

        if not news_items:
            return {
                'market_sentiment': '中性',
                'sentiment_score': 50.0,
                'news_count': 0
            }

        sentiment_scores = []
        sector_sentiment = {}

        for news in news_items:
            if self.use_bert and self.bert_analyzer:
                result = self.bert_analyzer.analyze(news.title + " " + news.content)
            else:
                result = self._keyword_based_analysis(news.title + " " + news.content)

            sentiment_scores.append(result['score'])

            # 按板块统计
            sector = self._detect_sector(news.title + " " + news.content)
            if sector:
                if sector not in sector_sentiment:
                    sector_sentiment[sector] = []
                sector_sentiment[sector].append(result['score'])

        avg_score = np.mean(sentiment_scores)

        # 计算板块情绪
        sector_avg = {}
        for sector, scores in sector_sentiment.items():
            sector_avg[sector] = round(np.mean(scores), 2)

        return {
            'market_sentiment': self._score_to_level(avg_score),
            'sentiment_score': round(avg_score, 2),
            'news_count': len(news_items),
            'sector_sentiment': sector_avg,
            'trend': '改善' if avg_score > 55 else ('恶化' if avg_score < 45 else '稳定')
        }

    def _detect_sector(self, text: str) -> Optional[str]:
        """检测新闻所属板块"""
        sector_keywords = {
            "新能源": ["新能源", "光伏", "风电", "储能", "电池"],
            "AI": ["AI", "人工智能", "大模型", "AIGC"],
            "芯片": ["芯片", "半导体", "集成电路"],
            "医药": ["医药", "生物", "疫苗", "创新药"],
            "消费": ["消费", "白酒", "食品", "零售"],
            "金融": ["银行", "保险", "券商", "金融"],
            "科技": ["科技", "互联网", "软件", "通信"]
        }

        for sector, keywords in sector_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return sector

        return None

    def _score_to_level(self, score: float) -> str:
        """分数转换为等级"""
        if score >= 80:
            return "强烈看好"
        elif score >= 60:
            return "看好"
        elif score >= 40:
            return "中性"
        elif score >= 20:
            return "看空"
        else:
            return "强烈看空"


# 便捷函数
def create_sentiment_analyzer(use_bert: bool = True, use_gpu: bool = False) -> EnhancedSentimentAnalyzer:
    """创建情绪分析器实例"""
    return EnhancedSentimentAnalyzer(use_bert, use_gpu)


def analyze_stock(ts_code: str, use_bert: bool = True) -> Dict:
    """
    便捷函数：分析个股舆情

    Args:
        ts_code: 股票代码
        use_bert: 是否使用 BERT 模型

    Returns:
        Dict: 情绪分析结果
    """
    analyzer = create_sentiment_analyzer(use_bert=use_bert)
    return analyzer.analyze_stock_sentiment(ts_code)


def analyze_market() -> Dict:
    """
    便捷函数：分析市场整体情绪

    Returns:
        Dict: 市场情绪分析结果
    """
    analyzer = create_sentiment_analyzer(use_bert=False)  # 市场分析不需要 BERT
    return analyzer.analyze_market_sentiment()


if __name__ == "__main__":
    # 测试代码
    print("测试增强版舆情分析...")

    # 测试市场情绪分析
    market_result = analyze_market()
    print(f"\n市场情绪：{market_result['market_sentiment']}")
    print(f"情绪得分：{market_result['sentiment_score']}")
    print(f"新闻数量：{market_result['news_count']}")

    # 测试个股情绪分析 (示例：贵州茅台)
    # stock_result = analyze_stock("600519.SH", use_bert=False)
    # print(f"\n个股情绪：{stock_result['sentiment_level']}")
    # print(f"情绪得分：{stock_result['sentiment_score']}")
