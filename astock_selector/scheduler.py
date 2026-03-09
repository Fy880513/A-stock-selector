"""
定时任务调度器

每个交易日 17:00 自动更新数据并选股
"""
import schedule
import time
from datetime import datetime
from pathlib import Path

from selector.screener import get_screener
from report.generator import create_report_generator
from data.storage import get_storage
from utils.logger import get_logger

logger = get_logger(__name__)


def job():
    """每日选股任务"""
    logger.info("开始执行每日选股任务")

    try:
        # 执行选股
        screener = get_screener()
        result = screener.select_with_portfolio(top_n=10)

        if result["stocks"]:
            # 生成报告
            generator = create_report_generator()
            today = datetime.now().strftime("%Y%m%d")

            # 保存 JSON
            json_path = generator.generate_json_report(
                today,
                result["stocks"],
                result["portfolio"],
            )
            logger.info(f"JSON 报告已保存：{json_path}")

            # 保存 HTML
            html_path = generator.generate_html_report(
                today,
                result["stocks"],
                result["portfolio"],
            )
            logger.info(f"HTML 报告已保存：{html_path}")

            # 保存到数据库
            storage = get_storage()
            import pandas as pd
            df = pd.DataFrame(result["stocks"])
            df["select_date"] = today
            storage.save_selection_result(df)

            logger.info(f"选股完成，共选出 {len(result['stocks'])} 只股票")
        else:
            logger.warning(f"选股失败：{result.get('message', '未知错误')}")

    except Exception as e:
        logger.error(f"选股任务失败：{e}")


def is_trading_day() -> bool:
    """判断是否为交易日（简化版本）"""
    today = datetime.now()
    # 跳过周末
    if today.weekday() >= 5:
        return False
    # 这里可以添加节假日判断逻辑
    return True


def run_scheduler():
    """运行调度器"""
    logger.info("调度器启动")

    # 每日 17:00 执行
    schedule.every().day.at("17:00").do(job)

    # 每周一 9:00 执行（如果周末错过了）
    schedule.every().monday.at("09:00").do(job)

    logger.info("任务已添加到调度器：每个交易日 17:00 执行选股")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    # 立即执行一次
    if is_trading_day():
        job()

    # 启动调度器
    run_scheduler()
