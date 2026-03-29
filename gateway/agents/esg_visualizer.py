# esg_visualizer.py — ESG 可视化数据生成
# 职责：将 ESGScoreReport 转换为前端可以直接使用的可视化数据格式
# 支持多种图表：雷达图、柱状图、热力图、趋势图、仪表图

from datetime import datetime
from typing import Dict, Any, List, Optional
from gateway.agents.esg_scorer import ESGScoreReport
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class ESGVisualizer:
    """
    ESG 可视化数据生成器
    将ESGScoreReport转换为前端所需的各种图表数据格式
    """

    @staticmethod
    def generate_report_visual(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成完整的可视化数据包

        Returns:
            包含所有图表数据的字典，可直接传给前端渲染
        """
        visualizations = {
            "radar": ESGVisualizer._generate_radar_data(report),
            "dimension_bars": ESGVisualizer._generate_dimension_bars(report),
            "metric_details": ESGVisualizer._generate_metric_details(report),
            "heatmap": ESGVisualizer._generate_heatmap_data(report),
            "gauges": ESGVisualizer._generate_gauge_data(report),
            "summary_stats": ESGVisualizer._generate_summary_stats(report),
        }

        return visualizations

    @staticmethod
    def _generate_radar_data(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成雷达图数据
        用于展示 E/S/G 三维评分
        """
        return {
            "type": "radar",
            "title": f"{report.company_name} - ESG 三维评分",
            "data": {
                "labels": ["环境 (E)", "社会 (S)", "治理 (G)"],
                "datasets": [
                    {
                        "label": report.company_name,
                        "data": [
                            report.e_scores.overall_score,
                            report.s_scores.overall_score,
                            report.g_scores.overall_score,
                        ],
                        "borderColor": "#4F46E5",
                        "backgroundColor": "rgba(79, 70, 229, 0.1)",
                        "pointBackgroundColor": "#4F46E5",
                    }
                ]
            },
            "options": {
                "scales": {
                    "r": {
                        "beginAtZero": True,
                        "max": 100,
                        "ticks": {"stepSize": 20}
                    }
                }
            }
        }

    @staticmethod
    def _generate_dimension_bars(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成维度柱状图
        展示 E/S/G 各维度内的 5 个指标详情
        """
        dimensions = [
            ("E", report.e_scores, "环境维度"),
            ("S", report.s_scores, "社会维度"),
            ("G", report.g_scores, "治理维度"),
        ]

        datasets = []
        all_labels = set()

        for dim_code, dim_scores, dim_name in dimensions:
            scores = []
            labels = []
            for metric_key, metric in dim_scores.metrics.items():
                scores.append(metric.score)
                labels.append(metric.name)
                all_labels.add(metric.name)

            datasets.append({
                "label": dim_name,
                "data": scores,
                "backgroundColor": {
                    "E": "#10B981",  # Green
                    "S": "#3B82F6",  # Blue
                    "G": "#F59E0B",  # Amber
                }[dim_code],
            })

        return {
            "type": "bar",
            "title": "ESG 各维度指标详情",
            "data": {
                "labels": list(all_labels),
                "datasets": datasets,
            },
            "options": {
                "indexAxis": "y",
                "scales": {
                    "x": {
                        "beginAtZero": True,
                        "max": 100,
                    }
                }
            }
        }

    @staticmethod
    def _generate_metric_details(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成指标详情列表
        返回所有指标的详细信息用于表格展示
        """
        metrics_list = []

        for dim_code, dim_scores in [
            ("E", report.e_scores),
            ("S", report.s_scores),
            ("G", report.g_scores),
        ]:
            for metric_key, metric in dim_scores.metrics.items():
                metrics_list.append({
                    "dimension": dim_code,
                    "metric_key": metric_key,
                    "metric_name": metric.name,
                    "score": metric.score,
                    "weight": metric.weight,
                    "trend": metric.trend,
                    "reasoning": metric.reasoning,
                    "data_source": metric.data_source,
                    "rating": ESGVisualizer._get_metric_rating(metric.score),
                })

        return {
            "type": "table",
            "title": "指标详细评分",
            "data": metrics_list,
            "columns": [
                {"field": "dimension", "headerName": "维度", "width": 80},
                {"field": "metric_name", "headerName": "指标", "width": 150},
                {"field": "score", "headerName": "评分", "width": 100},
                {"field": "weight", "headerName": "权重", "width": 80},
                {"field": "trend", "headerName": "趋势", "width": 80},
                {"field": "rating", "headerName": "评级", "width": 100},
                {"field": "reasoning", "headerName": "评分理由", "width": 300},
            ]
        }

    @staticmethod
    def _generate_heatmap_data(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成热力图数据
        用于展示所有指标的评分分布
        """
        # 准备矩阵数据
        matrix = []
        dimensions = ["E", "S", "G"]
        dim_objects = [report.e_scores, report.s_scores, report.g_scores]

        for dim_code, dim_scores in zip(dimensions, dim_objects):
            row = []
            for metric_key, metric in dim_scores.metrics.items():
                row.append({
                    "value": metric.score,
                    "name": metric.name,
                    "dimension": dim_code,
                })
            matrix.append(row)

        return {
            "type": "heatmap",
            "title": "ESG 评分热力分布",
            "data": {
                "matrix": matrix,
                "maxValue": 100,
                "minValue": 0,
            },
            "colorScale": [
                "#FF6B6B",  # Red (0-25)
                "#FFA500",  # Orange (25-50)
                "#FFD700",  # Yellow (50-75)
                "#90EE90",  # Light Green (75-100)
            ]
        }

    @staticmethod
    def _generate_gauge_data(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成仪表盘数据
        展示总体评分和各维度评分的仪表
        """
        gauges = []

        # 总体评分仪表
        gauges.append({
            "title": "综合ESG评分",
            "value": report.overall_score,
            "max": 100,
            "color": ESGVisualizer._get_score_color(report.overall_score),
            "label": ESGVisualizer._get_rating_text(report.overall_score),
        })

        # 三维评分仪表
        for label, scores, color in [
            ("环境评分", report.e_scores.overall_score, "#10B981"),
            ("社会评分", report.s_scores.overall_score, "#3B82F6"),
            ("治理评分", report.g_scores.overall_score, "#F59E0B"),
        ]:
            gauges.append({
                "title": label,
                "value": scores,
                "max": 100,
                "color": color,
                "label": ESGVisualizer._get_rating_text(scores),
            })

        return {
            "type": "gauge",
            "title": "评分仪表",
            "data": gauges,
        }

    @staticmethod
    def _generate_summary_stats(report: ESGScoreReport) -> Dict[str, Any]:
        """
        生成摘要统计信息
        """
        return {
            "type": "summary",
            "company_name": report.company_name,
            "ticker": report.ticker,
            "industry": report.industry,
            "overall_score": report.overall_score,
            "overall_rating": ESGVisualizer._get_rating_text(report.overall_score),
            "overall_trend": report.overall_trend,
            "peer_rank": report.peer_rank,
            "industry_position": report.industry_position,
            "confidence_score": f"{report.confidence_score*100:.0f}%",
            "assessment_date": report.assessment_date.isoformat(),
            "key_strengths": report.key_strengths,
            "key_weaknesses": report.key_weaknesses,
            "recommendations": report.recommendations,
            "data_sources": report.data_sources,
            "dimension_scores": {
                "e": {
                    "score": report.e_scores.overall_score,
                    "rating": ESGVisualizer._get_rating_text(report.e_scores.overall_score),
                },
                "s": {
                    "score": report.s_scores.overall_score,
                    "rating": ESGVisualizer._get_rating_text(report.s_scores.overall_score),
                },
                "g": {
                    "score": report.g_scores.overall_score,
                    "rating": ESGVisualizer._get_rating_text(report.g_scores.overall_score),
                }
            }
        }

    @staticmethod
    def _get_metric_rating(score: float) -> str:
        """获取指标评级"""
        if score >= 80:
            return "⭐⭐⭐⭐⭐ 优秀"
        elif score >= 60:
            return "⭐⭐⭐⭐ 良好"
        elif score >= 40:
            return "⭐⭐⭐ 一般"
        elif score >= 20:
            return "⭐⭐ 需改进"
        else:
            return "⭐ 不足"

    @staticmethod
    def _get_rating_text(score: float) -> str:
        """根据分数获取评级文本"""
        if score >= 80:
            return "优秀"
        elif score >= 60:
            return "良好"
        elif score >= 40:
            return "一般"
        elif score >= 20:
            return "需改进"
        else:
            return "不足"

    @staticmethod
    def _get_score_color(score: float) -> str:
        """根据分数获取颜色"""
        if score >= 80:
            return "#10B981"  # Green
        elif score >= 60:
            return "#3B82F6"  # Blue
        elif score >= 40:
            return "#F59E0B"  # Amber
        elif score >= 20:
            return "#EF4444"  # Red
        else:
            return "#7F1D1D"  # Dark Red

    @staticmethod
    def generate_html_report(report: ESGScoreReport, visualizations: Dict[str, Any]) -> str:
        """
        生成可独立查看的 HTML 报告
        包含所有可视化和分析内容
        """
        html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ESG 评分报告 - {report.company_name}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: #f5f7fa; }}

        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            border-radius: 12px;
            margin-bottom: 30px;
        }}

        h1 {{ font-size: 2em; margin-bottom: 10px; }}
        .subtitle {{ font-size: 0.9em; opacity: 0.9; }}

        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .card h3 {{ color: #333; margin-bottom: 10px; }}
        .card-value {{ font-size: 1.8em; font-weight: bold; color: #667eea; }}
        .card-label {{ color: #666; font-size: 0.9em; }}

        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .chart-title {{ font-weight: bold; margin-bottom: 15px; color: #333; }}

        .strengths-weaknesses {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}

        .strength-box, .weakness-box {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .strength-box h3 {{ color: #10B981; }}
        .weakness-box h3 {{ color: #EF4444; }}

        .strength-box li {{ border-left: 3px solid #10B981; padding-left: 10px; margin-bottom: 10px; }}
        .weakness-box li {{ border-left: 3px solid #EF4444; padding-left: 10px; margin-bottom: 10px; }}

        .footer {{
            text-align: center;
            color: #999;
            font-size: 0.85em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}

        @media print {{
            body {{ background: white; }}
            .card {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{report.company_name}</h1>
            <p class="subtitle">ESG 综合评分报告 | {report.assessment_date.strftime('%Y年%m月%d日')}</p>
        </header>

        <div class="summary-grid">
            <div class="card">
                <h3>综合评分</h3>
                <div class="card-value">{report.overall_score:.1f}</div>
                <div class="card-label">{ESGVisualizer._get_rating_text(report.overall_score)}</div>
            </div>
            <div class="card">
                <h3>环境维度</h3>
                <div class="card-value">{report.e_scores.overall_score:.1f}</div>
                <div class="card-label">E Score</div>
            </div>
            <div class="card">
                <h3>社会维度</h3>
                <div class="card-value">{report.s_scores.overall_score:.1f}</div>
                <div class="card-label">S Score</div>
            </div>
            <div class="card">
                <h3>治理维度</h3>
                <div class="card-value">{report.g_scores.overall_score:.1f}</div>
                <div class="card-label">G Score</div>
            </div>
        </div>

        <div class="strengths-weaknesses">
            <div class="strength-box">
                <h3>✓ 核心优势</h3>
                <ul>
                    {"".join(f"<li>{s}</li>" for s in report.key_strengths)}
                </ul>
            </div>
            <div class="weakness-box">
                <h3>✗ 改进方向</h3>
                <ul>
                    {"".join(f"<li>{w}</li>" for w in report.key_weaknesses)}
                </ul>
            </div>
        </div>

        <div class="footer">
            <p>报告由 ESG 智能分析系统自动生成 | 信心度: {report.confidence_score*100:.0f}%</p>
        </div>
    </div>
</body>
</html>
"""
        return html
