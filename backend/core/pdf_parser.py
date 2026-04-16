"""
PDF财报解析模块
从财务报告PDF中提取结构化数据
支持上交所和深交所两种命名格式
"""
import os
import re
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ReportMeta:
    """财报元数据"""
    file_path: str = ""
    file_name: str = ""
    stock_code: str = ""
    stock_abbr: str = ""
    report_year: int = 0
    report_period: str = ""  # FY, Q1, HY, Q3
    report_type: str = ""  # 年度报告, 半年度报告, 一季度报告, 三季度报告, 报告摘要
    exchange: str = ""  # 上交所, 深交所
    publish_date: str = ""


@dataclass
class FinancialData:
    """提取的财务数据"""
    meta: ReportMeta = field(default_factory=ReportMeta)
    core_performance: Dict[str, Any] = field(default_factory=dict)
    balance_sheet: Dict[str, Any] = field(default_factory=dict)
    income_sheet: Dict[str, Any] = field(default_factory=dict)
    cash_flow_sheet: Dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    tables: List[Dict] = field(default_factory=list)


def parse_report_meta_shanghai(filename: str) -> ReportMeta:
    """
    解析上交所报告文件名
    格式：股票代码_报告日期_随机标识.pdf
    例如：600080_20230428_FQ2V.pdf
    """
    meta = ReportMeta(exchange="上交所", file_name=filename)
    parts = filename.replace(".pdf", "").split("_")
    if len(parts) >= 3:
        meta.stock_code = parts[0]
        date_str = parts[1]
        if len(date_str) == 8:
            meta.publish_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            month = int(date_str[4:6])
            # 根据发布月份推断报告类型
            # 4月发布的通常是年报或一季报
            # 8月发布的通常是半年报
            # 10月发布的通常是三季报
            if month in [3, 4, 5]:
                # 可能是年报或一季报，需要根据内容判断
                meta.report_type = "待确定"
            elif month in [7, 8, 9]:
                meta.report_type = "半年度报告"
            elif month in [10, 11]:
                meta.report_type = "三季度报告"
    return meta


def parse_report_meta_shenzhen(filename: str) -> ReportMeta:
    """
    解析深交所报告文件名
    格式：A股简称：年份+报告周期+报告类型.pdf
    例如：华润三九：2023年年度报告.pdf
    """
    meta = ReportMeta(exchange="深交所", file_name=filename)
    name_part = filename.replace(".pdf", "")

    # 提取公司简称（冒号前的部分）
    if "：" in name_part:
        meta.stock_abbr = name_part.split("：")[0]
        report_part = name_part.split("：")[1]
    elif ":" in name_part:
        meta.stock_abbr = name_part.split(":")[0]
        report_part = name_part.split(":")[1]
    else:
        return meta

    # 提取年份
    year_match = re.search(r'(\d{4})年', report_part)
    if year_match:
        meta.report_year = int(year_match.group(1))

    # 确定报告类型和期间
    if "年度报告摘要" in report_part:
        meta.report_type = "年度报告摘要"
        meta.report_period = f"{meta.report_year}FY"
    elif "年度报告" in report_part:
        meta.report_type = "年度报告"
        meta.report_period = f"{meta.report_year}FY"
    elif "半年度报告摘要" in report_part:
        meta.report_type = "半年度报告摘要"
        meta.report_period = f"{meta.report_year}HY"
    elif "半年度报告" in report_part:
        meta.report_type = "半年度报告"
        meta.report_period = f"{meta.report_year}HY"
    elif "一季度报告" in report_part:
        meta.report_type = "一季度报告"
        meta.report_period = f"{meta.report_year}Q1"
    elif "三季度报告" in report_part:
        meta.report_type = "三季度报告"
        meta.report_period = f"{meta.report_year}Q3"

    return meta


def extract_text_from_pdf(pdf_path: str) -> str:
    """从PDF提取文本"""
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
        return "\n".join(text_parts)
    except ImportError:
        logger.error("请安装 pdfplumber: pip install pdfplumber")
        raise


def extract_tables_from_pdf(pdf_path: str) -> List[List[List[str]]]:
    """从PDF提取表格"""
    try:
        import pdfplumber
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                if tables:
                    all_tables.extend(tables)
        return all_tables
    except ImportError:
        logger.error("请安装 pdfplumber: pip install pdfplumber")
        raise


