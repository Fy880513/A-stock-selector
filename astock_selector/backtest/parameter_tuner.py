"""
参数调优模块

提供更高效的参数搜索和评估功能
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from backtest.engine import create_backtest_engine, BacktestResult
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ParameterTuningResult:
    """参数调优结果"""
    best_params: Dict[str, float]
    best_score: float
    best_result: BacktestResult
    all_results: List[Dict]
    optimization_time: float
    parameter_importance: Optional[Dict[str, float]] = None


class ParameterTuner:
    """参数调优器"""

    def __init__(
        self,
        initial_capital: float = 100000,
        max_workers: int = None,
    ):
        """
        Args:
            initial_capital: 初始资金
            max_workers: 并行工作线程数
        """
        self.initial_capital = initial_capital
        self.max_workers = max_workers or multiprocessing.cpu_count()

    def _evaluate_params(
        self,
        param_dict: Dict[str, float],
        start_date: str,
        end_date: str,
        benchmark_code: str,
        objective: str,
    ) -> Dict:
        """
        评估单个参数组合

        Returns:
            dict: 评估结果
        """
        try:
            # 创建回测引擎
            engine = create_backtest_engine(
                initial_capital=self.initial_capital,
                holding_period=int(param_dict.get('holding_period', 15)),
                top_n=int(param_dict.get('top_n', 10)),
                selection_strategy=param_dict.get('selection_strategy', 'comprehensive'),
                strategy_weights=param_dict.get('strategy_weights'),
            )

            # 运行回测
            result = engine.run_backtest(start_date, end_date, benchmark_code)

            # 计算目标值
            if objective == 'sharpe_ratio':
                score = result.metrics.sharpe_ratio
            elif objective == 'total_return':
                score = result.metrics.total_return
            elif objective == 'sortino_ratio':
                score = result.metrics.sortino_ratio
            elif objective == 'win_rate':
                score = result.metrics.win_rate
            elif objective == 'profit_loss_ratio':
                score = result.metrics.profit_loss_ratio
            elif objective == 'max_drawdown':
                score = -result.metrics.max_drawdown  # 取负值，因为我们要最大化得分
            else:
                score = result.metrics.sharpe_ratio

            return {
                'params': param_dict,
                'score': score,
                'result': result,
                'error': None,
            }
        except Exception as e:
            logger.error(f"参数评估失败 {param_dict}：{e}")
            return {
                'params': param_dict,
                'score': -float('inf'),
                'result': None,
                'error': str(e),
            }

    def grid_search(
        self,
        start_date: str,
        end_date: str,
        param_grid: Dict[str, List[float]],
        benchmark_code: str = "000300.SH",
        objective: str = "sharpe_ratio",
    ) -> ParameterTuningResult:
        """
        网格搜索参数优化

        Args:
            start_date: 开始日期
            end_date: 结束日期
            param_grid: 参数网格
            benchmark_code: 基准指数
            objective: 优化目标

        Returns:
            ParameterTuningResult: 调优结果
        """
        import itertools
        import time

        start_time = time.time()
        logger.info(f"开始网格搜索参数优化，目标：{objective}")

        # 生成参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(itertools.product(*param_values))

        logger.info(f"总参数组合数：{len(param_combinations)}")

        # 并行评估参数组合
        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for params in param_combinations:
                param_dict = dict(zip(param_names, params))
                future = executor.submit(
                    self._evaluate_params,
                    param_dict,
                    start_date,
                    end_date,
                    benchmark_code,
                    objective,
                )
                futures.append(future)

            # 收集结果
            for i, future in enumerate(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if i % 10 == 0:
                        logger.info(f"已完成 {i+1}/{len(futures)} 个参数组合评估")
                except Exception as e:
                    logger.error(f"获取结果失败：{e}")

        # 找出最优结果
        best_result = max(results, key=lambda x: x['score'])

        # 计算参数重要性
        parameter_importance = self._calculate_parameter_importance(results, param_names)

        optimization_time = time.time() - start_time
        logger.info(f"参数优化完成，耗时：{optimization_time:.2f} 秒")

        return ParameterTuningResult(
            best_params=best_result['params'],
            best_score=best_result['score'],
            best_result=best_result['result'],
            all_results=results,
            optimization_time=optimization_time,
            parameter_importance=parameter_importance,
        )

    def genetic_algorithm(
        self,
        start_date: str,
        end_date: str,
        param_ranges: Dict[str, Tuple[float, float]],
        benchmark_code: str = "000300.SH",
        objective: str = "sharpe_ratio",
        population_size: int = 20,
        generations: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.8,
    ) -> ParameterTuningResult:
        """
        遗传算法参数优化

        Args:
            start_date: 开始日期
            end_date: 结束日期
            param_ranges: 参数范围
            benchmark_code: 基准指数
            objective: 优化目标
            population_size: 种群大小
            generations: 进化代数
            mutation_rate: 变异率
            crossover_rate: 交叉率

        Returns:
            ParameterTuningResult: 调优结果
        """
        import time
        import random

        start_time = time.time()
        logger.info(f"开始遗传算法参数优化，目标：{objective}")

        # 初始化种群
        population = []
        param_names = list(param_ranges.keys())
        for _ in range(population_size):
            individual = {}
            for param, (min_val, max_val) in param_ranges.items():
                if isinstance(min_val, int) and isinstance(max_val, int):
                    individual[param] = random.randint(min_val, max_val)
                else:
                    individual[param] = random.uniform(min_val, max_val)
            population.append(individual)

        # 进化过程
        all_results = []
        best_individual = None
        best_score = -float('inf')

        for generation in range(generations):
            # 评估种群
            logger.info(f"第 {generation+1}/{generations} 代，种群大小：{len(population)}")

            # 并行评估
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for individual in population:
                    future = executor.submit(
                        self._evaluate_params,
                        individual,
                        start_date,
                        end_date,
                        benchmark_code,
                        objective,
                    )
                    futures.append(future)

                # 收集结果
                generation_results = []
                for future in futures:
                    try:
                        result = future.result()
                        generation_results.append(result)
                        all_results.append(result)
                    except Exception as e:
                        logger.error(f"获取结果失败：{e}")

            # 排序并选择
            generation_results.sort(key=lambda x: x['score'], reverse=True)

            # 更新最优结果
            if generation_results and generation_results[0]['score'] > best_score:
                best_score = generation_results[0]['score']
                best_individual = generation_results[0]
                logger.info(f"第 {generation+1} 代找到更优参数：{best_individual['params']}, 得分：{best_score:.4f}")

            # 选择父代
            selected = generation_results[:population_size // 2]
            parents = [r['params'] for r in selected]

            # 交叉和变异
            new_population = []
            while len(new_population) < population_size:
                # 选择父母
                if random.random() < crossover_rate and len(parents) >= 2:
                    parent1, parent2 = random.sample(parents, 2)
                    # 交叉
                    child = {}
                    for param in param_names:
                        if random.random() < 0.5:
                            child[param] = parent1[param]
                        else:
                            child[param] = parent2[param]
                else:
                    # 直接复制
                    child = random.choice(parents).copy()

                # 变异
                for param, (min_val, max_val) in param_ranges.items():
                    if random.random() < mutation_rate:
                        if isinstance(min_val, int) and isinstance(max_val, int):
                            child[param] = random.randint(min_val, max_val)
                        else:
                            child[param] = random.uniform(min_val, max_val)

                new_population.append(child)

            population = new_population

        # 计算参数重要性
        parameter_importance = self._calculate_parameter_importance(all_results, param_names)

        optimization_time = time.time() - start_time
        logger.info(f"遗传算法参数优化完成，耗时：{optimization_time:.2f} 秒")

        return ParameterTuningResult(
            best_params=best_individual['params'],
            best_score=best_individual['score'],
            best_result=best_individual['result'],
            all_results=all_results,
            optimization_time=optimization_time,
            parameter_importance=parameter_importance,
        )

    def _calculate_parameter_importance(
        self,
        results: List[Dict],
        param_names: List[str],
    ) -> Dict[str, float]:
        """
        计算参数重要性

        Returns:
            dict: 参数重要性
        """
        if not results or not param_names:
            return {}

        importance = {}
        for param in param_names:
            # 收集参数值和得分
            param_values = []
            scores = []
            for result in results:
                if result['score'] > -float('inf'):
                    param_values.append(result['params'].get(param, 0))
                    scores.append(result['score'])

            if len(param_values) > 1:
                # 计算相关系数
                correlation = np.corrcoef(param_values, scores)[0, 1]
                importance[param] = abs(correlation)
            else:
                importance[param] = 0.0

        # 归一化
        total = sum(importance.values())
        if total > 0:
            for param in importance:
                importance[param] = importance[param] / total

        return importance

    def analyze_results(
        self,
        tuning_result: ParameterTuningResult,
    ) -> pd.DataFrame:
        """
        分析调优结果

        Returns:
            DataFrame: 结果分析
        """
        data = []
        for result in tuning_result.all_results:
            if result['score'] > -float('inf'):
                row = result['params'].copy()
                row['score'] = result['score']
                if result['result']:
                    row['total_return'] = result['result'].metrics.total_return
                    row['sharpe_ratio'] = result['result'].metrics.sharpe_ratio
                    row['max_drawdown'] = result['result'].metrics.max_drawdown
                    row['win_rate'] = result['result'].metrics.win_rate
                data.append(row)

        return pd.DataFrame(data)

    def plot_parameter_importance(
        self,
        tuning_result: ParameterTuningResult,
    ):"""
        绘制参数重要性图
        """
        if not tuning_result.parameter_importance:
            logger.warning("没有参数重要性数据")
            return

        import matplotlib.pyplot as plt

        params = list(tuning_result.parameter_importance.keys())
        importance = list(tuning_result.parameter_importance.values())

        plt.figure(figsize=(10, 6))
        plt.barh(params, importance)
        plt.xlabel('重要性')
        plt.ylabel('参数')
        plt.title('参数重要性分析')
        plt.tight_layout()
        plt.show()

    def print_tuning_result(
        self,
        tuning_result: ParameterTuningResult,
    ):
        """
        打印调优结果
        """
        print("\n" + "=" * 60)
        print("参数调优结果")
        print("=" * 60)
        print(f"最优参数：{tuning_result.best_params}")
        print(f"最优得分：{tuning_result.best_score:.4f}")
        print(f"优化耗时：{tuning_result.optimization_time:.2f} 秒")
        
        if tuning_result.best_result:
            m = tuning_result.best_result.metrics
            print("\n最优结果绩效:")
            print(f"  总收益率：{m.total_return:.2%}")
            print(f"  夏普比率：{m.sharpe_ratio:.2f}")
            print(f"  最大回撤：{m.max_drawdown:.2%}")
            print(f"  胜率：{m.win_rate:.2%}")
            print(f"  盈亏比：{m.profit_loss_ratio:.2f}")
        
        if tuning_result.parameter_importance:
            print("\n参数重要性:")
            for param, importance in sorted(
                tuning_result.parameter_importance.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"  {param}: {importance:.4f}")
        
        print("=" * 60)


def create_parameter_tuner(
    initial_capital: float = 100000,
    max_workers: int = None,
) -> ParameterTuner:
    """创建参数调优器实例"""
    return ParameterTuner(initial_capital, max_workers)
