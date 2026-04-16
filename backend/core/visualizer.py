"""
可视化模块 - 多风格专业图表生成
根据查询结果生成图表（折线图、柱状图、饼图、表格等）
支持风格: default(现代简洁), academic(学术), business(商务), minimal(极简),
          dark(暗黑), colorful(多彩), financial(金融专业), elegant(雅致)
"""
import os
import logging
import json
import math
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# 中文字段名映射
# =============================================================================
FIELD_DISPLAY_NAMES = {
    "stock_abbr": "股票简称",
    "stock_code": "股票代码",
    "company_name": "公司名称",
    "report_year": "报告年份",
    "report_period": "报告期",
    "total_operating_revenue": "营业总收入(万元)",
    "operating_revenue_yoy_growth": "营收同比增长(%)",
    "operating_revenue_qoq_growth": "营收环比增长(%)",
    "net_profit_10k_yuan": "净利润(万元)",
    "net_profit_yoy_growth": "净利润同比增长(%)",
    "net_profit_qoq_growth": "净利润环比增长(%)",
    "eps": "每股收益(元)",
    "net_asset_per_share": "每股净资产(元)",
    "roe": "净资产收益率(%)",
    "operating_cf_per_share": "每股经营现金流(元)",
    "net_profit_excl_non_recurring": "扣非净利润(万元)",
    "net_profit_excl_non_recurring_yoy": "扣非净利润同比(%)",
    "gross_profit_margin": "毛利率(%)",
    "industry": "行业",
    "exchange": "交易所",
    "registered_area": "注册地",
    "employee_count": "员工数",
    "net_profit": "净利润(万元)",
    "total_assets": "总资产(万元)",
    "total_liabilities": "总负债(万元)",
    "total_equity": "股东权益(万元)",
}


def _friendly_name(field: str) -> str:
    """将字段名转为友好的中文名"""
    return FIELD_DISPLAY_NAMES.get(field, field)


def _smart_format(value: float) -> str:
    """智能格式化数字"""
    if abs(value) >= 1e8:
        return f'{value / 1e8:.2f}亿'
    elif abs(value) >= 1e4:
        return f'{value / 1e4:.1f}万'
    elif abs(value) >= 1000:
        return f'{value:,.0f}'
    elif abs(value) >= 1:
        return f'{value:.2f}'
    elif abs(value) >= 0.01:
        return f'{value:.2f}%' if abs(value) < 100 else f'{value:.2f}'
    else:
        return f'{value:.4f}'


