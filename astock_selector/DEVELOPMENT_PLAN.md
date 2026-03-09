# A 股选股系统 - 开发计划

本文档详细规划了 A 股选股系统的后续开发方向，包括功能描述、技术方案和优先级。

---

## Phase 1: ML 模型增强 (优先级：高)

### 1.1 XGBoost/CatBoost 模型

**目标**: 扩展现有 ML 模型，增加梯度提升树模型

**技术方案**:
```python
# ml_models/gradient_boosting.py

class GBStockPredictor:
    """梯度提升树预测器"""

    def __init__(self, model_type: str = "xgboost"):
        self.model_type = model_type
        if model_type == "xgboost":
            import xgboost as xgb
            self.model = xgb.XGBRegressor(
                n_estimators=500,
                max_depth=6,
                learning_rate=0.01,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42
            )
        elif model_type == "catboost":
            from catboost import CatBoostRegressor
            self.model = CatBoostRegressor(
                iterations=500,
                depth=6,
                learning_rate=0.01,
                loss_function='RMSE',
                verbose=False
            )

    def train(self, X_train, y_train, X_val, y_val):
        """训练模型"""
        pass

    def predict(self, features) -> np.ndarray:
        """预测"""
        pass
```

**集成方式**:
- 与现有 LightGBM 模型组成 Ensemble
- 加权平均多个模型预测结果
- 使用 Stacking 方法融合

**预计工作量**: 2-3 天

---

### 1.2 LSTM 时序预测

**目标**: 使用深度学习捕捉股价时序特征

**技术方案**:
```python
# ml_models/lstm_predictor.py

import torch
import torch.nn as nn

class LSTMStockPredictor(nn.Module):
    """LSTM 股价预测模型"""

    def __init__(self, input_size=60, hidden_size=128, num_layers=2):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2
        )
        self.fc1 = nn.Linear(hidden_size, 64)
        self.fc2 = nn.Linear(64, 1)  # 预测收益率
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)

    def forward(self, x):
        # x: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)
        out = lstm_out[:, -1, :]  # 取最后一个时间步
        out = self.dropout(self.relu(self.fc1(out)))
        out = self.fc2(out)
        return out

    def predict_return(self, price_sequence) -> float:
        """预测未来收益率"""
        pass
```

**特征输入**:
- 过去 60 天的收盘价、成交量
- 技术指标序列 (MACD, RSI, KDJ)
- 市场指数序列

**训练目标**: 预测未来 5 日/10 日收益率

**预计工作量**: 4-5 天

---

### 1.3 模型融合框架

**目标**: 整合多个模型预测结果

**技术方案**:
```python
# ml_models/ensemble.py

class EnsemblePredictor:
    """模型融合预测器"""

    def __init__(self):
        self.models = {
            'lightgbm': load_model('lightgbm'),
            'xgboost': load_model('xgboost'),
            'catboost': load_model('catboost'),
            'lstm': load_model('lstm'),
            'random_forest': load_model('rf')
        }
        self.weights = {
            'lightgbm': 0.25,
            'xgboost': 0.20,
            'catboost': 0.20,
            'lstm': 0.20,
            'random_forest': 0.15
        }

    def predict(self, features) -> Dict:
        """
        融合预测

        Returns:
            {
                'ensemble_score': 85.5,
                'individual_scores': {...},
                'confidence': '高',
                'model_disagreement': 0.15  # 模型分歧度
            }
        """
        predictions = {}
        for name, model in self.models.items():
            predictions[name] = model.predict(features)

        # 加权平均
        ensemble_score = sum(
            predictions[name] * self.weights[name]
            for name in predictions
        )

        # 计算模型分歧度 (标准差)
        disagreement = np.std(list(predictions.values()))

        return {
            'ensemble_score': ensemble_score,
            'individual_scores': predictions,
            'confidence': self._get_confidence(disagreement),
            'model_disagreement': disagreement
        }
```

**预计工作量**: 2 天

---

## Phase 2: 资金分配优化 (优先级：高)

### 2.1 Kelly 公式仓位管理

**目标**: 基于胜率和盈亏比计算最优仓位

