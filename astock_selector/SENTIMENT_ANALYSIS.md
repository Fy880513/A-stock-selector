# 增强版舆情情绪分析模块

## 功能概述

增强版舆情分析模块提供以下功能：

1. **多源新闻聚合** - 从新浪财经、东方财富、百度财经三个来源聚合新闻
2. **BERT 深度学习情绪分析** - 使用 HuggingFace transformers 进行情绪识别
3. **实时新闻推送** - 异步 HTTP 并发获取最新新闻
4. **个股智能关联** - 自动提取新闻中相关的股票代码

---

## 安装依赖

```bash
pip install transformers torch aiohttp
```

**可选：GPU 加速**

如需使用 GPU 加速 BERT 模型，请安装：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

---

## 使用方法

### 1. 命令行使用

```bash
# 基础版舆情分析（关键词分析）
python main.py --sentiment 600519.SH

# BERT 深度学习分析
python main.py --sentiment 600519.SH --sentiment-bert

# BERT + GPU 加速
python main.py --sentiment 600519.SH --sentiment-bert --sentiment-gpu
```

### 2. Python API 调用

#### 快速分析个股

```python
from factors.hotspots import analyze_stock_sentiment_enhanced

# 基础版（关键词分析）
result = analyze_stock_sentiment_enhanced("600519.SH", use_bert=False)
print(f"情绪得分：{result['sentiment_score']}")
print(f"情绪等级：{result['sentiment_level']}")
print(f"趋势：{result['trend']}")

# BERT 版（深度学习）
result = analyze_stock_sentiment_enhanced("600519.SH", use_bert=True)
print(f"情绪得分：{result['sentiment_score']}")
print(f"情绪等级：{result['sentiment_level']}")
```

#### 直接使用新闻聚合器

```python
from factors.news_sentiment import MultiSourceNewsAggregator

aggregator = MultiSourceNewsAggregator()

# 获取个股相关新闻
news_list = aggregator.fetch_news_sync(ts_code="600519.SH", limit=20)

for news in news_list:
    print(f"[{news.source.value}] {news.title}")
    print(f"发布时间：{news.publish_time}")
    print(f"URL: {news.url}")
    print()
```

#### 直接使用 BERT 分析器

```python
from factors.news_sentiment import BERTSentimentAnalyzer

analyzer = BERTSentimentAnalyzer()
analyzer.load_model(use_gpu=False)  # 或 use_gpu=True

# 分析单条文本
result = analyzer.analyze("贵州茅台发布亮眼财报，净利润大幅增长")
print(f"情绪：{result['sentiment']}")
print(f"得分：{result['score']}")
print(f"置信度：{result['confidence']}")

# 批量分析
texts = ["新闻标题 1", "新闻标题 2", "新闻标题 3"]
results = analyzer.analyze_batch(texts)
for r in results:
    print(f"得分：{r['score']}, 情绪：{r['sentiment']}")
```

#### 完整增强版分析器

```python
from factors.news_sentiment import EnhancedSentimentAnalyzer, create_sentiment_analyzer

# 创建分析器
analyzer = create_sentiment_analyzer(use_bert=True, use_gpu=False)

# 分析个股情绪
result = analyzer.analyze_stock_sentiment("600519.SH", news_limit=10)

print(f"股票：{result['stock_code']}")
print(f"情绪得分：{result['sentiment_score']}")
print(f"情绪等级：{result['sentiment_level']}")
print(f"趋势：{result['trend']}")
print(f"新闻数量：{result['news_count']}")
print(f"正面比例：{result['positive_ratio']:.1%}")
print(f"平均置信度：{result['avg_confidence']}")

# 分析市场整体情绪
market_result = analyzer.analyze_market_sentiment()
print(f"\n市场情绪：{market_result['market_sentiment']}")
print(f"板块情绪：{market_result['sector_sentiment']}")
```

---

## 输出说明

### 情绪得分与等级

| 得分范围 | 情绪等级 | 说明 |
|----------|----------|------|
| >= 80 | 强烈看好 | 重大利好主导 |
| 60-79 | 看好 | 正面消息较多 |
| 40-59 | 中性 | 消息面平淡 |
| 20-39 | 看空 | 负面消息较多 |
| < 20 | 强烈看空 | 重大利空主导 |

### 情绪趋势

- **改善**：正面新闻显著多于负面
- **恶化**：负面新闻显著多于正面
- **稳定**：正面负面基本持平

---

## 技术架构

```
┌─────────────────────────────────────────────────┐
│           EnhancedSentimentAnalyzer             │
│  （增强版舆情分析器）                             │
├─────────────────────────────────────────────────┤
│  ┌───────────────────┐  ┌────────────────────┐ │
│  │ MultiSourceNews   │  │ BERTSentiment      │ │
│  │ Aggregator        │  │ Analyzer           │ │
│  │                   │  │                    │ │
│  │ - 新浪财经        │  │ - BERT 模型         │ │
│  │ - 东方财富        │  │ - 深度学习情绪识别  │ │
│  │ - 百度财经        │  │ - GPU 加速支持      │ │
│  └───────────────────┘  └────────────────────┘ │
└─────────────────────────────────────────────────┘
```

---

## 降级方案

当 BERT 模型不可用时（未安装 transformers 或加载失败），系统会自动降级到关键词分析法：

```python
# 降级逻辑
if not self.is_loaded:
    return self._fallback_analyze(text)  # 关键词分析
```

关键词分析法基于预定义的正面/负面词库进行计分，虽然准确度不如 BERT，但速度快、无需额外依赖。

---

## 性能优化建议

1. **使用 GPU 加速**：BERT 模型在 GPU 上速度提升 5-10 倍
2. **批量分析**：使用 `analyze_batch()` 减少模型加载次数
3. **缓存结果**：对同一股票的重复分析可缓存结果
4. **限制新闻数量**：`news_limit` 参数建议设置为 10-20

---

## 注意事项

1. **网络依赖**：新闻获取需要联网，建议设置合理的超时时间
2. **API 稳定性**：新闻 API 端点可能变化，需定期维护
3. **模型大小**：BERT 模型约 400MB，首次加载较慢
4. **内存占用**：GPU 模式下需要至少 4GB 显存

---

## 示例输出

```bash
$ python main.py --sentiment 600519.SH --sentiment-bert

============================================================
A 股选股系统 - 舆情情绪分析
============================================================
股票代码：600519.SH
分析模式：BERT 深度学习
============================================================

【舆情得分】72.5 / 100
【情绪等级】看好
【情绪趋势】改善

【新闻统计】
  新闻总数：15
  正面比例：73.3%
  正面新闻：11
  中性新闻：3
  负面新闻：1

📈 情绪看好，正面消息较多

============================================================
```

---

## 后续优化方向

- [ ] 增加更多新闻源（同花顺、证券时报等）
- [ ] 使用 FinBERT 等金融领域专用模型
- [ ] 添加新闻重要性评分
- [ ] 实现实时新闻推送通知
- [ ] 结合历史舆情数据做趋势预测
