# A 股选股系统

一个基于基本面、技术面、资金面和热点的综合 A 股选股系统，整合多种策略模式。

## 功能特点

- **9 种策略模式**：从稳健到激进，满足不同投资风格
- **龙头战法**：识别板块龙头，挖掘补涨机会
- **涨停分析**：封单强度、连板概率预测
- **龙虎榜席位**：机构/游资/北向资金追踪
- **ML 选股**：LightGBM/RandomForest 机器学习模型
- **持仓分析**：接入同花顺 API，实时分析持仓

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 配置数据源（创建.env 文件）
echo "TUSHARE_TOKEN=your_token" > .env

# 运行选股
python main.py --strategy balanced --top-n 10
```

## 文档

- [快速入门](QUICKSTART.md)
- [策略模式](STRATEGY_MODES.md)
- [龙头战法](DRAGON_STRATEGY.md)
- [持仓分析](POSITION_MODULE.md)

## 免责声明

本系统仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。