**技术方案**:
```python
# position/kelly_position.py

class KellyPositionManager:
    """Kelly 公式仓位管理器"""

    def __init__(self, max_position_ratio: float = 0.25):
        self.max_position_ratio = max_position_ratio  # 单只股票最大仓位

    def calculate_kelly_fraction(
        self,
        win_rate: float,
        profit_loss_ratio: float,
        confidence: float = 1.0
    ) -> float:
        """
        计算 Kelly 仓位

        Args:
            win_rate: 胜率 (0-1)
            profit_loss_ratio: 盈亏比
            confidence: 置信度折扣 (0-1)

        Returns:
            float: 建议仓位比例
        """
        # Kelly 公式：f = (p * b - q) / b
        # p = 胜率，q = 1-p, b = 盈亏比
        p = win_rate
        q = 1 - win_rate
        b = profit_loss_ratio

        kelly_fraction = (p * b - q) / b

        # 应用置信度折扣
        kelly_fraction *= confidence

        # 半 Kelly (降低风险)
        kelly_fraction *= 0.5

        # 限制最大仓位
        return min(kelly_fraction, self.max_position_ratio)

    def calculate_portfolio_positions(
        self,
        stocks: List[Dict],
        total_capital: float
    ) -> List[Dict]:
        """
        计算组合中各股票仓位

        Returns:
            包含目标仓位和股数的列表
        """
        positions = []
        remaining_capital = total_capital

        for stock in stocks:
            kelly_frac = self.calculate_kelly_fraction(
                win_rate=stock.get('win_rate', 0.55),
                profit_loss_ratio=stock.get('profit_loss_ratio', 2.0),
                confidence=stock.get('confidence', 0.8)
            )

            target_amount = remaining_capital * kelly_frac
            target_shares = int(target_amount / stock['current_price'] / 100) * 100

            positions.append({
                'ts_code': stock['ts_code'],
                'target_shares': target_shares,
                'target_amount': target_shares * stock['current_price'],
                'kelly_fraction': kelly_frac
            })

            remaining_capital -= target_amount

        return positions
```

**预计工作量**: 1-2 天

---

### 2.2 均值 - 方差模型组合优化

**目标**: 使用现代投资组合理论 (MPT) 优化股票组合

**技术方案**:
```python
# selector/mean_variance.py

import numpy as np
from scipy.optimize import minimize

class MeanVarianceOptimizer:
    """均值 - 方差组合优化器"""

    def __init__(self, risk_free_rate: float = 0.03):
        self.risk_free_rate = risk_free_rate

    def optimize_sharpe(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        max_positions: int = 10
    ) -> np.ndarray:
        """
        最大化夏普比率的权重配置

        Args:
            expected_returns: 预期收益率向量
            cov_matrix: 协方差矩阵
            max_positions: 最大持仓数

        Returns:
            最优权重向量
        """
        n_assets = len(expected_returns)

        # 负夏普比率 (最小化)
        def negative_sharpe(weights):
            port_return = np.sum(expected_returns * weights)
            port_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            return -(port_return - self.risk_free_rate) / port_std

        # 约束条件
        constraints = (
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},  # 权重和为 1
        )

        # 边界 (0 <= weight <= 0.25)
        bounds = tuple((0, 0.25) for _ in range(n_assets))

        # 初始猜测 (等权重)
        init_guess = n_assets * [1. / n_assets]

        result = minimize(
            negative_sharpe,
            init_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x

    def optimize_min_variance(
        self,
        cov_matrix: np.ndarray,
        min_return: float = 0.0
    ) -> np.ndarray:
        """
        最小方差组合

        Returns:
            最优权重向量
        """
        n_assets = cov_matrix.shape[0]

        def portfolio_variance(weights):
            return np.dot(weights.T, np.dot(cov_matrix, weights))

        constraints = (
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': lambda x: np.sum(x * expected_returns) - min_return}
        )

        bounds = tuple((0, 0.25) for _ in range(n_assets))
        init_guess = n_assets * [1. / n_assets]

        result = minimize(
            portfolio_variance,
            init_guess,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x
```

**预计工作量**: 2-3 天

---

## Phase 3: 参数优化 (优先级：中)

### 3.1 贝叶斯优化自动调参

**目标**: 自动优化策略参数，减少人工试错

