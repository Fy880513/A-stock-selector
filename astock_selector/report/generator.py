"""
报告生成模块

生成 HTML/PDF 选股报告
"""
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from config.settings import OUTPUT_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """报告生成器"""

    def __init__(self):
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(exist_ok=True)

    def generate_html_report(
        self,
        select_date: str,
        stocks: List[Dict],
        portfolio: Dict,
        output_path: Optional[str] = None,
    ) -> str:
        """
        生成 HTML 选股报告

        Args:
            select_date: 选股日期
            stocks: 选股列表
            portfolio: 仓位建议
            output_path: 输出路径（可选）

        Returns:
            str: HTML 文件路径
        """
        if output_path is None:
            output_path = self.output_dir / f"选股报告_{select_date}.html"

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>A 股选股报告 - {select_date}</title>
    <style>
        body {{
            font-family: "Microsoft YaHei", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #1e88e5, #1565c0);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header p {{
            margin: 10px 0 0;
            opacity: 0.9;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .summary-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }}
        .summary-item .value {{
            font-size: 24px;
            font-weight: bold;
            color: #1e88e5;
        }}
        .summary-item .label {{
            font-size: 14px;
            color: #666;
            margin-top: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background: #1e88e5;
            color: white;
            padding: 12px 8px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px 8px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{
            background: #f5f9ff;
        }}
        .rank-1 {{ background: #fff3cd !important; }}
        .rank-2 {{ background: #e2e3f5 !important; }}
        .rank-3 {{ background: #ffe8cc !important; }}
        .score-high {{ color: #28a745; font-weight: bold; }}
        .score-medium {{ color: #ffc107; font-weight: bold; }}
        .score-low {{ color: #dc3545; font-weight: bold; }}
        .position-info {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-top: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .disclaimer {{
            margin-top: 30px;
            padding: 15px;
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
            font-size: 14px;
            color: #856404;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding: 20px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📈 A 股选股报告</h1>
        <p>选股日期：{select_date} | 生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </div>

    <div class="summary">
        <h2>📊 组合概要</h2>
        <div class="summary-grid">
            <div class="summary-item">
                <div class="value">{len(stocks)}</div>
                <div class="label">选股数量</div>
            </div>
            <div class="summary-item">
                <div class="value">¥{portfolio.get('total_amount', 0):,.0f}</div>
                <div class="label">建议仓位</div>
            </div>
            <div class="summary-item">
                <div class="value">{portfolio.get('used_ratio', 0):.0%}</div>
                <div class="label">仓位使用</div>
            </div>
            <div class="summary-item">
                <div class="value">¥{portfolio.get('remaining', 0):,.0f}</div>
                <div class="label">剩余资金</div>
            </div>
        </div>
    </div>

    <div class="position-info">
        <h2>🎯 选股列表</h2>
        <table>
            <thead>
                <tr>
                    <th>排名</th>
                    <th>代码</th>
                    <th>名称</th>
                    <th>综合得分</th>
                    <th>基本面</th>
                    <th>技术面</th>
                    <th>资金面</th>
                    <th>热点面</th>
                    <th>买入价</th>
                    <th>仓位</th>
                    <th>止损价</th>
                    <th>止盈价</th>
                </tr>
            </thead>
            <tbody>
"""

        for stock in stocks:
            rank = stock.get("rank", 0)
            rank_class = f"rank-{rank}" if rank <= 3 else ""

            # 得分颜色
            total_score = stock.get("total_score", 0)
            if total_score >= 75:
                score_class = "score-high"
            elif total_score >= 60:
                score_class = "score-medium"
            else:
                score_class = "score-low"

            html += f"""                <tr class="{rank_class}">
                    <td>#{rank}</td>
                    <td>{stock.get('ts_code', '')}</td>
                    <td>{stock.get('stock_name', '')}</td>
                    <td class="{score_class}">{total_score:.1f}</td>
                    <td>{stock.get('fundamental_score', 0):.1f}</td>
                    <td>{stock.get('technical_score', 0):.1f}</td>
                    <td>{stock.get('capital_flow_score', 0):.1f}</td>
                    <td>{stock.get('hotspot_score', 0):.1f}</td>
                    <td>¥{stock.get('buy_price', 0):.2f}</td>
                    <td>{stock.get('position_ratio', 0):.1f}%</td>
                    <td style="color: #dc3545;">¥{stock.get('stop_loss', 0):.2f}</td>
                    <td style="color: #28a745;">¥{stock.get('stop_profit', 0):.2f}</td>
                </tr>
"""

        html += """            </tbody>
        </table>
    </div>

    <div class="disclaimer">
        <strong>⚠️ 免责声明：</strong>
        本报告仅供学习和研究使用，不构成投资建议。股市有风险，投资需谨慎。
        选股结果基于历史数据分析，不代表未来表现。请结合个人判断进行决策。
    </div>

    <div class="footer">
        <p>Generated by A-Stock Selector | A 股选股系统</p>
    </div>
</body>
</html>
"""

        # 保存文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML 报告已保存：{output_path}")
        return str(output_path)

    def generate_json_report(
        self,
        select_date: str,
        stocks: List[Dict],
        portfolio: Dict,
        output_path: Optional[str] = None,
    ) -> str:
        """
        生成 JSON 报告

        Returns:
            str: JSON 文件路径
        """
        import json

        if output_path is None:
            output_path = self.output_dir / f"选股结果_{select_date}.json"

        report = {
            "select_date": select_date,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stocks": stocks,
            "portfolio": portfolio,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 报告已保存：{output_path}")
        return str(output_path)

    def generate_text_report(
        self,
        select_date: str,
        stocks: List[Dict],
        portfolio: Dict,
    ) -> str:
        """
        生成文本报告

        Returns:
            str: 报告文本
        """
        text = f"""
{'='*60}
A 股选股报告
选股日期：{select_date}
生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}
{'='*60}

【组合概要】
选股数量：{len(stocks)}
建议仓位：¥{portfolio.get('total_amount', 0):,.0f}
仓位使用：{portfolio.get('used_ratio', 0):.0%}
剩余资金：¥{portfolio.get('remaining', 0):,.0f}

【选股列表】
"""

        for stock in stocks:
            text += f"""
#{stock.get('rank', 0)} {stock.get('ts_code', '')} - {stock.get('stock_name', '')}
   综合得分：{stock.get('total_score', 0):.1f}
   基本面：{stock.get('fundamental_score', 0):.1f} | 技术面：{stock.get('technical_score', 0):.1f}
   资金面：{stock.get('capital_flow_score', 0):.1f} | 热点面：{stock.get('hotspot_score', 0):.1f}
   买入价：¥{stock.get('buy_price', 0):.2f}
   建议仓位：{stock.get('position_ratio', 0):.1f}% ({stock.get('target_shares', 0)} 股)
   止损价：¥{stock.get('stop_loss', 0):.2f} | 止盈价：¥{stock.get('stop_profit', 0):.2f}
"""

        text += f"""
{'='*60}
免责声明：本报告仅供参考，不构成投资建议。
股市有风险，投资需谨慎。
{'='*60}
"""

        return text


def create_report_generator() -> ReportGenerator:
    """创建报告生成器实例"""
    return ReportGenerator()