def classify_report_by_content(text: str, meta: ReportMeta) -> ReportMeta:
    """
    根据PDF内容进一步确定报告类型
    主要用于上交所格式（文件名不含报告类型信息）
    """
    text_lower = text[:5000]  # 只看前面部分

    if "年度报告摘要" in text_lower:
        meta.report_type = "年度报告摘要"
    elif "年度报告" in text_lower or "年 度 报 告" in text_lower:
        meta.report_type = "年度报告"
    elif "半年度报告摘要" in text_lower:
        meta.report_type = "半年度报告摘要"
    elif "半年度报告" in text_lower or "半 年 度 报 告" in text_lower:
        meta.report_type = "半年度报告"
    elif "第一季度报告" in text_lower or "一季度报告" in text_lower:
        meta.report_type = "一季度报告"
    elif "第三季度报告" in text_lower or "三季度报告" in text_lower:
        meta.report_type = "三季度报告"

    # 提取年份
    year_match = re.search(r'(20\d{2})\s*年', text_lower)
    if year_match and meta.report_year == 0:
        meta.report_year = int(year_match.group(1))

    # 确定report_period
    if meta.report_year > 0 and not meta.report_period:
        period_map = {
            "年度报告": "FY", "年度报告摘要": "FY",
            "半年度报告": "HY", "半年度报告摘要": "HY",
            "一季度报告": "Q1", "三季度报告": "Q3",
        }
        suffix = period_map.get(meta.report_type, "")
        if suffix:
            meta.report_period = f"{meta.report_year}{suffix}"

    # 提取股票代码和简称
    if not meta.stock_abbr:
        abbr_match = re.search(r'(?:股票简称|A股简称)[：:]\s*(\S+)', text_lower)
        if abbr_match:
            meta.stock_abbr = abbr_match.group(1).strip()

    code_match = re.search(r'(?:股票代码|证券代码)[：:]\s*(\d{6})', text_lower)
    if code_match and not meta.stock_code:
        meta.stock_code = code_match.group(1)

    return meta


# =============================================================================
# 财务数据规则提取器
# =============================================================================

def _parse_number(text: str) -> Optional[float]:
    """解析数字字符串为浮点数"""
    if not text or text.strip() in ["-", "—", "–", "N/A", "不适用", ""]:
        return None
    text = text.strip().replace(",", "").replace("，", "").replace(" ", "")
    # 处理百分号
    is_percent = "%" in text
    text = text.replace("%", "")
    # 处理括号表示负数
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    if text.startswith("（") and text.endswith("）"):
        text = "-" + text[1:-1]
    try:
        val = float(text)
        return val
    except ValueError:
        return None


def _extract_value_from_text(text: str, patterns: List[str]) -> Optional[float]:
    """使用正则模式从文本中提取数值"""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            val = _parse_number(match.group(1))
            if val is not None:
                return val
    return None


def _normalize_table_text(text: str) -> str:
    """归一化表格标签文本，尽量消除换行、空白和括号说明的影响。"""
    normalized = re.sub(r"\s+", "", text or "")
    normalized = normalized.replace("（", "(").replace("）", ")")
    normalized = normalized.replace("：", ":")
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = normalized.replace(":", "")
    return re.sub(r"^[一二三四五六七八九十\d]+[、\.．]", "", normalized)


def _is_note_reference_cell(text: str) -> bool:
    """识别主报表中的附注编号列，例如“七、67”“十九、5”."""
    normalized = re.sub(r"\s+", "", text or "")
    if not normalized:
        return False
    return bool(re.match(r"^[一二三四五六七八九十百零]+、\d+(?:\.\d+)?$", normalized))


def _extract_row_label_and_numbers(row: List[Any]) -> Tuple[str, List[float]]:
    """提取一行表格中的标签文本，以及标签右侧的所有数值。"""
    label_parts: List[str] = []
    numbers: List[float] = []
    seen_numeric = False

    for cell in row or []:
        cell_text = str(cell or "").strip()
        if not cell_text:
            continue

        number = _parse_number(cell_text)
        if number is None and not seen_numeric:
            if label_parts and _is_note_reference_cell(cell_text):
                continue
            label_parts.append(cell_text)
            continue

        if number is not None:
            seen_numeric = True
            numbers.append(number)

    label = _normalize_table_text("".join(label_parts))
    return label, numbers


_INCOME_TABLE_ANCHORS = [
    "营业总收入",
    "营业收入",
    "营业总成本",
    "营业总支出",
    "营业利润",
    "利润总额",
    "净利润",
    "营业外收入",
    "营业外支出",
]

_INCOME_NOTE_HINTS = [
    "除上述各项之外",
    "主要系",
    "非经常性损益",
]


