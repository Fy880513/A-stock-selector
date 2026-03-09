# A 股选股系统 - 快速入门指南

## 1. 安装步骤

### 1.1 创建虚拟环境（推荐）
```bash
cd astock_selector
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 1.2 安装依赖
```bash
pip install -r requirements.txt
```

### 1.3 安装 TA-Lib（可选，用于更精确的技术指标）
Windows 用户：
1. 下载：https://www.lfd.uci.edu/~gohlke/pythonlibs/#ta-lib
2. 安装：`pip install TA_Lib‑0.4.25‑cp39‑cp39‑win_amd64.whl`

或者直接使用 pandas-ta（已包含在 requirements.txt 中）

### 1.4 配置 Tushare Token
1. 访问 https://tushare.pro/ 注册账号
2. 获取个人 Token
3. 复制 `.env.example` 为 `.env`
4. 编辑 `.env` 文件，填入你的 Token：
```
TUSHARE_TOKEN=your_token_here
```

## 2. 使用方法

### 2.1 命令行模式

#### 今日选股
```bash
python main.py --date 20260309 --top-n 10 --output all
```

#### 历史选股
```bash
python main.py --date 20260301 --top-n 10
```

#### 历史回测
```bash
python main.py --backtest --start 20250101 --end 20260301 --capital 100000
```

#### 查看选股追踪
```bash
python main.py --tracking 20260301
```

#### 查看帮助
```bash
python main.py --help
```

### 2.2 Web 界面模式

启动 Streamlit 应用：
```bash
streamlit run web/streamlit_app.py
```

浏览器访问：http://localhost:8501

### 2.3 定时任务模式

启动每日自动选股：
```bash
python scheduler.py
```

## 3. 输出说明

### 3.1 命令行输出
```
============================================================
A 股选股系统 - 选股结果
============================================================
选股日期：20260309
选出数量：10
============================================================

【组合概要】
  选股数量：10
  建议仓位：¥250,000
  仓位使用：125%
  剩余资金：¥-50,000

排名  代码        名称        得分    买入价      仓位      止损      止盈
------------------------------------------------------------------------------
#1    000001    平安银行   78.5   ¥12.50     10.0%    ¥11.50   ¥15.00
#2    600036    招商银行   76.2   ¥35.80     10.0%    ¥33.00   ¥43.00
...
```

### 3.2 输出文件
- `output/选股结果_YYYYMMDD.json` - JSON 格式选股结果
- `output/选股报告_YYYYMMDD.html` - HTML 格式选股报告

### 3.3 数据字段说明
| 字段 | 说明 |
|------|------|
| ts_code | 股票代码 |
| stock_name | 股票名称 |
| total_score | 综合得分 (0-100) |
| fundamental_score | 基本面得分 |
| technical_score | 技术面得分 |
| capital_flow_score | 资金面得分 |
| hotspot_score | 热点面得分 |
| buy_price | 建议买入价 |
| target_shares | 建议股数 |
| target_amount | 建议金额 |
| stop_loss | 止损价 |
| stop_profit | 止盈价 |
| position_ratio | 仓位占比 |

## 4. 选股策略说明

### 4.1 评分权重
- **基本面 (25%)**：PE、PEG、营收增长、净利润增长、ROE、毛利率等
- **技术面 (35%)**：均线趋势、MACD、KDJ、RSI、布林带、成交量等
- **资金面 (25%)**：主力净流入、北向资金、龙虎榜、大单流向等
- **热点面 (15%)**：行业热度、概念热度、涨停梯队、新闻情绪等

### 4.2 筛选条件
1. 排除 ST、*ST 股票
2. 排除上市不满 1 年的新股
3. 基本面门槛：至少满足 60% 的基本面条件
4. 技术面确认：至少 3 个技术指标发出买入信号
5. 综合得分排名前 10

### 4.3 止损止盈规则
- **止损**：跌破 MA20 减仓 50%，跌破 MA60 或亏损 8% 清仓
- **止盈**：涨幅 20% 减仓 50%，涨幅 30% 或从最高点回撤 10% 清仓

## 5. 常见问题

### Q: 为什么选股结果为空？
A: 可能原因：
1. Tushare Token 未配置或积分不足
2. 日期不是交易日
3. 筛选条件过于严格

### Q: 如何调整选股数量？
A: 使用 `--top-n` 参数，例如：`python main.py --top-n 20`

### Q: 如何修改选股策略？
A: 编辑 `config/settings.py` 文件中的配置项

### Q: 数据更新频率？
A: 日线数据，建议每个交易日收盘后（17:00 后）运行

## 6. 数据源说明

### Tushare Pro
- 注册送 100 积分
- 基础数据足够使用（日线行情、财务数据等）
- 积分不足时可充值或升级

### AKShare（补充）
- 完全免费
- 用于获取龙虎榜、资金流向等数据
- 稳定性依赖于源网站

## 7. 风险提示

⚠️ **重要提示**：
1. 本系统仅供学习和研究使用
2. 选股结果基于历史数据分析，不代表未来表现
3. 股市有风险，投资需谨慎
4. 请结合个人判断进行决策，不要完全依赖系统推荐

## 8. 技术支持

如有问题，请查看：
- 项目 README.md
- 日志文件（控制台输出）
- Tushare 文档：https://tushare.pro/document/2
