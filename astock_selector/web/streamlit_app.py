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
from backtest.parameter_tuner import create_parameter_tuner
from position.risk_monitor import create_risk_monitor
from position.analyzer import create_analyzer


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
    ["今日选股", "历史选股", "历史回测", "参数调优", "风险控制", "选股追踪"],
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
            "fundamental_score", "technical_score", "capital_flow_score", "hotspot_score", "ml_score", "ml_confidence",
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
            "ml_score": "ML得分",
            "ml_confidence": "ML置信度",
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

        # ML置信度颜色
        def color_confidence(val):
            if val == "高":
                return "color: green; font-weight: bold"
            elif val == "中":
                return "color: orange; font-weight: bold"
            else:
                return "color: red; font-weight: bold"

        styled = display_df.style.applymap(
            color_score,
            subset=["综合得分", "基本面", "技术面", "资金面", "热点面", "ML得分"]
        ).applymap(
            color_confidence,
            subset=["ML置信度"]
        )

        # 添加条件格式
        styled = styled.background_gradient(
            subset=["综合得分"],
            cmap="RdYlGn",
            low=0.4,
            high=0.8
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

    col1, col2 = st.columns(2)
    with col1:
        top_n = st.slider("选股数量", 5, 20, 10)
    with col2:
        strategy = st.selectbox(
            "选股策略",
            ["comprehensive", "dragon"],
            index=0
        )

    if st.button("运行回测", type="primary"):
        with st.spinner("正在回测，请稍候..."):
            try:
                engine = create_backtest_engine(
                    initial_capital=capital,
                    holding_period=holding_period,
                    top_n=top_n,
                    selection_strategy=strategy,
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

                # 行业表现
                if result.sector_performance:
                    st.subheader("行业表现")
                    sector_df = pd.DataFrame(
                        list(result.sector_performance.items()),
                        columns=["行业", "平均收益率"]
                    )
                    sector_df = sector_df.sort_values("平均收益率", ascending=False)
                    st.dataframe(sector_df, use_container_width=True)

            except Exception as e:
                st.error(f"回测失败：{str(e)}")

elif mode == "参数调优":
    st.header("⚙️ 参数调优")

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
        objective = st.selectbox(
            "优化目标",
            ["sharpe_ratio", "total_return", "sortino_ratio", "win_rate"],
            index=0
        )

    # 参数范围
    st.subheader("参数范围")
    col1, col2 = st.columns(2)
    with col1:
        holding_period_min = st.number_input("持有周期最小值 (天)", min_value=5, value=5)
        holding_period_max = st.number_input("持有周期最大值 (天)", min_value=holding_period_min, value=20)
        holding_period_step = st.number_input("持有周期步长", min_value=1, value=5)
    with col2:
        top_n_min = st.number_input("选股数量最小值", min_value=5, value=5)
        top_n_max = st.number_input("选股数量最大值", min_value=top_n_min, value=15)
        top_n_step = st.number_input("选股数量步长", min_value=1, value=5)

    optimization_method = st.selectbox(
        "优化方法",
        ["网格搜索", "遗传算法"],
        index=0
    )

    if st.button("开始参数优化", type="primary"):
        with st.spinner("正在优化参数，请稍候..."):
            try:
                # 构建参数网格
                param_grid = {
                    'holding_period': list(range(holding_period_min, holding_period_max + 1, holding_period_step)),
                    'top_n': list(range(top_n_min, top_n_max + 1, top_n_step)),
                }

                tuner = create_parameter_tuner(initial_capital=capital)

                if optimization_method == "网格搜索":
                    result = tuner.grid_search(
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d"),
                        param_grid=param_grid,
                        objective=objective,
                    )
                else:
                    # 遗传算法参数范围
                    param_ranges = {
                        'holding_period': (holding_period_min, holding_period_max),
                        'top_n': (top_n_min, top_n_max),
                    }
                    result = tuner.genetic_algorithm(
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d"),
                        param_ranges=param_ranges,
                        objective=objective,
                    )

                # 显示结果
                st.success("参数优化完成！")
                
                # 最优参数
                st.subheader("最优参数")
                st.write(result.best_params)
                
                # 最优结果绩效
                if result.best_result:
                    m = result.best_result.metrics
                    st.subheader("最优结果绩效")
                    cols = st.columns(4)
                    cols[0].metric("总收益率", f"{m.total_return:.2%}")
                    cols[1].metric("夏普比率", f"{m.sharpe_ratio:.2f}")
                    cols[2].metric("最大回撤", f"{m.max_drawdown:.2%}", delta_color="inverse")
                    cols[3].metric("胜率", f"{m.win_rate:.2%}")
                
                # 参数重要性
                if result.parameter_importance:
                    st.subheader("参数重要性")
                    importance_df = pd.DataFrame(
                        list(result.parameter_importance.items()),
                        columns=["参数", "重要性"]
                    )
                    importance_df = importance_df.sort_values("重要性", ascending=False)
                    st.dataframe(importance_df, use_container_width=True)
                    
                    # 绘制重要性图
                    st.bar_chart(importance_df.set_index("参数"))

            except Exception as e:
                st.error(f"参数优化失败：{str(e)}")

elif mode == "风险控制":
    st.header("🛡️ 风险控制")

    # 单个股票风险评估
    st.subheader("个股风险评估")
    stock_code = st.text_input("输入股票代码", placeholder="例如：600000.SH")
    
    if st.button("评估风险"):
        if stock_code:
            with st.spinner("正在评估风险，请稍候..."):
                try:
                    analyzer = create_analyzer()
                    analysis = analyzer.analyze_stock(stock_code)
                    
                    if analysis:
                        # 显示股票基本信息
                        st.subheader(f"{analysis.stock_name} ({analysis.ts_code}) 风险评估")
                        
                        # 风险评估
                        risk_monitor = create_risk_monitor()
                        warnings = risk_monitor.check_all_risks(analysis)
                        
                        # 显示风险预警
                        if warnings:
                            st.warning("⚠️ 风险预警")
                            for warning in warnings:
                                if warning.risk_level.value == "danger":
                                    st.error(f"{warning.message} - 建议：{warning.suggestion}")
                                elif warning.risk_level.value == "warning":
                                    st.warning(f"{warning.message} - 建议：{warning.suggestion}")
                                else:
                                    st.info(f"{warning.message} - 建议：{warning.suggestion}")
                        else:
                            st.success("✅ 未发现明显风险")
                        
                        # 显示技术分析
                        st.subheader("技术分析")
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("技术得分", f"{analysis.technical_score:.0f}")
                        col2.metric("MA趋势", analysis.ma_trend)
                        col3.metric("KDJ状态", analysis.kdj_status)
                        col4.metric("MACD状态", analysis.macd_status)
                    else:
                        st.error("无法获取股票数据")
                except Exception as e:
                    st.error(f"风险评估失败：{str(e)}")
        else:
            st.warning("请输入股票代码")

    # 组合风险评估
    st.subheader("组合风险评估")
    stock_codes = st.text_area("输入股票代码列表（每行一个）", placeholder="600000.SH\n000001.SZ\n300001.SZ")
    
    if st.button("评估组合风险"):
        if stock_codes:
            with st.spinner("正在评估组合风险，请稍候..."):
                try:
                    codes = [code.strip() for code in stock_codes.split('\n') if code.strip()]
                    analyses = []
                    position_ratios = {}
                    
                    analyzer = create_analyzer()
                    for i, code in enumerate(codes):
                        analysis = analyzer.analyze_stock(code)
                        if analysis:
                            analyses.append(analysis)
                            position_ratios[code] = 1.0 / len(codes)  # 等权重
                    
                    if analyses:
                        risk_monitor = create_risk_monitor()
                        report = risk_monitor.generate_risk_report(analyses, position_ratios)
                        
                        # 显示风险统计
                        st.subheader("风险统计")
                        cols = st.columns(4)
                        cols[0].metric("总风险预警", report.get("total_warnings", 0))
                        cols[1].metric("危险级", report.get("danger_count", 0))
                        cols[2].metric("警告级", report.get("warning_count", 0))
                        cols[3].metric("观察级", report.get("watch_count", 0))
                        
                        # 显示组合风险评估
                        if "portfolio_risk" in report:
                            pr = report["portfolio_risk"]
                            st.subheader("组合风险评估")
                            st.write(f"总风险评分：{pr.total_risk_score:.1f}")
                            st.write(f"风险等级：{pr.risk_level.value}")
                            
                            if pr.recommendations:
                                st.subheader("风险建议")
                                for rec in pr.recommendations:
                                    st.info(rec)
                        
                        # 显示市场风险
                        if report.get("market_risk"):
                            mr = report["market_risk"]
                            st.subheader("市场风险")
                            st.write(f"{mr.message} - 建议：{mr.suggestion}")
                    else:
                        st.error("无法获取股票数据")
                except Exception as e:
                    st.error(f"组合风险评估失败：{str(e)}")
        else:
            st.warning("请输入股票代码列表")

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
