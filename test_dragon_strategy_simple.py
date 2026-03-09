"""
简化版测试龙头战法策略核心逻辑
"""
import sys
import os
import random
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'astock_selector'))

# 模拟数据获取器
class MockFetcher:
    def get_industry_list(self):
        import pandas as pd
        return pd.DataFrame({'name': ['人工智能', '新能源', '半导体', '医药', '大消费']})
    
    def get_industry_stocks(self, board_name):
        import pandas as pd
        # 模拟每个板块有20只股票
        stocks = [f'{i:06d}' for i in range(1, 21)]
        return pd.DataFrame({'code': stocks})
    
    def get_industry_history(self, board_name, period="日"):
        import pandas as pd
        import numpy as np
        # 模拟板块历史数据
        dates = pd.date_range(end=datetime.now(), periods=10)
        data = {
            '交易日': dates,
            '收盘价': np.random.uniform(100, 200, size=10)
        }
        return pd.DataFrame(data)
    
    def get_stock_prices(self, ts_code, count=1):
        import pandas as pd
        import numpy as np
        # 模拟股票价格数据
        dates = pd.date_range(end=datetime.now(), periods=count)
        data = {
            'trade_date': dates,
            'close': np.random.uniform(10, 100, size=count),
            'pct_chg': np.random.uniform(-10, 10, size=count),
            'vol': np.random.uniform(1000000, 10000000, size=count),
            'amount': np.random.uniform(10000000, 100000000, size=count),
            'circ_mv': np.random.uniform(1000000000, 10000000000, size=count)
        }
        return pd.DataFrame(data)

# 模拟数据获取函数
def mock_get_data_fetcher():
    return MockFetcher()

# 替换原始的get_data_fetcher
import sys
import importlib.util

# 动态替换data.fetcher模块
spec = importlib.util.spec_from_file_location("data.fetcher", os.path.join(os.path.dirname(__file__), 'astock_selector', 'data', 'fetcher.py'))
data_fetcher = importlib.util.module_from_spec(spec)
sys.modules["data.fetcher"] = data_fetcher
data_fetcher.get_data_fetcher = mock_get_data_fetcher
spec.loader.exec_module(data_fetcher)

# 现在导入策略模块
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
    test_board = "人工智能"
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