# =============================================================================
# 风格定义
# =============================================================================
CHART_STYLES = {
    "default": {
        "name": "现代简洁",
        "bg_color": "#ffffff",
        "plot_bg": "#f8fafc",
        "title_color": "#0f172a",
        "text_color": "#475569",
        "label_color": "#64748b",
        "grid_color": "#e2e8f0",
        "grid_alpha": 0.6,
        "spine_color": "#cbd5e1",
        "colors": ["#3b82f6", "#ef4444", "#22c55e", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"],
        "title_size": 16,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.88,
        "bar_edge": "#ffffff",
        "bar_edge_width": 1.2,
        "bar_radius": True,
        "shadow": False,
        "gradient": True,
    },
    "academic": {
        "name": "学术风格",
        "bg_color": "#ffffff",
        "plot_bg": "#ffffff",
        "title_color": "#1a1a1a",
        "text_color": "#333333",
        "label_color": "#555555",
        "grid_color": "#cccccc",
        "grid_alpha": 0.3,
        "spine_color": "#333333",
        "colors": ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"],
        "title_size": 14,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.85,
        "bar_edge": "#333333",
        "bar_edge_width": 0.5,
        "bar_radius": False,
        "shadow": False,
        "gradient": False,
    },
    "business": {
        "name": "商务风格",
        "bg_color": "#ffffff",
        "plot_bg": "#f1f5f9",
        "title_color": "#0c4a6e",
        "text_color": "#334155",
        "label_color": "#475569",
        "grid_color": "#94a3b8",
        "grid_alpha": 0.25,
        "spine_color": "#94a3b8",
        "colors": ["#0369a1", "#0e7490", "#047857", "#b45309", "#7c3aed", "#be185d", "#4338ca", "#0f766e"],
        "title_size": 16,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.92,
        "bar_edge": "#ffffff",
        "bar_edge_width": 1,
        "bar_radius": True,
        "shadow": True,
        "gradient": True,
    },
    "minimal": {
        "name": "极简风格",
        "bg_color": "#ffffff",
        "plot_bg": "#ffffff",
        "title_color": "#111827",
        "text_color": "#6b7280",
        "label_color": "#9ca3af",
        "grid_color": "#f3f4f6",
        "grid_alpha": 1.0,
        "spine_color": "#f3f4f6",
        "colors": ["#6366f1", "#a855f7", "#ec4899", "#14b8a6", "#f97316", "#3b82f6", "#eab308", "#64748b"],
        "title_size": 15,
        "label_size": 10,
        "tick_size": 9,
        "bar_alpha": 0.75,
        "bar_edge": "none",
        "bar_edge_width": 0,
        "bar_radius": True,
        "shadow": False,
        "gradient": False,
    },
    "dark": {
        "name": "暗黑风格",
        "bg_color": "#0f172a",
        "plot_bg": "#1e293b",
        "title_color": "#f1f5f9",
        "text_color": "#94a3b8",
        "label_color": "#64748b",
        "grid_color": "#334155",
        "grid_alpha": 0.5,
        "spine_color": "#334155",
        "colors": ["#60a5fa", "#f87171", "#4ade80", "#fbbf24", "#a78bfa", "#22d3ee", "#fb7185", "#a3e635"],
        "title_size": 16,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.9,
        "bar_edge": "#1e293b",
        "bar_edge_width": 1,
        "bar_radius": True,
        "shadow": False,
        "gradient": True,
    },
    "colorful": {
        "name": "多彩风格",
        "bg_color": "#fffbeb",
        "plot_bg": "#fefce8",
        "title_color": "#78350f",
        "text_color": "#92400e",
        "label_color": "#a16207",
        "grid_color": "#fde68a",
        "grid_alpha": 0.5,
        "spine_color": "#fcd34d",
        "colors": ["#f43f5e", "#8b5cf6", "#06b6d4", "#f59e0b", "#10b981", "#ec4899", "#3b82f6", "#84cc16"],
        "title_size": 16,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.92,
        "bar_edge": "#ffffff",
        "bar_edge_width": 1.5,
        "bar_radius": True,
        "shadow": True,
        "gradient": True,
    },
    "financial": {
        "name": "金融专业",
        "bg_color": "#ffffff",
        "plot_bg": "#f8f9fa",
        "title_color": "#1b2a4a",
        "text_color": "#3d5a80",
        "label_color": "#5a7da8",
        "grid_color": "#c9d6df",
        "grid_alpha": 0.4,
        "spine_color": "#a8bfd0",
        "colors": ["#1b4965", "#c73e3a", "#2a7d4f", "#d4a843", "#5b3a8c", "#2589bd", "#8e4a4a", "#3a8c5b"],
        "title_size": 15,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.9,
        "bar_edge": "#ffffff",
        "bar_edge_width": 0.8,
        "bar_radius": False,
        "shadow": False,
        "gradient": True,
    },
    "elegant": {
        "name": "雅致风格",
        "bg_color": "#faf8f5",
        "plot_bg": "#faf8f5",
        "title_color": "#2d2926",
        "text_color": "#5c5552",
        "label_color": "#8a8582",
        "grid_color": "#d4cfca",
        "grid_alpha": 0.35,
        "spine_color": "#c4bfba",
        "colors": ["#b5838d", "#6d6875", "#e5989b", "#ffb4a2", "#cdb4db", "#a2d2ff", "#bde0fe", "#ffc8dd"],
        "title_size": 16,
        "label_size": 11,
        "tick_size": 10,
        "bar_alpha": 0.85,
        "bar_edge": "#faf8f5",
        "bar_edge_width": 1,
        "bar_radius": True,
        "shadow": False,
        "gradient": True,
    },
}


def _get_style(style_name: str) -> dict:
    """获取风格配置"""
    return CHART_STYLES.get(style_name, CHART_STYLES["default"])


_MPL_INITIALIZED = False


def ensure_matplotlib_chinese():
    """确保matplotlib支持中文显示（首次调用时重建字体缓存）"""
    global _MPL_INITIALIZED
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    if not _MPL_INITIALIZED:
        _MPL_INITIALIZED = True
        
        # 首次运行时，重建字体缓存以确保中文字体被识别
        try:
            cache_dir = matplotlib.get_cachedir()
            if cache_dir:
                for f in os.listdir(cache_dir):
                    if f.startswith('fontlist'):
                        cache_path = os.path.join(cache_dir, f)
                        os.remove(cache_path)
                        logger.info(f"已清除matplotlib字体缓存: {cache_path}")
                fm._load_fontmanager(try_read_cache=False)
        except Exception as e:
            logger.warning(f"清除字体缓存失败（可忽略）: {e}")

        # 注册中文字体文件
        font_paths = [
            'C:/Windows/Fonts/msyh.ttc',       # Microsoft YaHei (Win)
            'C:/Windows/Fonts/simhei.ttf',      # SimHei (Win)
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',  # Linux
            '/System/Library/Fonts/STHeiti Medium.ttc',          # macOS
        ]
        
        font_set = False
        for fp in font_paths:
            try:
                if os.path.exists(fp):
                    fm.fontManager.addfont(fp)
                    prop = fm.FontProperties(fname=fp)
                    font_name = prop.get_name()
                    plt.rcParams['font.sans-serif'] = [font_name]
                    plt.rcParams['font.family'] = 'sans-serif'
                    font_set = True
                    logger.info(f"matplotlib中文字体设置成功: {font_name}")
                    break
            except Exception:
                continue
        
        if not font_set:
            plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
            plt.rcParams['font.family'] = 'sans-serif'
        
        plt.rcParams['axes.unicode_minus'] = False

    return plt


# =============================================================================
# 核心绘图函数
# =============================================================================

def generate_chart(
    data: List[Dict],
    chart_type: str,
    title: str = "",
    x_field: str = "",
    y_fields: List[str] = None,
    save_path: str = "",
    figsize: tuple = (12, 7),
    style: str = "default",
) -> str:
    """
    生成图表
    Args:
        data: 数据列表
        chart_type: 图表类型 (line, bar, pie, table, grouped_bar, horizontal_bar, area, stacked_bar)
        title: 图表标题
        x_field: X轴字段
        y_fields: Y轴字段列表
        save_path: 保存路径
        figsize: 图表大小
        style: 图表风格
    Returns:
        保存的文件路径
    """
    plt = ensure_matplotlib_chinese()

    if not data:
        logger.warning("没有数据，无法生成图表")
        return ""

    # 自动修正字段映射：检测y_fields是否为数值类型，如果不是则尝试交换
    if y_fields and data:
        def _is_numeric_field(field_name):
            for row in data[:3]:
                v = row.get(field_name)
                if v is not None:
                    try:
                        float(v)
                        return True
                    except (ValueError, TypeError):
                        return False
            return False

        non_numeric_y = [f for f in y_fields if not _is_numeric_field(f)]
        if non_numeric_y and x_field and _is_numeric_field(x_field):
            # y_fields包含非数值字段而x_field是数值 → 交换
            logger.info(f"自动修正字段映射: x_field={x_field} ↔ y_fields={y_fields}")
            old_x = x_field
            x_field = non_numeric_y[0]
            y_fields = [old_x] + [f for f in y_fields if f not in non_numeric_y]
        elif non_numeric_y:
            # 从y_fields中移除非数值字段，尝试用它们作为x_field
            numeric_y = [f for f in y_fields if _is_numeric_field(f)]
            if numeric_y:
                if not x_field or not _is_numeric_field(x_field):
                    pass  # x_field已经是标签字段，只需清理y_fields
                else:
                    x_field = non_numeric_y[0]
                y_fields = numeric_y
                logger.info(f"自动清理字段映射: x_field={x_field}, y_fields={y_fields}")

    style_cfg = _get_style(style)
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor(style_cfg["bg_color"])
    ax.set_facecolor(style_cfg["plot_bg"])

    if chart_type == "line" or chart_type == "area":
        _draw_line_chart(ax, data, x_field, y_fields, title, style_cfg, fill=(chart_type == "area"))
    elif chart_type in ("bar", "grouped_bar"):
        _draw_bar_chart(ax, data, x_field, y_fields, title, style_cfg)
    elif chart_type == "horizontal_bar":
        _draw_horizontal_bar(ax, data, x_field, y_fields, title, style_cfg)
    elif chart_type == "stacked_bar":
        _draw_stacked_bar(ax, data, x_field, y_fields, title, style_cfg)
    elif chart_type == "pie":
        _draw_pie_chart(ax, data, x_field, y_fields[0] if y_fields else "", title, style_cfg)
    elif chart_type == "table":
        plt.close(fig)
        return _save_as_table_image(data, title, save_path, figsize, style_cfg)
    else:
        _draw_bar_chart(ax, data, x_field, y_fields, title, style_cfg)

    plt.tight_layout(pad=2.0)

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=160, bbox_inches='tight',
                    facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close(fig)
        logger.info(f"图表已保存: {save_path}")
        return save_path

    plt.close(fig)
    return ""


def _smart_y_formatter(value, pos):
    """Y轴智能数字格式化器"""
    if abs(value) >= 1e8:
        return f'{value / 1e8:.1f}亿'
    elif abs(value) >= 1e4:
        return f'{value / 1e4:.0f}万'
    elif abs(value) >= 1000:
        return f'{value:,.0f}'
    elif abs(value) == 0:
        return '0'
    else:
        return f'{value:.1f}'


def _apply_common_style(ax, title, x_label, y_label, style_cfg, legend=False):
    """应用通用样式"""
    from matplotlib.ticker import FuncFormatter

    ax.set_title(title, fontsize=style_cfg["title_size"], fontweight='bold',
                 pad=18, color=style_cfg["title_color"])
    if x_label:
        ax.set_xlabel(_friendly_name(x_label), fontsize=style_cfg["label_size"],
                      color=style_cfg["text_color"], labelpad=8)
    if y_label:
        ax.set_ylabel(y_label, fontsize=style_cfg["label_size"],
                      color=style_cfg["text_color"], labelpad=8)

    # 使用智能Y轴格式化器，避免科学计数法
    ax.yaxis.set_major_formatter(FuncFormatter(_smart_y_formatter))

    ax.grid(True, alpha=style_cfg["grid_alpha"], linestyle='-',
            linewidth=0.6, color=style_cfg["grid_color"], axis='y', zorder=0)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(style_cfg["spine_color"])
    ax.spines['bottom'].set_color(style_cfg["spine_color"])
    ax.spines['left'].set_linewidth(0.8)
    ax.spines['bottom'].set_linewidth(0.8)
    ax.tick_params(axis='x', colors=style_cfg["label_color"], labelsize=style_cfg["tick_size"])
    ax.tick_params(axis='y', colors=style_cfg["label_color"], labelsize=style_cfg["tick_size"])

    if legend:
        ax.legend(loc='upper right', frameon=True, fancybox=True,
                  fontsize=style_cfg["tick_size"], framealpha=0.92,
                  edgecolor=style_cfg["grid_color"], borderpad=0.8)


def _draw_line_chart(ax, data, x_field, y_fields, title, style_cfg, fill=False):
    """绘制折线图"""
    import numpy as np

    colors = style_cfg["colors"]
    x_values = [str(d.get(x_field, "")) for d in data]
    x_pos = np.arange(len(x_values))

    for idx, y_field in enumerate(y_fields or []):
        y_values = [float(d.get(y_field, 0) or 0) for d in data]
        color = colors[idx % len(colors)]
        label = _friendly_name(y_field)

        if fill:
            ax.fill_between(x_pos, y_values, alpha=0.2, color=color)

        ax.plot(x_pos, y_values, marker='o', linewidth=2.5,
                markersize=7, label=label, color=color,
                markerfacecolor='white', markeredgewidth=2,
                markeredgecolor=color, zorder=3)

        # 智能标注：数据点少于12个时标注所有，否则标注首尾和极值
        if len(y_values) <= 12:
            indices = range(len(y_values))
        else:
            indices = {0, len(y_values) - 1}
            if y_values:
                indices.add(y_values.index(max(y_values)))
                indices.add(y_values.index(min(y_values)))

        for i in indices:
            ax.annotate(_smart_format(y_values[i]), (x_pos[i], y_values[i]),
                        textcoords="offset points", xytext=(0, 10),
                        ha='center', fontsize=8, fontweight='bold',
                        color=style_cfg["text_color"],
                        bbox=dict(boxstyle='round,pad=0.25', facecolor='white',
                                  edgecolor=color, alpha=0.85, linewidth=0.8))

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_values, rotation=30 if len(x_values) > 5 else 0, ha='right')
    _apply_common_style(ax, title, x_field, "", style_cfg, legend=len(y_fields or []) > 1)


