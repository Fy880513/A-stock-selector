"""
Streamlit Web 界面
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 导入本地模块
import sys
sys.path.insert(0, str(pd.Path(__file__).parent))

from selector.screener import get_screener
from report.generator import create_report_generator
from backtest.engine import create_backtest_engine


st.set_page_config(
    page_title="A 股选股系统",
    page_icon="📈",
    layout="wide",
)

st.title("📈 A 股选股系统")
st.markdown("---")

# 侧边栏
st.sidebar.header("功能选择")
mode = st.sidebar.radio(
    "选择模式",
    ["今日选股", "历史选股", "历史回测", "选股追踪"],
)

st.sidebar.markdown("---")
st.sidebar.info("""
**系统说明**

本系统从四个维度综合选股：
- **基本面** (25%)：估值、成长、盈利、偿债
- **技术面** (35%)：均线、MACD、KDJ、RSI 等
- **资金面** (25%)：主力、北向、龙虎榜
- **热点面** (15%)：行业、概念、新闻

适合中短期右侧交易风格。
""")

# 状态缓存
if "last_result" not in st.session_state:
    st.session_state.last_result = None


def run_stock_selection(date: str, top_n: int):
    """执行选股"""
    screener = get_screener()
    result = screener.select_with_portfolio(trade_date=date, top_n=top_n)
    return result


if mode == "今日选股":
    st.header("📊 今日选股")

    col1, col2 = st.columns([3, 1])
    with col1:
        today = datetime.now().strftime("%Y%m%d")
        top_n = st.slider("选出股票数量", 5, 20, 10)

    if st.button("开始选股", type="primary"):
        with st.spinner("正在选股，请稍候..."):
            try:
                result = run_stock_selection(today, top_n)
                st.session_state.last_result = result

                if result["stocks"]:
                    st.success(f"选出 {len(result['stocks'])} 只股票")
                else:
                    st.warning(f"选股失败：{result.get('message', '未知错误')}")
            except Exception as e:
                st.error(f"错误：{str(e)}")

    if st.session_state.last_result:
        result = st.session_state.last_result
        stocks = result["stocks"]
        portfolio = result["portfolio"]

        # 概要卡片
        cols = st.columns(4)
        cols[0].metric("选股数量", len(stocks))
        cols[1].metric("建议仓位", f"¥{portfolio.get('total_amount', 0):,.0f}")
        cols[2].metric("仓位使用", f"{portfolio.get('used_ratio', 0):.0%}")
        cols[3].metric("剩余资金", f"¥{portfolio.get('remaining', 0):,.0f}")

        st.markdown("---")

        # 股票表格
        df = pd.DataFrame(stocks)
        display_cols = [
            "rank", "ts_code", "stock_name", "total_score",
            "buy_price", "target_shares", "target_amount",
            "stop_loss", "stop_profit", "position_ratio"
        ]

        # 重命名列
        column_names = {
            "rank": "排名",
            "ts_code": "代码",
            "stock_name": "名称",
            "total_score": "综合得分",
            "fundamental_score": "基本面",
            "technical_score": "技术面",
            "capital_flow_score": "资金面",
            "hotspot_score": "热点面",
            "buy_price": "买入价",
            "target_shares": "股数",
            "target_amount": "金额",
            "stop_loss": "止损价",
            "stop_profit": "止盈价",
            "position_ratio": "仓位%",
        }

        # 显示表格
        display_df = df[[c for c in display_cols if c in df.columns]].copy()
        display_df = display_df.rename(columns=column_names)

        # 得分颜色
        def color_score(val):
            if val >= 75:
                return "color: green; font-weight: bold"
            elif val >= 60:
                return "color: orange; font-weight: bold"
            else:
                return "color: red; font-weight: bold"

        styled = display_df.style.applymap(
            color_score,
            subset=["综合得分"]
        )

        st.dataframe(styled, use_container_width=True)

        # 下载按钮
        csv = df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 下载 CSV",
            data=csv,
            file_name=f"选股结果_{today}.csv",
            mime="text/csv",
        )

elif mode == "历史选股":
    st.header("📅 历史选股")

    date = st.date_input("选择日期", value=datetime.now() - timedelta(days=1))
    date_str = date.strftime("%Y%m%d")
    top_n = st.slider("选出股票数量", 5, 20, 10)

    if st.button("开始选股", type="primary"):
        with st.spinner("正在选股..."):
            result = run_stock_selection(date_str, top_n)
            st.session_state.last_result = result

            if result["stocks"]:
                st.success(f"选出 {len(result['stocks'])} 只股票")
                df = pd.DataFrame(result["stocks"])
                st.dataframe(df, use_container_width=True)

elif mode == "历史回测":
    st.header("📉 历史回测")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime.now() - timedelta(days=180),
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=datetime.now(),
        )

    col1, col2 = st.columns(2)
    with col1:
        capital = st.number_input("初始资金", min_value=10000, value=100000, step=10000)
    with col2:
        holding_period = st.slider("持有周期 (天)", 5, 30, 15)

    if st.button("运行回测", type="primary"):
        with st.spinner("正在回测，请稍候..."):
            try:
                engine = create_backtest_engine(
                    initial_capital=capital,
                    holding_period=holding_period,
                )
                result = engine.run_backtest(
                    start_date.strftime("%Y%m%d"),
                    end_date.strftime("%Y%m%d"),
                )

                m = result.metrics

                # 绩效指标
                st.subheader("绩效指标")
                cols = st.columns(4)
                cols[0].metric("总收益率", f"{m.total_return:.2%}")
                cols[1].metric("年化收益", f"{m.annual_return:.2%}")
                cols[2].metric("最大回撤", f"{m.max_drawdown:.2%}", delta_color="inverse")
                cols[3].metric("夏普比率", f"{m.sharpe_ratio:.2f}")

                # 交易统计
                st.subheader("交易统计")
                cols = st.columns(3)
                cols[0].metric("总交易次数", m.total_trades)
                cols[1].metric("胜率", f"{m.win_rate:.2%}")
                cols[2].metric("盈亏比", f"{m.profit_loss_ratio:.2f}")

                # 权益曲线
                if result.equity_curve is not None:
                    st.subheader("权益曲线")
                    st.line_chart(result.equity_curve)

            except Exception as e:
                st.error(f"回测失败：{str(e)}")

elif mode == "选股追踪":
    st.header("📋 选股追踪")

    date = st.date_input("选择日期", value=datetime.now())
    date_str = date.strftime("%Y%m%d")

    if st.button("查看追踪结果"):
        from tracker.performance import create_tracker
        tracker = create_tracker()
        stats = tracker.update_tracking(date_str)

        if stats:
            cols = st.columns(3)
            cols[0].metric("选股数量", stats.get("total_count", 0))
            cols[1].metric("上涨数量", stats.get("positive_count", 0))
            cols[2].metric("胜率", f"{stats.get('win_rate', 0):.2%}")

            st.metric("平均收益", f"{stats.get('avg_return', 0):.2%}")
        else:
            st.info("该日期无选股数据")

# 页脚
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
        ⚠️ 免责声明：选股结果仅供参考，不构成投资建议。股市有风险，投资需谨慎。
    </div>
    """,
    unsafe_allow_html=True,
)