def _rank_income_statement_tables(tables: List) -> List:
    """优先识别主利润表，避免误取附注里的同名字段。"""
    normalized_anchors = [_normalize_table_text(keyword) for keyword in _INCOME_TABLE_ANCHORS]
    normalized_hints = [_normalize_table_text(keyword) for keyword in _INCOME_NOTE_HINTS]
    scored_tables: List[Tuple[int, int, Any]] = []

    for idx, table in enumerate(tables):
        labels: List[str] = []
        table_text_parts: List[str] = []

        for row in table or []:
            if not row:
                continue
            label_text, numbers = _extract_row_label_and_numbers(row)
            row_text = "".join(str(cell or "") for cell in row)
            if row_text:
                table_text_parts.append(row_text)
            if label_text and numbers:
                labels.append(label_text)

        if not labels:
            continue

        score = 0
        matched_anchor_count = 0
        for anchor in normalized_anchors:
            if any(label == anchor for label in labels):
                score += 4
                matched_anchor_count += 1
            elif any(anchor in label for label in labels):
                score += 1
                matched_anchor_count += 1

        if matched_anchor_count >= 4:
            score += 3
        elif matched_anchor_count >= 2:
            score += 1

        if len(labels) >= 8:
            score += 1

        normalized_table_text = _normalize_table_text("".join(table_text_parts))
        for hint in normalized_hints:
            if hint and hint in normalized_table_text:
                score -= 6

        if matched_anchor_count >= 2 and score > 0:
            scored_tables.append((score, idx, table))

    scored_tables.sort(key=lambda item: (-item[0], item[1]))
    return [table for _, _, table in scored_tables]


def extract_financial_data_by_rules(
    text: str,
    tables: List[List[List[str]]],
    meta: ReportMeta,
) -> FinancialData:
    """
    通过规则从文本和表格中提取财务数据
    这是第一步，后续可以用LLM增强
    """
    data = FinancialData(meta=meta, raw_text=text, tables=tables)

    # 提取利润表相关数据
    data.income_sheet = _extract_income_data(text, tables)
    # 提取资产负债表相关数据
    data.balance_sheet = _extract_balance_data(text, tables)
    # 提取现金流量表相关数据
    data.cash_flow_sheet = _extract_cash_flow_data(text, tables)
    # 提取核心业绩指标
    data.core_performance = _extract_core_performance(text, tables)

    return data


def _find_table_value(tables: List, row_keywords: List[str], col_index: int = 1) -> Optional[float]:
    """在表格中查找特定行的值。

    与早期实现不同，这里不再写死读取 `row[1]`，而是：
    1. 归一化行标签，处理换行、空白、括号说明；
    2. 从标签右侧开始，取第 `col_index` 个有效数值。
    """
    target_number_index = max(col_index - 1, 0)
    normalized_keywords = [_normalize_table_text(keyword) for keyword in row_keywords if keyword]

    for keyword in normalized_keywords:
        fuzzy_match_value = None
        for table in tables:
            for row in table:
                if not row:
                    continue
                label_text, numbers = _extract_row_label_and_numbers(row)
                if not keyword or len(numbers) <= target_number_index:
                    continue
                if label_text == keyword:
                    return numbers[target_number_index]
                if keyword in label_text and fuzzy_match_value is None:
                    fuzzy_match_value = numbers[target_number_index]
        if fuzzy_match_value is not None:
            return fuzzy_match_value
    return None


def _find_table_value_with_priority(
    tables: List,
    row_keywords: List[str],
    preferred_tables: Optional[List] = None,
    col_index: int = 1,
) -> Optional[float]:
    """优先在候选主表中取值，找不到再回退到全表搜索。"""
    if preferred_tables:
        value = _find_table_value(preferred_tables, row_keywords, col_index=col_index)
        if value is not None:
            return value
    return _find_table_value(tables, row_keywords, col_index=col_index)


def _extract_income_data(text: str, tables: List) -> Dict[str, Any]:
    """提取利润表数据"""
    data = {}
    preferred_income_tables = _rank_income_statement_tables(tables)
    
    # 从表格中查找关键字段
    field_mappings = {
        "total_operating_revenue": ["营业总收入", "营业收入"],
        "operating_expense_cost_of_sales": ["营业成本", "营业支出"],
        "operating_expense_selling_expenses": ["销售费用"],
        "operating_expense_administrative_expenses": ["管理费用"],
        "operating_expense_financial_expenses": ["财务费用"],
        "operating_expense_rnd_expenses": ["研发费用"],
        "operating_expense_taxes_and_surcharges": ["税金及附加"],
        "total_operating_expenses": ["营业总支出", "营业总成本"],
        "operating_profit": ["营业利润"],
        "total_profit": ["利润总额"],
        "net_profit": ["净利润"],
        "other_income": ["其他收益"],
        "investment_income": ["投资收益"],
        "fair_value_change_income": ["公允价值变动收益"],
        "asset_disposal_income": ["资产处置收益"],
        "non_operating_income": ["营业外收入"],
        "non_operating_expenses": ["营业外支出"],
        "asset_impairment_loss": ["资产减值损失"],
        "credit_impairment_loss": ["信用减值损失"],
    }

    for field_name, keywords in field_mappings.items():
        val = _find_table_value_with_priority(
            tables,
            keywords,
            preferred_tables=preferred_income_tables,
        )
        if val is not None:
            data[field_name] = val

    return data