def _draw_bar_chart(ax, data, x_field, y_fields, title, style_cfg):
    """绘制柱状图 - 支持多系列分组"""
    import numpy as np

    colors = style_cfg["colors"]
    x_values = [str(d.get(x_field, "")) for d in data]
    # 截断过长的标签
    x_display = [v[:8] + '…' if len(v) > 8 else v for v in x_values]
    x_pos = np.arange(len(x_values))

    n_fields = len(y_fields) if y_fields else 1
    width = min(0.8 / n_fields, 0.45) if n_fields > 1 else 0.55

    for i, y_field in enumerate(y_fields or []):
        y_values = [float(d.get(y_field, 0) or 0) for d in data]
        offset = (i - n_fields / 2 + 0.5) * width if n_fields > 1 else 0
        color = colors[i % len(colors)]
        label = _friendly_name(y_field)

        edge_color = style_cfg["bar_edge"] if style_cfg["bar_edge"] != "none" else "none"
        bars = ax.bar(x_pos + offset, y_values, width, label=label,
                      color=color, alpha=style_cfg["bar_alpha"],
                      edgecolor=edge_color, linewidth=style_cfg["bar_edge_width"],
                      zorder=2)

        # 渐变高光效果
        if style_cfg.get("gradient"):
            for bar in bars:
                h = bar.get_height()
                if h > 0:
                    ax.bar(bar.get_x(), h * 0.12, width=bar.get_width(),
                           bottom=h * 0.88, color='white', alpha=0.25, zorder=3)

        # 数据标签
        for bar, val in zip(bars, y_values):
            if val != 0:
                label_text = _smart_format(val)
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + (max(y_values) - min(y_values)) * 0.015,
                        label_text, ha='center', va='bottom',
                        fontsize=8, fontweight='bold',
                        color=style_cfg["text_color"])

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_display, rotation=30 if len(x_display) > 4 else 0, ha='right')
    _apply_common_style(ax, title, x_field, "", style_cfg, legend=n_fields > 1)