**技术方案**:
```python
# backtest/bayesian_optimizer.py

from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical

class BayesianStrategyOptimizer:
    """贝叶斯策略优化器"""

    def __init__(self, backtest_engine):
        self.engine = backtest_engine
        self.param_space = [
            Real(0.03, 0.10, name='stop_loss_ratio'),      # 止损率
            Real(0.10, 0.30, name='stop_profit_ratio'),    # 止盈率
            Integer(5, 30, name='holding_period'),         # 持有期
            Real(0.5, 0.9, name='min_score_threshold'),    # 最低得分
            Categorical(['conservative', 'balanced', 'aggressive'], name='strategy')
        ]

    def optimize(
        self,
        start_date: str,
        end_date: str,
        n_calls: int = 50
    ) -> Dict:
        """
        贝叶斯优化

        Returns:
            {
                'best_params': {...},
                'best_score': 1.85,  # 夏普比率
                'optimization_history': [...]
            }
        """
        def objective(params):
            stop_loss, stop_profit, holding, min_score, strategy = params

            result = self.engine.run_backtest(
                start_date=start_date,
                end_date=end_date,
                stop_loss_ratio=stop_loss,
                stop_profit_ratio=stop_profit,
                holding_period=holding,
                min_score=min_score,
                strategy=strategy
            )

            # 最大化夏普比率
            sharpe = result.get('sharpe_ratio', 0)
            return -sharpe  # 最小化负值

        result = gp_minimize(
            objective,
            self.param_space,
            n_calls=n_calls,
            random_state=42
        )

        return {
            'best_params': {
                'stop_loss_ratio': result.x[0],
                'stop_profit_ratio': result.x[1],
                'holding_period': result.x[2],
                'min_score_threshold': result.x[3],
                'strategy': result.x[4]
            },
            'best_score': -result.fun,
            'optimization_history': result.x_iters
        }
```

**预计工作量**: 2-3 天

---

### 3.2 遗传算法策略权重优化

**目标**: 使用遗传算法优化多策略权重配置

**技术方案**:
```python
# backtest/genetic_optimizer.py

import random
from deap import base, creator, tools, algorithms

class GeneticWeightOptimizer:
    """遗传算法权重优化器"""

    def __init__(self, backtest_engine, n_strategies: int = 5):
        self.engine = backtest_engine
        self.n_strategies = n_strategies

        # 创建 DEAP 框架
        creator.create("FitnessMax", base.Fitness, weights=(1.0,))
        creator.create("Individual", list, fitness=creator.FitnessMax)

        self.toolbox = base.Toolbox()
        self._setup_genetic_algorithm()

    def _setup_genetic_algorithm(self):
        """配置遗传算法"""
        # 基因：策略权重 (0-0.5)
        self.toolbox.register(
            "attr_float",
            random.uniform, 0, 0.5
        )

        # 个体：权重向量
        self.toolbox.register(
            "individual",
            tools.initRepeat,
            creator.Individual,
            self.toolbox.attr_float,
            n=self.n_strategies
        )

        # 种群
        self.toolbox.register(
            "population",
            tools.initRepeat,
            list,
            self.toolbox.individual
        )

        # 评估函数
        self.toolbox.register("evaluate", self._evaluate_weights)

        # 遗传操作
        self.toolbox.register(
            "mate",
            tools.cxSimulatedBinary,
            eta=20
        )
        self.toolbox.register(
            "mutate",
            tools.mutPolynomialBounded,
            eta=20,
            low=0,
            up=0.5
        )
        self.toolbox.register(
            "select",
            tools.selNSGA2
        )

    def _evaluate_weights(self, individual) -> tuple:
        """评估权重适应度"""
        # 归一化权重
        weights = np.array(individual)
        weights = weights / weights.sum()

        # 运行回测
        result = self.engine.run_backtest_with_weights(weights)

        # 适应度：夏普比率
        return (result.get('sharpe_ratio', 0),)

    def optimize(
        self,
        n_generations: int = 100,
        population_size: int = 50
    ) -> Dict:
        """
        执行遗传优化

        Returns:
            最优权重配置
        """
        population = self.toolbox.population(n=population_size)

        # 运行 NSGA-II
        algorithms.eaMuPlusLambda(
            population,
            self.toolbox,
            mu=population_size,
            lambda_=population_size,
            ngen=n_generations
        )

        # 获取最优解
        best = tools.selBest(population, k=1)[0]
        weights = np.array(best) / sum(best)

        return {
            'best_weights': weights.tolist(),
            'strategies': ['comprehensive', 'dragon', 'limit_up', 'ml', 'seat']
        }
```

**预计工作量**: 3-4 天

---

## Phase 4: 数据增强 (优先级：中)

### 4.1 实时新闻舆情抓取

**目标**: 实时获取财经新闻并分析情绪

