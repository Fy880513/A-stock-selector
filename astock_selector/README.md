# A 股选股系统 (A-Stock Selector)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

一个基于基本面、热点、资金流入和技术指标的综合 A 股选股系统，整合多种策略模式，支持从稳健到激进的多种投资风格。

> **免责声明**：本系统仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。

---

## 🎯 策略模式

| 模式 | 配置 | 风险 | 适用人群 |
|------|------|------|----------|
| **conservative** | 综合评分 100% | ⭐低 | 稳健型、中线 |
| **balanced** | 综合 50% + 龙头 30% + ML 20% | ⭐⭐中 | 平衡型 |
| **aggressive** | 龙头 60% + 涨停 40% | ⭐⭐⭐高 | 激进型、短线 |
| **all_in** | 全策略融合 | ⭐⭐⭐⭐中高 | 全面分析 |

## 🚀 快速开始

### 1. 安装依赖

```bash
cd astock_selector
pip install -r requirements.txt
```

### 2. 配置数据源

注册 Tushare 获取 Token: https://tushare.pro/

创建 `.env` 文件：
```bash
TUSHARE_TOKEN=your_token_here
```

### 3. 运行选股

```bash
# 稳健型选股
python main.py --strategy conservative --top-n 10

# 龙头战法
python main.py --dragon --board 人工智能

# 涨停分析
python main.py --limit-up

# 龙虎榜席位
python main.py --seat

# 持仓分析（需登录同花顺）
python main.py --position --suggestion
```

---

## 📊 核心功能

### 多维度选股
- **基本面 (25%)**：PE/PEG、ROE、营收/利润增长
- **技术面 (35%)**：MA、MACD、KDJ、RSI、布林带
- **资金面 (25%)**：主力净流入、北向资金、龙虎榜
- **热点面 (15%)**：板块热度、新闻情绪、概念题材

### 特色策略
- **龙头战法**：识别板块龙头，挖掘龙二龙三
- **涨停分析**：封单强度、连板概率预测
- **龙虎榜席位**：机构/游资/北向资金追踪
- **ML 选股**：LightGBM/RandomForest 机器学习模型
- **舆情分析**：BERT 深度学习情绪分析（增强版）

### 交易辅助
- **智能止损止盈**：自动计算止损/止盈位
- **持仓分析**：接入同花顺 API，实时分析持仓
- **历史回测**：验证策略有效性
- **选股追踪**：记录选股表现

---

## 📁 项目结构

```
astock_selector/
├── config/             # 配置文件
│   ├── settings.py    # 系统配置
│   └── trading_config.py  # 交易配置
├── data/              # 数据层
│   ├── fetcher.py     # 统一数据接口
│   ├── tushare_api.py # Tushare 接口
│   └── akshare_api.py # AKShare 接口
├── factors/           # 因子计算
│   ├── fundamentals.py  # 基本面因子
│   ├── technicals.py    # 技术面因子
│   ├── capital_flow.py  # 资金面因子
│   ├── hotspots.py      # 热点因子
│   └── news_sentiment.py  # 舆情情绪分析（增强版）
├── strategies/        # 策略层
│   ├── dragon_strategy.py   # 龙头战法
│   ├── limit_up.py          # 涨停分析
│   └── seat_analysis.py     # 龙虎榜席位
├── ml_models/         # ML 模型
├── selector/          # 选股引擎
│   ├── screener.py    # 选股器
│   ├── scorer.py      # 评分器
│   └── strategy_manager.py  # 策略管理器
├── position/          # 持仓分析
├── backtest/          # 回测模块
├── report/            # 报告生成
├── web/               # Web 界面 (Streamlit)
├── main.py            # 主入口
└── requirements.txt   # 依赖列表
```

---

## 📖 使用文档

| 文档 | 说明 |
|------|------|
| [QUICKSTART.md](QUICKSTART.md) | 快速入门指南 |
| [STRATEGY_MODES.md](STRATEGY_MODES.md) | 策略模式详解 |
| [DRAGON_STRATEGY.md](DRAGON_STRATEGY.md) | 龙头战法指南 |
| [POSITION_MODULE.md](POSITION_MODULE.md) | 持仓分析模块 |
| [SENTIMENT_ANALYSIS.md](SENTIMENT_ANALYSIS.md) | 舆情情绪分析（增强版） |

---

## 🛠️ 数据源

| 数据 | 来源 | 说明 |
|------|------|------|
| 实时行情 | AKShare | 免费 |
| 基本面数据 | Tushare | 需 Token |
| 资金流向 | AKShare | 免费 |
| 龙虎榜 | AKShare | 免费 |

---

## ⚠️ 风险提示

1. **策略风险**：激进型策略（龙头/涨停）风险高于稳健型
2. **数据延迟**：龙虎榜为盘后数据，ML 模型存在滞后性
3. **止损设置**：建议设置 -5%~-8% 止损线
4. **市场风险**：熊市/震荡市降低仓位

---

## 📝 开发计划

- [x] 实时新闻舆情抓取（NLP 分析）
- [x] BERT 深度学习情绪分析
- [ ] 更多 ML 模型（XGBoost/CatBoost/神经网络）
- [ ] Web 界面优化
- [ ] 策略回测优化器

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 📧 联系方式

如有问题或建议，请提交 Issue。