def _extract_balance_data(text: str, tables: List) -> Dict[str, Any]:
    """提取资产负债表数据"""
    data = {}

    field_mappings = {
        "asset_cash_and_cash_equivalents": ["货币资金"],
        "asset_accounts_receivable": ["应收账款"],
        "asset_inventory": ["存货"],
        "asset_trading_financial_assets": ["交易性金融资产"],
        "asset_construction_in_progress": ["在建工程"],
        "asset_total_assets": ["资产总计", "总资产"],
        "liability_accounts_payable": ["应付账款"],
        "liability_advance_from_customers": ["预收账款", "预收款项"],
        "liability_total_liabilities": ["负债合计", "负债总计", "总负债"],
        "liability_contract_liabilities": ["合同负债"],
        "liability_short_term_loans": ["短期借款"],
        "equity_unappropriated_profit": ["未分配利润"],
        "equity_total_equity": ["所有者权益合计", "股东权益合计"],
    }

    for field_name, keywords in field_mappings.items():
        val = _find_table_value(tables, keywords)
        if val is not None:
            data[field_name] = val

    # 计算资产负债率
    if "asset_total_assets" in data and "liability_total_liabilities" in data:
        if data["asset_total_assets"] != 0:
            data["asset_liability_ratio"] = round(
                data["liability_total_liabilities"] / data["asset_total_assets"] * 100, 4
            )

    return data


def _extract_cash_flow_data(text: str, tables: List) -> Dict[str, Any]:
    """提取现金流量表数据"""
    data = {}

    field_mappings = {
        "operating_cf_cash_from_sales": ["销售商品、提供劳务收到的现金", "销售商品收到的现金"],
        "operating_cf_net_amount": ["经营活动产生的现金流量净额"],
        "investing_cf_net_amount": ["投资活动产生的现金流量净额"],
        "investing_cf_cash_for_investments": ["投资支付的现金"],
        "investing_cf_cash_from_investment_recovery": ["收回投资收到的现金"],
        "financing_cf_cash_from_borrowing": ["取得借款收到的现金"],
        "financing_cf_cash_for_debt_repayment": ["偿还债务支付的现金"],
        "financing_cf_net_amount": ["筹资活动产生的现金流量净额", "融资活动产生的现金流量净额"],
        "net_cash_flow": ["现金及现金等价物净增加额"],
    }

    for field_name, keywords in field_mappings.items():
        val = _find_table_value(tables, keywords)
        if val is not None:
            data[field_name] = val

    # 计算占比
    net_cf = data.get("net_cash_flow")
    if net_cf and net_cf != 0:
        for key, ratio_key in [
            ("operating_cf_net_amount", "operating_cf_ratio_of_net_cf"),
            ("investing_cf_net_amount", "investing_cf_ratio_of_net_cf"),
            ("financing_cf_net_amount", "financing_cf_ratio_of_net_cf"),
        ]:
            if key in data:
                data[ratio_key] = round(data[key] / net_cf * 100, 4)

    return data


def _extract_core_performance(text: str, tables: List) -> Dict[str, Any]:
    """提取核心业绩指标"""
    data = {}

    field_mappings = {
        "eps": ["基本每股收益", "每股收益"],
        "net_asset_per_share": ["每股净资产"],
        "roe": ["净资产收益率", "加权平均净资产收益率"],
        "operating_cf_per_share": ["每股经营现金流量", "每股经营活动现金流量净额"],
        "gross_profit_margin": ["销售毛利率", "毛利率"],
    }

    for field_name, keywords in field_mappings.items():
        val = _find_table_value(tables, keywords)
        if val is not None:
            data[field_name] = val

    return data


def scan_report_files(data_dir: str) -> List[ReportMeta]:
    """
    扫描数据目录，返回所有财报文件的元数据列表
    """
    reports = []
    data_path = Path(data_dir)

    # 扫描附件2
    att2_patterns = ["附件2", "财务报告"]
    for d in data_path.iterdir():
        if d.is_dir() and any(p in d.name for p in att2_patterns):
            # 扫描上交所
            sh_dir = d / "reports-上交所"
            if sh_dir.exists():
                for f in sh_dir.glob("*.pdf"):
                    meta = parse_report_meta_shanghai(f.name)
                    meta.file_path = str(f)
                    reports.append(meta)

            # 扫描深交所
            sz_dir = d / "reports-深交所"
            if sz_dir.exists():
                for f in sz_dir.glob("*.pdf"):
                    meta = parse_report_meta_shenzhen(f.name)
                    meta.file_path = str(f)
                    reports.append(meta)

    logger.info(f"扫描到 {len(reports)} 个财报文件")
    return reports