**技术方案**:
```python
# factors/news_sentiment.py

import aiohttp
from transformers import pipeline

class NewsSentimentAnalyzer:
    """新闻情绪分析器"""

    def __init__(self):
        self.sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="bert-base-chinese"
        )
        self.news_sources = [
            "http://api.sina.com.cn/finance/news",
            "http://api.eastmoney.com/news",
            "http://api.10jqka.com.cn/news"
        ]

    async def fetch_news(self, ts_code: str, limit: int = 10) -> List[Dict]:
        """获取股票相关新闻"""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_from_source(session, source, ts_code)
                for source in self.news_sources
            ]
            results = await asyncio.gather(*tasks)
        return results

    def analyze_sentiment(self, news_texts: List[str]) -> Dict:
        """
        分析新闻情绪

        Returns:
            {
                'overall_sentiment': 0.65,  # -1 到 1
                'positive_count': 7,
                'negative_count': 2,
                'neutral_count': 1,
                'keywords': ['业绩增长', '新订单', ...]
            }
        """
        sentiments = self.sentiment_pipeline(news_texts)

        # 转换情绪得分
        scores = []
        for result in sentiments:
            if result['label'] == 'POSITIVE':
                scores.append(result['score'])
            else:
                scores.append(-result['score'])

        return {
            'overall_sentiment': np.mean(scores),
            'positive_count': sum(1 for s in scores if s > 0),
            'negative_count': sum(1 for s in scores if s < 0),
            'neutral_count': sum(1 for s in scores if s == 0)
        }
```

**预计工作量**: 3-4 天

---

### 4.2 板块轮动因子

**目标**: 捕捉板块轮动规律，提前布局热点

**技术方案**:
```python
# factors/sector_rotation.py

class SectorRotationFactor:
    """板块轮动因子"""

    def __init__(self):
        self.sector_momentum = {}
        self.sector_inflows = {}

    def calculate_sector_momentum(
        self,
        sector_index: str,
        lookback_days: int = 20
    ) -> float:
        """
        计算板块动量

        Returns:
            动量得分 (-1 到 1)
        """
        # 获取板块指数数据
        index_data = get_sector_index(sector_index, lookback_days)

        # 计算收益率
        returns = index_data['close'].pct_change().mean()

        # 计算相对强弱
        market_returns = get_market_index_returns(lookback_days)
        relative_strength = returns - market_returns

        # 归一化到 -1 到 1
        momentum = np.tanh(relative_strength * 10)

        return momentum

    def calculate_sector_inflows(
        self,
        sector: str,
        lookback_days: int = 5
    ) -> float:
        """
        计算板块资金流入

        Returns:
            资金流入得分
        """
        # 获取板块成分股资金流
        stocks = get_sector_stocks(sector)
        total_inflow = 0

        for stock in stocks:
            inflow = get_stock_capital_inflow(stock, lookback_days)
            total_inflow += inflow

        # 归一化
        inflow_score = total_inflow / len(stocks)

        return inflow_score

    def get_rotation_signals(self) -> List[Dict]:
        """
        获取板块轮动信号

        Returns:
            [
                {
                    'sector': '新能源',
                    'momentum': 0.75,
                    'inflows': 0.60,
                    'signal': '买入',
                    'confidence': '高'
                },
                ...
            ]
        """
        sectors = ['新能源', '半导体', '医药', '消费', '金融', '科技']
        signals = []

        for sector in sectors:
            momentum = self.calculate_sector_momentum(sector)
            inflows = self.calculate_sector_inflows(sector)

            # 综合得分
            composite_score = 0.6 * momentum + 0.4 * inflows

            if composite_score > 0.5:
                signal = '买入'
            elif composite_score < -0.5:
                signal = '卖出'
            else:
                signal = '观望'

            signals.append({
                'sector': sector,
                'momentum': momentum,
                'inflows': inflows,
                'composite_score': composite_score,
                'signal': signal,
                'confidence': self._get_confidence(composite_score)
            })

        # 按得分排序
        signals.sort(key=lambda x: x['composite_score'], reverse=True)

        return signals
```

**预计工作量**: 3-4 天

---

## Phase 5: Web 界面优化 (优先级：低)

### 5.1 Streamlit 界面升级

**目标**: 改善用户体验，增加交互功能

**功能清单**:
- [ ] 实时选股结果展示
- [ ] 回测结果可视化 (权益曲线、回撤图)
- [ ] 策略对比分析
- [ ] 持仓监控面板
- [ ] 风险预警通知

