# 代码优化总结

根据第三方代码审查建议，已完成以下优化：

---

## 1. 策略融合与权重优化

### 1.1 自定义策略权重

**文件**: `selector/strategy_manager.py`

新增 `set_custom_weights()` 方法，支持用户根据市场环境手动调整各策略权重：

```python
manager = create_strategy_manager()

# 自定义权重（自动归一化）
manager.set_custom_weights(
    comprehensive=0.50,  # 综合评分 50%
    dragon=0.30,         # 龙头战法 30%
    limit_up=0.10,       # 涨停板 10%
    ml=0.10,             # ML 选股 10%
)
```

### 1.2 市场环境自适应

新增 `set_market_condition()` 方法，根据市场环境自动调整权重：

| 市场环境 | 配置 | 权重调整 |
|----------|------|----------|
| **牛市** (bull) | 激进 | 龙头 35% + 涨停 20% + 综合 30% |
| **熊市** (bear) | 保守 | 综合 60% + 龙头 15% + 涨停 5% |
| **震荡市** (volatile) | 平衡 | 综合 40% + 龙头 25% + ML 20% |

```python
# 根据市场状态自动调整
manager.set_market_condition("bull")    # 牛市模式
manager.set_market_condition("bear")    # 熊市模式
manager.set_market_condition("volatile") # 震荡市模式
```

### 1.3 选股理由生成

新增 `generate_selection_reasons()` 方法，自动生成每只股票入选理由：

```python
# 输出示例
 reasons = [
    "综合评分优秀 (85.0 分)",
    "板块龙头，连板数高",
    "涨停强度强，封单充足",
    "多策略共振 (3 个策略推荐)"
]
```

---

## 2. 风控与资金管理增强

### 2.1 动态止损

**文件**: `position/risk_monitor.py`

新增 `calculate_dynamic_stop_loss()` 方法：

```python
# 基于 ATR 的动态止损
monitor.calculate_dynamic_stop_loss(
    current_price=100,
    atr=3.5,  # ATR 为 3.5
    volatility_multiplier=1.5
)
# 止损价 = 100 - (3.5 * 1.5) = 94.75

# 基于波动率的动态止损
monitor.calculate_dynamic_stop_loss(
    current_price=100,
    volatility=0.04  # 波动率 4%
)
# 止损价 = 100 * (1 - 0.04 * 1.5) = 94.0
```

### 2.2 动态止盈

新增 `calculate_dynamic_stop_profit()` 方法，基于持仓时间调整止盈点：

| 持仓天数 | 止盈目标 |
|----------|----------|
| 1 天 | 10% |
| 3 天 | 15% |
| 5 天 | 20% |
| 10 天 | 25% |
| 20 天 | 30% |

```python
# 持仓 5 天，成本价 100
stop_profit = monitor.calculate_dynamic_stop_profit(
    cost_price=100,
    holding_days=5
)
# 止盈价 = 100 * (1 + 0.20) = 120
```

### 2.3 移动止盈（追踪止盈）

新增 `check_trail_stop()` 方法，从最高点回撤自动触发止盈：

```python
# 持仓盈利 15% 以上启用移动止盈
# 从最高点回撤 10% 触发
monitor.check_trail_stop(
    analysis=stock_analysis,
    highest_price=130  # 持仓期间最高价
)
```

---

## 3. 回测与评估增强

### 3.1 进阶风险指标

**文件**: `backtest/metrics.py`

| 指标 | 说明 | 计算方法 |
|------|------|----------|
| **Calmar 比率** | 年化收益/最大回撤 | 衡量风险调整后收益 |
| **VaR (95%)** | 风险价值 | 95% 置信水平下的最大预期损失 |
| **CVaR (95%)** | 条件 VaR | 超过 VaR 阈值的预期损失 |
| **Omega 比率** | 收益/损失比 | 考虑所有矩的收益分布比 |
| **尾部比率** | 右尾/左尾 | 衡量收益分布的对称性 |

### 3.2 基准对比指标

| 指标 | 说明 |
|------|------|
| **信息比率** | 超额收益/跟踪误差 |
| **跟踪误差** | 相对基准的波动率 |
| **Alpha** | 相对基准的超额收益 |
| **Beta** | 相对基准的敏感度 |

### 3.3 交易统计指标

| 指标 | 说明 |
|------|------|
| **连续盈利** | 最大连续盈利次数 |
| **连续亏损** | 最大连续亏损次数 |
| **最佳月度** | 历史最佳月度收益 |
| **最差月度** | 历史最差月度收益 |
| **月度收益** | 各月收益率列表 |

### 3.4 回测输出示例

```
【回测绩效】
总收益率：+45.2%
年化收益率：+38.5%
最大回撤：-12.3%
夏普比率：1.85
索提诺比率：2.10
Calmar 比率：3.13

进阶指标:
  VaR(95%): -2.5%
  CVaR(95%): -3.8%
  Omega 比率：1.65
  尾部比率：1.42

基准对比:
  Alpha: +15.2%
  Beta: 0.85
  信息比率：0.75

交易统计:
  胜率：62.5%
  盈亏比：2.35
  连续盈利：8 次
  连续亏损：3 次
  最佳月度：+12.5%
  最差月度：-5.2%
```

---

## 4. 使用示例

### 4.1 策略权重优化

```bash
# 牛市模式
python main.py --strategy balanced --market bull --top-n 10

# 自定义权重
python main.py --strategy custom \
    --weights "0.4,0.3,0.15,0.1,0.05" \
    --top-n 10
```

### 4.2 动态风控

```python
from position.risk_monitor import create_risk_monitor

monitor = create_risk_monitor()

# 设置动态止损
stop_loss_price = monitor.calculate_dynamic_stop_loss(
    current_price=current_price,
    atr=stock.atr,
    volatility=stock.volatility
)

# 设置动态止盈
stop_profit_price = monitor.calculate_dynamic_stop_profit(
    cost_price=position.cost,
    holding_days=position.holding_days,
    current_price=current_price
)
```

### 4.3 回测增强

```python
from backtest.metrics import create_metrics_calculator

calculator = create_metrics_calculator(risk_free_rate=0.03)

metrics = calculator.calculate_metrics(
    equity_curve=equity_curve,
    benchmark_curve=benchmark_curve,
    trade_returns=trade_returns,
    holding_days=holding_days
)

print(f"Calmar 比率：{metrics.calmar_ratio:.2f}")
print(f"信息比率：{metrics.information_ratio:.2f}")
print(f"最佳月度：{metrics.best_month:.2%}")
```

---

## 5. 注意事项

### 5.1 动态止损止盈

- ATR/波动率数据需要额外获取
- 移动止盈适用于盈利超过 15% 的持仓
- 建议设置止损范围为 -5% 到 -8%

### 5.2 策略权重

- 权重总和会自动归一化
- 建议根据市场环境定期调整
- 单一策略权重不宜超过 60%

### 5.3 进阶指标

- VaR/CVaR 基于历史数据，存在滞后性
- Alpha/Beta 需要至少 10 个数据点
- 月度收益需要足够的回测周期

---

## 6. 后续优化方向

- [ ] 贝叶斯优化自动调参
- [ ] 遗传算法策略权重优化
- [ ] Kelly 公式资金分配
- [ ] 均值 - 方差模型组合优化
- [ ] 高频数据支持
- [ ] 板块轮动因子
- [ ] XGBoost/CatBoost/LSTM多模型融合

---

**更新时间**: 2026-03-09
