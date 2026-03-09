"""
A 股选股系统 - 主入口

使用方法:
    python main.py --date 2026-03-09 --top-n 10
    python main.py --backtest --start 20250101 --end 20260301
    python main.py --help
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import OUTPUT_DIR
from selector.screener import get_screener
from backtest.engine import create_backtest_engine
from report.generator import create_report_generator
from data.storage import get_storage
from utils.logger import get_logger
from utils.helpers import format_currency

logger = get_logger(__name__)


def select_stocks(
    date: str,
    top_n: int,
    output_format: str,
):
    """执行选股"""
    print(f"\n{'='*60}")
    print("A 股选股系统 - 选股结果")
    print(f"{'='*60}")
    print(f"选股日期：{date}")
    print(f"选出数量：{top_n}")
    print(f"{'='*60}\n")

    # 执行选股
    screener = get_screener()
    result = screener.select_with_portfolio(trade_date=date, top_n=top_n)

    if not result["stocks"]:
        print(f"❌ 选股失败：{result.get('message', '未知错误')}")
        return

    # 显示结果
    stocks = result["stocks"]
    portfolio = result["portfolio"]

    print(f"【组合概要】")
    print(f"  选股数量：{len(stocks)}")
    print(f"  建议仓位：{format_currency(portfolio.get('total_amount', 0))}")
    print(f"  仓位使用：{portfolio.get('used_ratio', 0):.0%}")
    print(f"  剩余资金：{format_currency(portfolio.get('remaining', 0))}")
    print()

    # 表格显示
    print(f"{'排名':<6}{'代码':<12}{'名称':<12}{'得分':<8}{'买入价':<12}{'仓位':<10}{'止损':<12}{'止盈':<12}")
    print("-" * 82)

    for stock in stocks:
        rank = stock.get("rank", 0)
        ts_code = stock.get("ts_code", "")
        name = stock.get("stock_name", "")
        score = stock.get("total_score", 0)
        buy_price = stock.get("buy_price", 0)
        position_ratio = stock.get("position_ratio", 0)
        stop_loss = stock.get("stop_loss", 0)
        stop_profit = stock.get("stop_profit", 0)

        print(f"#{rank:<5}{ts_code:<12}{name:<12}{score:<8.1f}{buy_price:<12.2f}{position_ratio:<9.1f}%{stop_loss:<12.2f}{stop_profit:.2f}")

    print()

    # 保存结果
    generator = create_report_generator()

    if output_format == "json":
        output_file = generator.generate_json_report(date, stocks, portfolio)
        print(f"✅ JSON 报告已保存：{output_file}")
    elif output_format == "html":
        output_file = generator.generate_html_report(date, stocks, portfolio)
        print(f"✅ HTML 报告已保存：{output_file}")
    elif output_format == "all":
        json_file = generator.generate_json_report(date, stocks, portfolio)
        html_file = generator.generate_html_report(date, stocks, portfolio)
        print(f"✅ JSON 报告：{json_file}")
        print(f"✅ HTML 报告：{html_file}")

    # 保存到数据库
    storage = get_storage()
    try:
        df = pd.DataFrame(stocks)
        df["select_date"] = date
        storage.save_selection_result(df)
        print(f"✅ 数据已保存至数据库")
    except Exception as e:
        logger.warning(f"保存数据库失败：{e}")

    print(f"\n{'='*60}")
    print("免责声明：选股结果仅供参考，不构成投资建议。")
    print("股市有风险，投资需谨慎。")
    print(f"{'='*60}\n")


def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float,
    holding_period: int,
):
    """运行回测"""
    print(f"\n{'='*60}")
    print("A 股选股系统 - 历史回测")
    print(f"{'='*60}")
    print(f"回测区间：{start_date} - {end_date}")
    print(f"初始资金：¥{initial_capital:,.0f}")
    print(f"持有周期：{holding_period}天")
    print(f"{'='*60}\n")

    # 运行回测
    engine = create_backtest_engine(
        initial_capital=initial_capital,
        holding_period=holding_period,
    )

    result = engine.run_backtest(start_date, end_date)
    engine.print_result(result)


def show_tracking(date: str):
    """显示选股追踪"""
    from tracker.performance import create_tracker

    tracker = create_tracker()
    report = tracker.generate_tracking_report(date)
    print(report)


def analyze_position(
    show_suggestion: bool = False,
    show_risk: bool = False,
    auto_login: bool = False,
):
    """
    分析持仓

    Args:
        show_suggestion: 显示操作建议
        show_risk: 显示风险警示
        auto_login: 是否自动登录
    """
    print(f"\n{'='*60}")
    print("A 股选股系统 - 持仓分析")
    print(f"{'='*60}")

    from position.easytrader_api import get_trading_api, create_trading_api
    from position.analyzer import create_position_analyzer
    from position.risk_monitor import create_risk_monitor
    from position.suggestion import create_suggestion_generator

    # 获取交易 API
    api = get_trading_api()

    # 尝试登录
    if auto_login:
        print("正在自动登录...")
        if not api.login():
            print("❌ 自动登录失败，请先手动登录同花顺")
            print("   提示：启动同花顺客户端并登录后，再运行此命令")
            return
    else:
        # 手动模式：尝试连接已运行的同花顺
        if not api.login():
            print("❌ 连接失败，请先启动并登录同花顺客户端")
            return

    print("✅ 成功连接到交易账户\n")

    # 获取账户信息
    account_info = api.get_account_info()
    if account_info:
        print(f"【账户信息】")
        print(f"  总资产：¥{account_info.total_assets:,.2f}")
        print(f"  可用资金：¥{account_info.available_cash:,.2f}")
        print(f"  持仓市值：¥{account_info.market_value:,.2f}")
        print(f"  总盈亏：¥{account_info.total_profit:,.2f} ({account_info.total_profit_ratio:.2%})")
        print()

    # 获取持仓
    positions = api.get_positions()
    if not positions:
        print("【持仓】空仓")
        print(f"\n{'='*60}\n")
        return

    print(f"【持仓概览】共 {len(positions)} 只")
    print(f"{'代码':<12}{'名称':<12}{'数量':<10}{'成本':<12}{'现价':<10}{'盈亏':<12}")
    print("-" * 68)

    for pos in positions:
        profit_symbol = "+" if pos.profit >= 0 else ""
        print(f"{pos.ts_code:<12}{pos.stock_name:<12}{pos.volume:<10}{pos.cost_price:<12.2f}"
              f"{pos.current_price:<10.2f}{profit_symbol}¥{pos.profit:,.0f} ({pos.profit_ratio:.2%})")
    print("-" * 68)

    # 持仓分析
    print("\n【持仓分析】")
    analyzer = create_position_analyzer()
    analyses = analyzer.analyze_all_positions(positions)
    summary = analyzer.generate_summary(analyses)

    print(f"  持仓市值：¥{summary.get('total_market_value', 0):,.2f}")
    print(f"  总盈亏：¥{summary.get('total_profit', 0):,.2f} ({summary.get('total_profit_ratio', 0):.2%})")
    print(f"  平均技术得分：{summary.get('avg_technical_score', 0):.1f}")
    print(f"  多头趋势：{summary.get('strong_count', 0)} 只")
    print(f"  空头趋势：{summary.get('weak_count', 0)} 只")

    # 详细分析
    print("\n【详细分析】")
    print(f"{'代码':<12}{'名称':<12}{'技术分':<10}{'均线趋势':<12}{'MACD':<12}{'KDJ':<10}")
    print("-" * 68)

    for a in analyses:
        print(f"{a.ts_code:<12}{a.stock_name:<12}{a.technical_score:<10.1f}"
              f"{a.ma_trend:<12}{a.macd_status:<12}{a.kdj_status:<10}")
    print("-" * 68)

    # 风险监控
    if show_risk or show_suggestion:
        monitor = create_risk_monitor()
        risk_report = monitor.generate_risk_report(analyses)

        if risk_report["danger_warnings"]:
            print("\n【🔴 危险警示】")
            for w in risk_report["danger_warnings"]:
                print(f"  • {w.ts_code} {w.stock_name}: {w.message}")
                print(f"    建议：{w.suggestion}")

        if risk_report["warning_warnings"]:
            print("\n【⚠️ 风险预警】")
            for w in risk_report["warning_warnings"]:
                print(f"  • {w.ts_code} {w.stock_name}: {w.message}")
                print(f"    建议：{w.suggestion}")

        if risk_report["watch_warnings"]:
            print("\n【🟡 观察提示】")
            for w in risk_report["watch_warnings"]:
                print(f"  • {w.ts_code} {w.stock_name}: {w.message}")

        if not risk_report["warnings"]:
            print("\n【风险警示】无")

    # 操作建议
    if show_suggestion:
        generator = create_suggestion_generator()

        # 准备预警数据
        all_warnings = {}
        for a in analyses:
            warnings = monitor.check_all_risks(a)
            all_warnings[a.ts_code] = warnings

        suggestions = generator.generate_all_suggestions(analyses, all_warnings)
        generator.print_suggestions(suggestions)

    print(f"\n{'='*60}")
    print("免责声明：分析结果仅供参考，不构成投资建议。")
    print("股市有风险，投资需谨慎。")
    print(f"{'='*60}\n")


def show_dragon_stocks(board_name: Optional[str] = None):
    """
    显示龙头股

    Args:
        board_name: 板块名称（可选）
    """
    print(f"\n{'='*60}")
    print("A 股选股系统 - 龙头战法")
    print(f"{'='*60}")

    from strategies.dragon_strategy import create_dragon_strategy

    strategy = create_dragon_strategy()

    if board_name:
        # 分析指定板块
        print(f"\n【板块】{board_name}")
        dragons = strategy.identify_dragon_stocks(board_name, top_n=3)

        if not dragons:
            print("未找到龙头股")
            return

        print(f"\n{'排名':<6}{'代码':<10}{'名称':<12}{'涨幅':<10}{'连板':<8}{'置信度':<8}")
        print("-" * 60)

        for d in dragons:
            print(f"#{d.rank:<5}{d.ts_code:<10}{d.stock_name:<12}{d.change_pct:>8.2f}%"
                  f"{d.limit_up_count:>6}板     {d.confidence:<8}")

        print("\n【龙头切换分析】")
        switch_info = strategy.find_dragon_switch(board_name)
        if switch_info.get("switch_signal"):
            confidence = switch_info.get("confidence", "低")
            print(f"⚠️ 龙头切换信号：{switch_info.get('analysis')} (置信度：{confidence})")
        else:
            print(f"✓ {switch_info.get('analysis')}")

    else:
        # 显示热门板块龙头
        print("\n【热门板块龙头】")
        boards = ["人工智能", "新能源", "半导体", "医药", "大消费"]

        for board in boards[:5]:
            dragons = strategy.identify_dragon_stocks(board, top_n=1)
            if dragons:
                d = dragons[0]
                print(f"  {board}: {d.stock_name} ({d.ts_code}) - {d.change_pct:.2f}%, {d.limit_up_count}连板")

    print(f"\n{'='*60}")


def show_limit_up_analysis():
    """显示涨停板分析"""
    print(f"\n{'='*60}")
    print("A 股选股系统 - 涨停板分析")
    print(f"{'='*60}")

    from strategies.limit_up import create_limit_up_analyzer

    analyzer = create_limit_up_analyzer()

    # 涨停统计
    stat = analyzer.get_limit_up_statistics()

    print(f"\n【涨停统计】")
    print(f"  涨停数量：{stat.total_limit_up}")
    print(f"  跌停数量：{stat.total_limit_down}")
    print(f"  涨停占比：{stat.limit_up_ratio:.2f}%")
    print(f"  炸板数量：{stat.炸板_count}")
    print(f"  炸板率：{stat.炸板_ratio:.2f}%")
    print(f"  最高连板：{stat.highest_connect}板")

    print(f"\n【连板分布】")
    for count, num in sorted(stat.connect_board_count.items(), reverse=True):
        print(f"  {count}连板：{num}只")

    # 涨停股列表
    print(f"\n【涨停股列表】")
    limit_up_stocks = analyzer.get_limit_up_list()

    if limit_up_stocks:
        print(f"{'代码':<12}{'名称':<12}{'涨幅':<10}{'量比':<8}{'换手':<8}{'行业':<20}")
        print("-" * 70)

        for s in limit_up_stocks[:20]:  # 显示前 20 只
            print(f"{s.ts_code:<12}{s.stock_name:<12}{s.change_pct:>8.2f}%"
                  f"{s.volume_ratio:>8.2f}{s.turn_over_rate:>6.2f}%  {s.industry:<20}")

    # 强度分析
    print(f"\n{'='*60}")
    print("使用：python main.py --limit-up-detail --code 000001 查看个股涨停强度")
    print(f"{'='*60}")


def show_limit_up_detail(ts_code: str):
    """
    显示个股涨停强度

    Args:
        ts_code: 股票代码
    """
    print(f"\n{'='*60}")
    print(f"A 股选股系统 - 涨停强度分析 ({ts_code})")
    print(f"{'='*60}")

    from strategies.limit_up import create_limit_up_analyzer

    analyzer = create_limit_up_analyzer()

    # 强度分析
    strength_info = analyzer.analyze_limit_up_strength(ts_code)
    if strength_info:
        print(f"\n【强度评分】{strength_info.get('score', 0)}分 - {strength_info.get('strength', '')}")
        print(f"\n【分析】")
        for reason in strength_info.get("reasons", []):
            print(f"  • {reason}")
        print(f"\n【建议】{strength_info.get('suggestion', '')}")

    # 连板概率
    prob_info = analyzer.predict_connect_probability(ts_code)
    if prob_info:
        print(f"\n【连板概率】{prob_info.get('probability', 0)}% - {prob_info.get('level', '')}")
        print(f"【建议】{prob_info.get('suggestion', '')}")

    print(f"\n{'='*60}")


def show_seat_analysis():
    """显示龙虎榜席位分析"""
    print(f"\n{'='*60}")
    print("A 股选股系统 - 龙虎榜席位分析")
    print(f"{'='*60}")

    from strategies.seat_analysis import create_seat_analyzer

    analyzer = create_seat_analyzer()

    # 获取龙虎榜列表
    lhb_stocks = analyzer.get_lhb_list()

    if not lhb_stocks:
        print("今日无龙虎榜数据")
        return

    print(f"\n【龙虎榜统计】共 {len(lhb_stocks)} 只")
    print(f"{'代码':<12}{'名称':<12}{'涨跌幅':<10}{'换手率':<10}{'净买入':<12}{'机构':<8}{'北向':<8}{'席位分':<8}")
    print("-" * 90)

    # 按席位得分排序
    lhb_stocks.sort(key=lambda x: x.seat_score, reverse=True)

    for stock in lhb_stocks[:20]:  # 显示前 20 只
        net_symbol = "+" if stock.net_amount >= 0 else ""
        institution_symbol = "✓" if stock.has_institution else ""
        north_symbol = "✓" if stock.has_north else ""
        print(f"{stock.ts_code:<12}{stock.stock_name:<12}{stock.change_pct:>8.2f}%"
              f"{stock.turn_over_rate:>8.2f}%{net_symbol}¥{stock.net_amount:>8.0f}"
              f"{institution_symbol:>6}{'':>1}{north_symbol:>5}{'':>1}{stock.seat_score:>8.1f}")

    print("-" * 90)

    # 机构买入股
    institution_stocks = [s for s in lhb_stocks if s.has_institution]
    if institution_stocks:
        print(f"\n【机构买入】共 {len(institution_stocks)} 只")
        for s in institution_stocks[:5]:
            print(f"  • {s.stock_name} ({s.ts_code}): 净买入¥{s.net_amount:.0f}万")

    # 北向买入股
    north_stocks = [s for s in lhb_stocks if s.has_north]
    if north_stocks:
        print(f"\n【北向买入】共 {len(north_stocks)} 只")
        for s in north_stocks[:5]:
            print(f"  • {s.stock_name} ({s.ts_code}): 净买入¥{s.net_amount:.0f}万")

    print(f"\n{'='*60}")


def show_sentiment_analysis(ts_code: str, use_bert: bool = False, use_gpu: bool = False):
    """显示个股舆情情绪分析"""
    print(f"\n{'='*60}")
    print("A 股选股系统 - 舆情情绪分析")
    print(f"{'='*60}")
    print(f"股票代码：{ts_code}")
    print(f"分析模式：{'BERT 深度学习' if use_bert else '关键词分析'}")
    if use_gpu:
        print(f"加速方式：GPU 加速")
    print(f"{'='*60}\n")

    from factors.hotspots import analyze_stock_sentiment_enhanced, BERT_AVAILABLE

    if not BERT_AVAILABLE and use_bert:
        print("⚠️  BERT 模块不可用，请安装依赖：")
        print("   pip install transformers torch aiohttp")
        print()

    result = analyze_stock_sentiment_enhanced(
        ts_code=ts_code,
        use_bert=use_bert,
        use_gpu=use_gpu
    )

    if "error" in result:
        print(f"❌ 分析失败：{result['error']}")
        return

    print(f"【舆情得分】{result.get('sentiment_score', 0):.1f} / 100")
    print(f"【情绪等级】{result.get('sentiment_level', 'N/A')}")
    print(f"【情绪趋势】{result.get('trend', 'N/A')}")
    print()
    print(f"【新闻统计】")
    print(f"  新闻总数：{result.get('news_count', 0)}")
    print(f"  正面比例：{result.get('positive_ratio', 0):.1%}")
    print(f"  正面新闻：{result.get('positive_count', 0)}")
    print(f"  中性新闻：{result.get('neutral_count', 0)}")
    print(f"  负面新闻：{result.get('negative_count', 0)}")
    print()

    # 显示情绪等级说明
    sentiment_score = result.get('sentiment_score', 50)
    if sentiment_score >= 80:
        print("📈 情绪强烈看好，利好消息主导")
    elif sentiment_score >= 60:
        print("📈 情绪看好，正面消息较多")
    elif sentiment_score >= 40:
        print("➖ 情绪中性，消息面平淡")
    elif sentiment_score >= 20:
        print("📉 情绪看空，负面消息较多")
    else:
        print("📉 情绪强烈看空，重大利空主导")

    print(f"\n{'='*60}")


def select_stocks_with_strategy(
    date: str,
    top_n: int,
    output_format: str,
    strategy: str,
    enable_ml: bool = False,
):
    """
    使用指定策略执行选股

    Args:
        date: 选股日期
        top_n: 选出数量
        output_format: 输出格式
        strategy: 策略模式
        enable_ml: 是否启用 ML 评分
    """
    print(f"\n{'='*60}")
    print("A 股选股系统 - 策略选股")
    print(f"{'='*60}")
    print(f"选股日期：{date}")
    print(f"策略模式：{strategy}")
    print(f"{'='*60}\n")

    from selector.strategy_manager import create_strategy_manager, StrategyConfig, StrategyMode
    from selector.screener import get_screener

    # 创建策略管理器
    manager = create_strategy_manager()

    # 加载预设策略
    if strategy in ["conservative", "aggressive", "balanced", "all_in", "combined"]:
        manager.load_preset(strategy)
        print(f"使用预设策略：{strategy}")
    else:
        # 单一策略
        mode_map = {
            "comprehensive": StrategyMode.COMPREHENSIVE,
            "dragon": StrategyMode.DRAGON,
            "limit_up": StrategyMode.LIMIT_UP,
            "ml": StrategyMode.ML,
            "seat": StrategyMode.SEAT,
        }
        if strategy in mode_map:
            manager.strategies = {
                strategy: StrategyConfig(mode=mode_map[strategy], weight=1.0, enabled=True)
            }
        print(f"使用单一策略：{strategy}")

    # 执行综合选股
    screener = get_screener()
    result = screener.select_with_portfolio(trade_date=date, top_n=top_n * 2)  # 多选一些用于合并

    if not result["stocks"]:
        print(f"❌ 选股失败：{result.get('message', '未知错误')}")
        return

    comprehensive_stocks = result["stocks"]

    # 获取其他策略数据（如果需要）
    dragon_stocks = None
    limit_up_stocks = None
    ml_stocks = None
    seat_stocks = None

    enabled_strategies = manager.get_enabled_strategies()

    if "dragon" in enabled_strategies:
        from strategies.dragon_strategy import create_dragon_strategy
        dragon_strategy = create_dragon_strategy()
        # 获取热门板块龙头
        dragon_stocks = []
        for board in ["人工智能", "新能源", "半导体", "医药", "大消费"]:
            dragons = dragon_strategy.identify_dragon_stocks(board, top_n=3)
            for d in dragons:
                dragon_stocks.append({
                    "ts_code": d.ts_code,
                    "stock_name": d.stock_name,
                    "dragon_score": d.confidence == "高" and 85 or (d.confidence == "中" and 65 or 50),
                })

    if "limit_up" in enabled_strategies:
        from strategies.limit_up import create_limit_up_analyzer
        limit_up_analyzer = create_limit_up_analyzer()
        limit_up_list = limit_up_analyzer.get_limit_up_list()
        limit_up_stocks = []
        for s in limit_up_list:
            strength = limit_up_analyzer.analyze_limit_up_strength(s.ts_code)
            limit_up_stocks.append({
                "ts_code": s.ts_code,
                "stock_name": s.stock_name,
                "limit_up_score": strength.get("score", 50) if strength else 50,
            })

    if "ml" in enabled_strategies or enable_ml:
        try:
            from ml_models import get_ml_score
            ml_stocks = []
            for stock in comprehensive_stocks[:top_n]:
                # 获取价格数据
                price_df = screener.fetcher.get_stock_prices(stock["ts_code"], count=60)
                if not price_df.empty:
                    ml_result = get_ml_score(price_df)
                    ml_stocks.append({
                        "ts_code": stock["ts_code"],
                        "stock_name": stock["stock_name"],
                        "ml_score": ml_result.get("ml_score", 50),
                    })
        except Exception as e:
            logger.warning(f"ML 评分失败：{e}")
            ml_stocks = []

    if "seat" in enabled_strategies:
        from strategies.seat_analysis import create_seat_analyzer
        seat_analyzer = create_seat_analyzer()
        lhb_stocks = seat_analyzer.get_lhb_list()
        seat_stocks = []
        for s in lhb_stocks:
            seat_stocks.append({
                "ts_code": s.ts_code,
                "stock_name": s.stock_name,
                "seat_score": s.seat_score,
            })

    # 合并股票列表
    candidates = manager.merge_stock_lists(
        comprehensive_stocks,
        dragon_stocks,
        limit_up_stocks,
        ml_stocks,
        seat_stocks,
    )

    # 取前 N 只
    final_stocks = candidates[:top_n]

    # 显示结果
    print(f"\n【选股结果】")
    print(f"{'排名':<6}{'代码':<12}{'名称':<12}{'综合':<8}{'龙头':<8}{'涨停':<8}{'ML':<8}{'席位':<8}{'最终':<8}")
    print("-" * 86)

    for c in final_stocks:
        print(f"#{c.rank:<5}{c.ts_code:<12}{c.stock_name:<12}"
              f"{c.comprehensive_score:<8.1f}{c.dragon_score:<8.1f}"
              f"{c.limit_up_score:<8.1f}{c.ml_score:<8.1f}"
              f"{c.seat_score:<8.1f}{c.final_score:<8.1f}")

    print("-" * 86)
    print(f"\n{'='*60}")
    print("免责声明：选股结果仅供参考，不构成投资建议。")
    print("股市有风险，投资需谨慎。")
    print(f"{'='*60}\n")


def run_strategy_rotation(market_condition: str = "normal"):
    """
    执行策略轮动

    Args:
        market_condition: 市场环境 (bull/bear/normal/volatile)
    """
    print(f"\n{'='*60}")
    print("A 股选股系统 - 策略轮动")
    print(f"{'='*60}")
    print(f"市场环境：{market_condition}")
    print(f"{'='*60}\n")

    from selector.strategy_manager import create_strategy_manager

    # 创建策略管理器
    manager = create_strategy_manager()

    # 设置市场环境
    manager.set_market_condition(market_condition)

    # 加载平衡型策略作为起点
    manager.load_preset("balanced")

    print("【当前策略配置】")
    for name, config in manager.strategies.items():
        if config.enabled:
            perf = manager.strategy_performance.get(name, {}).get("performance", 0)
            print(f"  {name}: 权重={config.weight:.2%}, 性能={perf:.2f}")

    # 模拟策略性能（实际使用中应该从回测或实盘获取）
    print("\n【模拟策略性能更新】")
    import random
    for name in manager.get_enabled_strategies():
        # 模拟性能（夏普比率）
        simulated_perf = random.uniform(0.5, 2.5)
        manager.update_strategy_performance(name, simulated_perf)
        print(f"  {name}: {simulated_perf:.2f}")

    # 执行策略轮动
    print("\n【执行策略轮动】")
    manager.run_strategy_rotation()

    # 显示轮动后配置
    print("\n【轮动后策略配置】")
    for name, config in manager.strategies.items():
        if config.enabled:
            print(f"  {name}: 权重={config.weight:.2%}")

    # 显示轮动历史
    history = manager.get_rotation_history(1)
    if history:
        print("\n【最近轮动记录】")
        last = history[0]
        print(f"  时间：{last['timestamp']}")
        print(f"  选中策略：{', '.join(last['selected_strategies'])}")
        print(f"  市场环境：{last['market_condition']}")

    print(f"\n{'='*60}")
    print("提示：实际使用时，策略性能应从回测或实盘数据中计算获取。")
    print(f"{'='*60}\n")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="A 股选股系统 - 基于基本面、技术面、资金面、热点的综合选股工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --date 2026-03-09 --top-n 10
  %(prog)s --backtest --start 20250101 --end 20260301
  %(prog)s --tracking 2026-03-09
  %(prog)s --position --suggestion  # 查看持仓分析 + 操作建议
  %(prog)s --dragon --board 人工智能  # 查看人工智能板块龙头
  %(prog)s --limit-up  # 查看涨停板统计
  %(prog)s --limit-up-detail --code 000001  # 查看个股涨停强度
  %(prog)s --seat  # 查看龙虎榜席位分析
  %(prog)s --rotation --market-condition bull  # 执行策略轮动（牛市模式）

策略模式:
  %(prog)s --strategy comprehensive  # 综合评分（原有系统）
  %(prog)s --strategy dragon  # 龙头战法
  %(prog)s --strategy ml  # ML 选股
  %(prog)s --strategy combined  # 多策略融合
  %(prog)s --strategy conservative  # 稳健型（仅综合评分）
  %(prog)s --strategy aggressive  # 激进型（龙头 + 涨停）
  %(prog)s --strategy balanced  # 平衡型（综合 + 龙头+ML）
  %(prog)s --strategy all_in  # 全策略融合
        """,
    )

    # 选股参数
    parser.add_argument(
        "--date", "-d",
        type=str,
        default=None,
        help="选股日期 (YYYYMMDD)，默认为今天",
    )
    parser.add_argument(
        "--top-n", "-n",
        type=int,
        default=10,
        help="选出股票数量 (默认：10)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        choices=["json", "html", "all", "none"],
        default="json",
        help="输出格式 (默认：json)",
    )

    # 回测参数
    parser.add_argument(
        "--backtest", "-b",
        action="store_true",
        help="运行历史回测",
    )
    parser.add_argument(
        "--start",
        type=str,
        default="20250101",
        help="回测开始日期 (默认：20250101)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="回测结束日期 (默认：今天)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=100000,
        help="回测初始资金 (默认：100000)",
    )
    parser.add_argument(
        "--holding-period",
        type=int,
        default=15,
        help="回测持有周期 (天，默认：15)",
    )

    # 追踪参数
    parser.add_argument(
        "--tracking", "-t",
        type=str,
        default=None,
        help="查看选股追踪 (日期：YYYYMMDD)",
    )

    # 持仓分析参数
    parser.add_argument(
        "--position", "-p",
        action="store_true",
        help="分析持仓",
    )
    parser.add_argument(
        "--suggestion", "-s",
        action="store_true",
        help="显示操作建议（与 --position 联用）",
    )
    parser.add_argument(
        "--risk", "-r",
        action="store_true",
        help="显示风险警示（与 --position 联用）",
    )
    parser.add_argument(
        "--auto-login",
        action="store_true",
        help="自动登录交易账户（默认手动）",
    )

    # 龙头战法参数
    parser.add_argument(
        "--dragon",
        action="store_true",
        help="显示龙头股",
    )
    parser.add_argument(
        "--board",
        type=str,
        default=None,
        help="板块名称（与 --dragon 联用）",
    )

    # 涨停板分析参数
    parser.add_argument(
        "--limit-up",
        action="store_true",
        help="显示涨停板统计",
    )
    parser.add_argument(
        "--limit-up-detail",
        type=str,
        metavar="CODE",
        help="查看个股涨停强度（传入股票代码）",
    )

    # 龙虎榜分析参数
    parser.add_argument(
        "--seat",
        action="store_true",
        help="显示龙虎榜席位分析",
    )

    # 舆情分析参数
    parser.add_argument(
        "--sentiment",
        type=str,
        metavar="CODE",
        help="分析个股舆情情绪（传入股票代码）",
    )
    parser.add_argument(
        "--sentiment-bert",
        action="store_true",
        help="使用 BERT 深度学习模型进行舆情分析（与 --sentiment 联用）",
    )
    parser.add_argument(
        "--sentiment-gpu",
        action="store_true",
        help="使用 GPU 加速 BERT 模型（与 --sentiment-bert 联用）",
    )

    # 策略选择参数
    parser.add_argument(
        "--strategy",
        type=str,
        default="comprehensive",
        choices=["comprehensive", "dragon", "limit_up", "ml", "seat", "combined", "conservative", "aggressive", "balanced", "all_in"],
        help="选股策略模式 (默认：comprehensive)",
    )
    parser.add_argument(
        "--ml-score",
        action="store_true",
        help="启用 ML 评分（与 --strategy 联用）",
    )

    # 策略轮动参数
    parser.add_argument(
        "--rotation",
        action="store_true",
        help="执行策略轮动",
    )
    parser.add_argument(
        "--market-condition",
        type=str,
        choices=["bull", "bear", "normal", "volatile"],
        default="normal",
        help="市场环境设置（与 --rotation 联用）",
    )

    # 其他参数
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )

    args = parser.parse_args()

    # 处理不同模式
    if args.rotation:
        run_strategy_rotation(args.market_condition)
    elif args.backtest:
        end_date = args.end or datetime.now().strftime("%Y%m%d")
        run_backtest(
            args.start,
            end_date,
            args.capital,
            args.holding_period,
        )
    elif args.sentiment:
        show_sentiment_analysis(
            args.sentiment,
            use_bert=args.sentiment_bert,
            use_gpu=args.sentiment_gpu
        )
    elif args.limit_up_detail:
        show_limit_up_detail(args.limit_up_detail)
    elif args.limit_up:
        show_limit_up_analysis()
    elif args.dragon:
        show_dragon_stocks(args.board)
    elif args.seat:
        show_seat_analysis()
    elif args.position:
        analyze_position(
            show_suggestion=args.suggestion,
            show_risk=args.risk or args.suggestion,
            auto_login=args.auto_login,
        )
    elif args.tracking:
        show_tracking(args.tracking)
    elif args.date or args.strategy != "comprehensive":
        select_stocks_with_strategy(
            args.date or datetime.now().strftime("%Y%m%d"),
            args.top_n,
            args.output,
            args.strategy,
            enable_ml=args.ml_score,
        )
    else:
        # 默认：执行今日选股
        today = datetime.now().strftime("%Y%m%d")
        select_stocks(today, args.top_n, args.output)


if __name__ == "__main__":
    main()