**技术方案**:
```python
# web/streamlit_app.py (增强版)

import streamlit as st
import plotly.graph_objects as go

def render_backtest_chart(equity_curve, benchmark_curve):
    """绘制回测权益曲线"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=equity_curve.index,
        y=equity_curve.values,
        name='策略收益',
        line=dict(color='red', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=benchmark_curve.index,
        y=benchmark_curve.values,
        name='基准收益',
        line=dict(color='gray', width=1, dash='dash')
    ))

    fig.update_layout(
        title='回测权益曲线',
        xaxis_title='日期',
        yaxis_title='累计收益',
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

def render_holdings_pie(positions):
    """绘制持仓饼图"""
    fig = go.Figure(data=[go.Pie(
        labels=[p['stock_name'] for p in positions],
        values=[p['position_ratio'] for p in positions],
        hole=0.3
    )])

    fig.update_layout(title='持仓分布')
    st.plotly_chart(fig, use_container_width=True)
```

**预计工作量**: 5-7 天

---

## Phase 6: 系统架构优化 (优先级：低)

### 6.1 数据库支持

**目标**: 使用 PostgreSQL/MySQL 替代 SQLite，支持高并发

**技术方案**:
```python
# data/database.py

from sqlalchemy import create_engine, Column, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class StockSelection(Base):
    __tablename__ = 'stock_selections'

    id = Column(String, primary_key=True)
    ts_code = Column(String, index=True)
    select_date = Column(DateTime, index=True)
    total_score = Column(Float)
    # ...

class SelectionDatabase:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def save_selection(self, result: Dict):
        session = self.Session()
        try:
            # 保存选股结果
            pass
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            session.close()
```

**预计工作量**: 2-3 天

---

### 6.2 任务调度系统

**目标**: 定时执行选股、回测等任务

**技术方案**:
```python
# scheduler/enhanced_scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

class EnhancedScheduler:
    """增强任务调度器"""

    def __init__(self):
        self.scheduler = BlockingScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """配置定时任务"""
        # 每日盘前选股 (交易日 9:00)
        self.scheduler.add_job(
            self._run_daily_selection,
            CronTrigger(hour=9, minute=0, day_of_week='mon-fri')
        )

        # 每日收盘后更新数据 (15:30)
        self.scheduler.add_job(
            self._update_market_data,
            CronTrigger(hour=15, minute=30, day_of_week='mon-fri')
        )

        # 每周策略评估 (周日 20:00)
        self.scheduler.add_job(
            self._weekly_strategy_review,
            CronTrigger(hour=20, minute=0, day_of_week='sun')
        )

        # 每月再平衡 (每月第一个交易日 9:00)
        self.scheduler.add_job(
            self._monthly_rebalance,
            CronTrigger(hour=9, minute=0, day=1)
        )

    def start(self):
        """启动调度器"""
        print("启动任务调度器...")
        self.scheduler.start()
```

**预计工作量**: 2-3 天

---

## 开发优先级总结

| 优先级 | 功能 | 预计工作量 | 价值 |
|--------|------|------------|------|
| **P0** | XGBoost/CatBoost 模型 | 2-3 天 | ⭐⭐⭐⭐ |
| **P0** | Kelly 公式仓位管理 | 1-2 天 | ⭐⭐⭐⭐ |
| **P1** | LSTM 时序预测 | 4-5 天 | ⭐⭐⭐⭐ |
| **P1** | 模型融合框架 | 2 天 | ⭐⭐⭐⭐ |
| **P1** | 均值 - 方差优化 | 2-3 天 | ⭐⭐⭐ |
| **P2** | 贝叶斯优化调参 | 2-3 天 | ⭐⭐⭐ |
| **P2** | 遗传算法权重优化 | 3-4 天 | ⭐⭐⭐ |
| **P2** | 实时新闻舆情 | 3-4 天 | ⭐⭐⭐ |
| **P2** | 板块轮动因子 | 3-4 天 | ⭐⭐⭐ |
| **P3** | Streamlit 界面升级 | 5-7 天 | ⭐⭐ |
| **P3** | 数据库支持 | 2-3 天 | ⭐⭐ |
| **P3** | 任务调度系统 | 2-3 天 | ⭐⭐ |

**总计工作量**: 约 35-45 天

---

## 里程碑

### Milestone 1 (Q2 2026)
- [x] 策略轮动系统
- [ ] ML 模型增强 (XGBoost/CatBoost)
- [ ] Kelly 公式仓位管理

### Milestone 2 (Q3 2026)
- [ ] LSTM 时序预测
- [ ] 模型融合框架
- [ ] 均值 - 方差优化

### Milestone 3 (Q4 2026)
- [ ] 参数优化系统
- [ ] 实时新闻舆情
- [ ] 板块轮动因子

### Milestone 4 (Q1 2027)
- [ ] Web 界面升级
- [ ] 数据库支持
- [ ] 任务调度系统

---

**最后更新**: 2026-03-10