def _draw_horizontal_bar(ax, data, x_field, y_fields, title, style_cfg):
    """绘制水平柱状图（适合长标签）"""
    import numpy as np

    colors = style_cfg["colors"]
    y_field = y_fields[0] if y_fields else ""
    labels = [str(d.get(x_field, "")) for d in data]
    values = [float(d.get(y_field, 0) or 0) for d in data]

    # 按值排序
    sorted_pairs = sorted(zip(labels, values), key=lambda x: x[1])
    labels, values = zip(*sorted_pairs) if sorted_pairs else ([], [])

    y_pos = np.arange(len(labels))
    color = colors[0]

    bars = ax.barh(y_pos, values, height=0.6, color=color,
                   alpha=style_cfg["bar_alpha"], zorder=2,
                   edgecolor=style_cfg["bar_edge"] if style_cfg["bar_edge"] != "none" else "none",
                   linewidth=style_cfg["bar_edge_width"])

    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + max(values) * 0.01, bar.get_y() + bar.get_height() / 2,
                _smart_format(val), ha='left', va='center',
                fontsize=8, fontweight='bold', color=style_cfg["text_color"])

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=style_cfg["tick_size"])
    ax.grid(True, alpha=style_cfg["grid_alpha"], axis='x', color=style_cfg["grid_color"])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(style_cfg["spine_color"])
    ax.spines['bottom'].set_color(style_cfg["spine_color"])
    ax.set_title(title, fontsize=style_cfg["title_size"], fontweight='bold',
                 pad=18, color=style_cfg["title_color"])


