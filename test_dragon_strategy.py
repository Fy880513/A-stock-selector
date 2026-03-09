"""
测试优化后的龙头战法策略
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'astock_selector'))

from strategies.dragon_strategy import create_dragon_strategy


def test_dragon_strategy():
    """测试龙头战法策略"""
    print("测试龙头战法策略...")
    
    # 创建策略实例
    strategy = create_dragon_strategy()
    
    # 测试获取行业板块列表
    print("\n1. 测试获取行业板块列表:")
    boards = strategy.get_industry_board_list()
    print(f"获取到 {len(boards)} 个板块")
    if boards:
        print(f"前5个板块: {boards[:5]}")
    
    # 测试获取板块成分股
    print("\n2. 测试获取板块成分股:")
    test_board = "人工智能" if "人工智能" in boards else boards[0] if boards else "人工智能"
    stocks = strategy.get_board_stocks(test_board)
    print(f"{test_board} 板块有 {len(stocks)} 只股票")
    if stocks:
        print(f"前5只股票: {stocks[:5]}")
    
    # 测试识别龙头股
    print(f"\n3. 测试识别 {test_board} 板块龙头股:")
    dragons = strategy.identify_dragon_stocks(test_board, top_n=3)
    print(f"识别到 {len(dragons)} 只龙头股")
    
    if dragons:
        print("\n龙头股列表:")
        print(f"{'排名':<6}{'代码':<10}{'名称':<12}{'涨幅':<10}{'连板':<8}{'置信度':<8}{'板块强度':<10}")
        print("-" * 70)
        
        for d in dragons:
            print(f"#{d.rank:<5}{d.ts_code:<10}{d.stock_name:<12}{d.change_pct:>8.2f}%" 
                  f"{d.limit_up_count:>6}板     {d.confidence:<8}{d.board_strength:>9.1f}")
    
    # 测试龙头切换分析
    print(f"\n4. 测试 {test_board} 板块龙头切换分析:")
    switch_info = strategy.find_dragon_switch(test_board)
    
    if switch_info:
        current_dragon = switch_info.get("current_dragon")
        potential_dragon = switch_info.get("potential_dragon")
        switch_signal = switch_info.get("switch_signal")
        analysis = switch_info.get("analysis")
        confidence = switch_info.get("confidence", "低")
        
        print(f"分析结果: {analysis}")
        print(f"切换信号: {'有' if switch_signal else '无'}")
        print(f"置信度: {confidence}")
        
        if current_dragon:
            print(f"当前龙头: {current_dragon.stock_name} ({current_dragon.ts_code})")
        if potential_dragon:
            print(f"潜在新龙头: {potential_dragon.stock_name} ({potential_dragon.ts_code})")
    
    # 测试涨停板分析
    print("\n5. 测试涨停板分析:")
    if stocks:
        test_stock = stocks[0]
        limit_up_info = strategy.analyze_limit_up(test_stock)
        if limit_up_info:
            print(f"股票: {limit_up_info.stock_name} ({limit_up_info.ts_code})")
            print(f"涨停原因: {limit_up_info.limit_up_reason}")
            print(f"强度: {limit_up_info.strength}")
            print(f"封单金额: {limit_up_info.封单_amount:.2f}")
            print(f"封单比例: {limit_up_info.封单_ratio:.2f}%")
            print(f"板块强度: {limit_up_info.board_strength:.1f}")
        else:
            print(f"{test_stock} 未达到涨停或分析失败")
    
    print("\n测试完成！")


if __name__ == "__main__":
    test_dragon_strategy()