def _draw_stacked_bar(ax, data, x_field, y_fields, title, style_cfg):
    """绘制堆叠柱状图"""
    import numpy as np

    colors = style_cfg["colors"]
    x_values = [str(d.get(x_field, ""))[:8] for d in data]
    x_pos = np.arange(len(x_values))

    bottom = np.zeros(len(x_values))
    for i, y_field in enumerate(y_fields or []):
        y_values = np.array([float(d.get(y_field, 0) or 0) for d in data])
        color = colors[i % len(colors)]
        ax.bar(x_pos, y_values, 0.55, bottom=bottom, label=_friendly_name(y_field),
               color=color, alpha=style_cfg["bar_alpha"], zorder=2)
        bottom += y_values

    ax.set_xticks(x_pos)
    ax.set_xticklabels(x_values, rotation=30, ha='right')
    _apply_common_style(ax, title, x_field, "", style_cfg, legend=True)


def _draw_pie_chart(ax, data, label_field, value_field, title, style_cfg):
    """绘制饼图 - 专业风格"""
    labels = [str(d.get(label_field, "")) for d in data]
    values = [float(d.get(value_field, 0) or 0) for d in data]

    filtered = [(l, v) for l, v in zip(labels, values) if v > 0]
    if not filtered:
        ax.text(0.5, 0.5, "无有效数据", ha='center', va='center',
                fontsize=14, color=style_cfg["text_color"])
        return

    labels, values = zip(*filtered)
    colors = style_cfg["colors"][:len(values)]

    # 最大的一块微微突出
    explode = [0.03 if v == max(values) else 0 for v in values]

    wedges, texts, autotexts = ax.pie(
        values, labels=labels, autopct='%1.1f%%',
        colors=colors, startangle=140, pctdistance=0.78,
        explode=explode,
        wedgeprops=dict(linewidth=1.5, edgecolor='white'),
        textprops=dict(fontsize=style_cfg["tick_size"], color=style_cfg["text_color"]),
    )

    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_fontweight('bold')
        autotext.set_color('#ffffff')

    # 中心空白区域（甜甜圈效果）
    centre_circle = plt_circle((0, 0), 0.45, fc=style_cfg["bg_color"], ec='none')
    ax.add_patch(centre_circle)

    ax.set_title(title, fontsize=style_cfg["title_size"], fontweight='bold',
                 pad=18, color=style_cfg["title_color"])


def plt_circle(center, radius, **kwargs):
    """创建圆形patch"""
    import matplotlib.patches as mpatches
    return mpatches.Circle(center, radius, **kwargs)


def _save_as_table_image(data, title, save_path, figsize, style_cfg):
    """将数据保存为表格图片 - 精美样式"""
    plt = ensure_matplotlib_chinese()

    if not data:
        return ""

    columns = list(data[0].keys())
    display_columns = [_friendly_name(c) for c in columns]
    cell_text = []
    for d in data:
        row = []
        for c in columns:
            v = d.get(c, "")
            if isinstance(v, float):
                row.append(_smart_format(v))
            else:
                row.append(str(v))
        cell_text.append(row)

    # 自适应大小
    n_rows = len(cell_text)
    n_cols = len(columns)
    fig_w = max(figsize[0], n_cols * 2.2)
    fig_h = max(4, (n_rows + 1) * 0.55 + 2)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.patch.set_facecolor(style_cfg["bg_color"])
    ax.axis('off')

    table = ax.table(
        cellText=cell_text,
        colLabels=display_columns,
        cellLoc='center',
        loc='center',
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.2, 1.6)

    # 表头样式
    header_color = style_cfg["colors"][0]
    for i in range(n_cols):
        cell = table[0, i]
        cell.set_facecolor(header_color)
        cell.set_text_props(color='white', fontweight='bold', fontsize=10)
        cell.set_edgecolor('#ffffff')
        cell.set_linewidth(1.5)

    # 交替行颜色
    for row_idx in range(1, n_rows + 1):
        for col_idx in range(n_cols):
            cell = table[row_idx, col_idx]
            if row_idx % 2 == 0:
                cell.set_facecolor('#f8fafc')
            else:
                cell.set_facecolor('#ffffff')
            cell.set_edgecolor('#e2e8f0')
            cell.set_linewidth(0.5)

    ax.set_title(title, fontsize=style_cfg["title_size"], fontweight='bold',
                 pad=20, color=style_cfg["title_color"])

    if save_path:
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        fig.savefig(save_path, dpi=160, bbox_inches='tight',
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        return save_path

    plt.close(fig)
    return ""


# =============================================================================
# 图表生成器（LLM驱动）
# =============================================================================

class ChartGenerator:
    """智能图表生成器，由LLM决定图表类型和参数"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def auto_generate_chart(
        self,
        question: str,
        sql_result: List[Dict],
        intent: Dict[str, Any],
        save_dir: str = "./results",
        file_prefix: str = "chart",
        style: str = "default",
    ) -> Optional[str]:
        """
        根据问题和数据自动生成图表
        Returns:
            图表文件路径
        """
        if not sql_result:
            return None

        chart_config = await self._decide_chart_config(question, sql_result, intent)

        if not chart_config or chart_config.get("chart_type") == "none":
            return None

        save_path = os.path.join(save_dir, f"{file_prefix}.jpg")
        chart_title = chart_config.get("title", question)

        try:
            return generate_chart(
                data=sql_result,
                chart_type=chart_config.get("chart_type", "bar"),
                title=chart_title,
                x_field=chart_config.get("x_field", ""),
                y_fields=chart_config.get("y_fields", []),
                save_path=save_path,
                style=style,
            )
        except Exception as exc:
            logger.warning("图表生成失败，已回退为表格图片: %s", exc)
            try:
                return generate_chart(
                    data=sql_result,
                    chart_type="table",
                    title=f"{chart_title}（表格兜底）",
                    x_field="",
                    y_fields=[],
                    save_path=save_path,
                    style=style,
                )
            except Exception as fallback_exc:
                logger.error("表格兜底也失败，跳过图表输出: %s", fallback_exc)
                return None

    async def _decide_chart_config(
        self,
        question: str,
        data: List[Dict],
        intent: Dict,
    ) -> Dict:
        """由LLM决定图表配置"""
        columns = list(data[0].keys()) if data else []
        sample = data[:3] if len(data) > 3 else data

        prompt = f"""
根据以下信息，决定最佳的图表类型和配置。

用户问题：{question}
数据列名：{columns}
数据样本（前3行）：{json.dumps(sample, ensure_ascii=False, default=str)}
数据总行数：{len(data)}

返回JSON格式：
{{
    "chart_type": "line/bar/horizontal_bar/stacked_bar/pie/table/none",
    "title": "图表标题（简洁中文标题，不要包含字段名）",
    "x_field": "X轴字段名",
    "y_fields": ["Y轴字段名1", "Y轴字段名2"],
    "reason": "选择此图表类型的原因"
}}

重要规则：
1. 时间序列/趋势数据用折线图(line)
2. 对比排名数据用柱状图(bar)
3. 标签较长（如公司全称）用水平柱状图(horizontal_bar)
4. 占比/构成数据用饼图(pie)
5. 多个指标堆叠用堆叠柱状图(stacked_bar)
6. 复杂多列数据用表格(table)
7. 如果数据不适合可视化，返回"none"
8. **Y轴字段不要混合量级差异极大的指标**（如利润和增长率不要放在一起）
9. 如果只有1行数据，优先使用table
10. title应该是简洁的中文标题，如"2024年中药行业利润排名Top10"
"""
        try:
            return await self.llm.query_json(prompt)
        except Exception as e:
            logger.warning(f"图表配置生成失败: {e}")
            if intent.get("chart_type") == "line":
                return {
                    "chart_type": "line",
                    "title": question,
                    "x_field": columns[0] if columns else "",
                    "y_fields": columns[1:2] if len(columns) > 1 else [],
                }
            return {"chart_type": "none"}
