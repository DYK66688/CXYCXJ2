"""
运行前自检模块
在任务脚本和后端启动前对常见环境/数据问题做前置检查。
"""
from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PLACEHOLDER_API_KEYS = {
    "",
    "xx",
    "your_api_key",
    "your-api-key",
    "api_key",
    "your key",
    "你的api密钥",
    "您的api密钥",
    "请输入api key",
}

_COMMON_FONT_PATHS = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
]


@dataclass
class PreflightReport:
    title: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "PreflightReport"):
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.update(other.info)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def _is_placeholder_api_key(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    lower = text.lower()
    return lower in _PLACEHOLDER_API_KEYS or lower.startswith("your_")


def _safe_import_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _has_chinese_font() -> bool:
    return any(Path(p).exists() for p in _COMMON_FONT_PATHS)


def _get_attachment_dir(sample_data_dir: Path, keywords: List[str]) -> Optional[Path]:
    if not sample_data_dir.exists():
        return None
    for child in sample_data_dir.iterdir():
        if child.is_dir() and any(keyword in child.name for keyword in keywords):
            return child
    return None


def _check_llm_config(config, strict: bool) -> PreflightReport:
    report = PreflightReport("LLM配置检查")
    enabled_llms = [llm for llm in config.llm_configs if llm.enabled]
    if not enabled_llms:
        report.errors.append("没有启用任何 LLM 配置。")
        return report

    report.info["enabled_llm_models"] = [llm.model for llm in enabled_llms]
    for llm in enabled_llms:
        if _is_placeholder_api_key(llm.api_key):
            message = f"LLM `{llm.name}` 的 API Key 仍是占位值，请先在 config.json 或前端设置页中填写真实 Key。"
            if strict:
                report.errors.append(message)
            else:
                report.warnings.append(message)

    if enabled_llms and not any("flash" in (llm.model or "").lower() for llm in enabled_llms):
        report.warnings.append("当前启用模型不含 Flash/轻量模型，批量任务执行可能较慢。")
    return report


def _check_embedding_config(config, strict: bool) -> PreflightReport:
    report = PreflightReport("Embedding配置检查")
    emb = config.embedding
    if emb.use_local:
        model_path = Path(emb.local_model_path)
        report.info["embedding_local_model_path"] = str(model_path)
        if not model_path.exists():
            message = f"本地嵌入模型目录不存在: {model_path}"
            if strict:
                report.errors.append(message)
            else:
                report.warnings.append(message)
        if "bge-small-zh-v1.5" in str(model_path).lower() and emb.dimension != 512:
            report.warnings.append("当前本地模型看起来是 bge-small-zh-v1.5，但 embedding.dimension 不是 512，可能导致向量维度不一致。")
    else:
        if _is_placeholder_api_key(emb.api_key) or not emb.api_base_url:
            message = "当前使用云端嵌入模型，但 api_key/api_base_url 仍未完整配置。"
            if strict:
                report.errors.append(message)
            else:
                report.warnings.append(message)
    return report


def _check_visualization_environment() -> PreflightReport:
    report = PreflightReport("可视化环境检查")
    if not _safe_import_available("matplotlib"):
        report.errors.append("matplotlib 未安装，图表生成功能无法使用。")
        return report
    if not _has_chinese_font():
        report.warnings.append("未检测到常用中文字体，图表中的中文可能出现乱码。")
    return report


def _check_ocr_support() -> Dict[str, Any]:
    has_pytesseract = _safe_import_available("pytesseract")
    tesseract_cmd = _find_tesseract_cmd()
    if has_pytesseract and tesseract_cmd:
        _configure_pytesseract(tesseract_cmd)
    return {
        "has_pytesseract": has_pytesseract,
        "tesseract_cmd": tesseract_cmd or "",
        "available": has_pytesseract and bool(tesseract_cmd),
    }


def _find_tesseract_cmd() -> Optional[str]:
    direct_match = shutil.which("tesseract")
    if direct_match:
        return direct_match

    env_cmd = os.environ.get("TESSERACT_CMD", "").strip()
    if env_cmd and Path(env_cmd).exists():
        return env_cmd

    candidate_roots = [
        Path(sys.prefix),
        Path(sys.executable).resolve().parent.parent,
    ]
    candidate_suffixes = [
        Path("Library/bin/tesseract.exe"),
        Path("Scripts/tesseract.exe"),
        Path("tesseract.exe"),
    ]

    for root in candidate_roots:
        for suffix in candidate_suffixes:
            candidate = root / suffix
            if candidate.exists():
                return str(candidate)
    return None


def _configure_pytesseract(tesseract_cmd: str):
    try:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    except Exception as exc:
        logger.debug("配置 pytesseract 路径失败: %s", exc)


def _detect_scan_like_pdfs(pdf_paths: List[Path], sample_limit: int = 3) -> List[str]:
    if not pdf_paths:
        return []
    if not _safe_import_available("pdfplumber"):
        return []

    import pdfplumber

    candidates: List[str] = []
    for pdf_path in pdf_paths[:sample_limit]:
        try:
            total_chars = 0
            sampled_pages = 0
            empty_pages = 0
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page in pdf.pages[: min(2, len(pdf.pages))]:
                    sampled_pages += 1
                    text = (page.extract_text() or "").strip()
                    total_chars += len(text)
                    if len(text) < 30:
                        empty_pages += 1
            if sampled_pages and (total_chars < 80 or empty_pages == sampled_pages):
                candidates.append(pdf_path.name)
        except Exception as exc:
            logger.debug("扫描式PDF检测失败: %s (%s)", pdf_path, exc)
    return candidates


def _database_summary(db) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "income_sheet_rows": 0,
        "balance_sheet_rows": 0,
        "cash_flow_sheet_rows": 0,
        "company_info_rows": 0,
        "research_reports_rows": 0,
        "knowledge_chunks_rows": 0,
        "available_report_periods": [],
        "sample_companies": [],
    }
    try:
        table_names = set(db.get_table_names())
    except Exception:
        return summary

    for table in [
        "income_sheet",
        "balance_sheet",
        "cash_flow_sheet",
        "company_info",
        "research_reports",
        "knowledge_chunks",
    ]:
        if table in table_names:
            try:
                summary[f"{table}_rows"] = db.get_table_row_count(table)
            except Exception:
                summary[f"{table}_rows"] = 0

    if "income_sheet" in table_names:
        try:
            rows = db.execute_query(
                """
                SELECT DISTINCT report_period, report_year
                FROM income_sheet
                WHERE report_period IS NOT NULL AND report_period != ''
                ORDER BY report_year DESC, report_period DESC
                LIMIT 12
                """
            )
            summary["available_report_periods"] = [row["report_period"] for row in rows]
        except Exception:
            pass

    company_source = "company_info" if "company_info" in table_names else "income_sheet"
    if company_source in table_names:
        try:
            rows = db.execute_query(
                f"""
                SELECT DISTINCT stock_abbr
                FROM {company_source}
                WHERE stock_abbr IS NOT NULL AND stock_abbr != ''
                ORDER BY stock_abbr
                LIMIT 12
                """
            )
            summary["sample_companies"] = [row["stock_abbr"] for row in rows]
        except Exception:
            pass
    return summary


def emit_preflight_report(report: PreflightReport, print_fn=print, logger_instance=None):
    print_fn(f"\n[自检] {report.title}")
    if report.info:
        for key, value in report.info.items():
            if value in (None, "", [], {}):
                continue
            print_fn(f"  - {key}: {value}")
    if not report.errors and not report.warnings:
        print_fn("  - 未发现阻塞问题")
    for warning in report.warnings:
        print_fn(f"  - 警告: {warning}")
        if logger_instance:
            logger_instance.warning("%s", warning)
    for error in report.errors:
        print_fn(f"  - 错误: {error}")
        if logger_instance:
            logger_instance.error("%s", error)


def run_task1_preflight(config, sample_data_dir: Path) -> PreflightReport:
    report = PreflightReport("任务一运行前检查")
    report.extend(_check_llm_config(config, strict=True))

    sample_data_dir = Path(sample_data_dir)
    if not sample_data_dir.exists():
        report.errors.append(f"数据目录不存在: {sample_data_dir}")
        return report

    from .pdf_parser import scan_report_files

    reports = scan_report_files(str(sample_data_dir))
    pdf_paths = [Path(item.file_path) for item in reports if item.file_path]
    report.info["data_dir"] = str(sample_data_dir)
    report.info["pdf_count"] = len(pdf_paths)

    if not pdf_paths:
        report.errors.append("未扫描到财报 PDF，请检查 `示例数据/附件2：财务报告/` 目录是否存在且包含 PDF。")
        return report

    if len(pdf_paths) > 20:
        report.warnings.append(f"当前共检测到 {len(pdf_paths)} 份财报，任务一初次运行可能耗时较长。")

    ocr_status = _check_ocr_support()
    report.info["ocr_available"] = ocr_status["available"]
    scan_like = _detect_scan_like_pdfs(pdf_paths)
    if scan_like and not ocr_status["available"]:
        report.warnings.append(
            "检测到疑似扫描件 PDF，但当前环境未安装完整 OCR。"
            f" 示例文件: {', '.join(scan_like[:3])}"
        )
    elif scan_like:
        report.warnings.append(
            f"检测到疑似扫描件 PDF，当前已具备 OCR 条件，可在必要时补充 OCR 解析。示例文件: {', '.join(scan_like[:3])}"
        )
    return report


def run_task2_preflight(config, db) -> PreflightReport:
    report = PreflightReport("任务二运行前检查")
    report.extend(_check_llm_config(config, strict=True))
    report.extend(_check_visualization_environment())

    summary = _database_summary(db)
    report.info["available_report_periods"] = summary["available_report_periods"]
    report.info["sample_companies"] = summary["sample_companies"]

    if summary["income_sheet_rows"] <= 0:
        report.errors.append("income_sheet 为空，请先运行 task1/run_task1.py 构建财报数据库。")
    if summary["company_info_rows"] <= 0:
        report.warnings.append("company_info 为空，部分公司信息展示可能不完整。")
    if not summary["available_report_periods"]:
        report.warnings.append("数据库中没有可用报告期，SQL 查询很容易返回空结果。")
    return report


def run_task3_preflight(config, db, sample_data_dir: Path) -> PreflightReport:
    report = PreflightReport("任务三运行前检查")
    report.extend(_check_llm_config(config, strict=True))
    report.extend(_check_embedding_config(config, strict=True))
    report.extend(_check_visualization_environment())

    summary = _database_summary(db)
    report.info["available_report_periods"] = summary["available_report_periods"]
    report.info["sample_companies"] = summary["sample_companies"]
    report.info["research_reports_rows"] = summary["research_reports_rows"]
    report.info["knowledge_chunks_rows"] = summary["knowledge_chunks_rows"]

    if summary["income_sheet_rows"] <= 0:
        report.errors.append("income_sheet 为空，请先运行 task1/run_task1.py 构建财报数据库。")

    sample_data_dir = Path(sample_data_dir)
    attachment5_dir = _get_attachment_dir(sample_data_dir, ["附件5", "研报"])
    has_existing_kb = summary["research_reports_rows"] > 0 and summary["knowledge_chunks_rows"] > 0
    if not has_existing_kb and attachment5_dir is None:
        report.errors.append("既没有已有知识库数据，也未找到附件5研报目录，任务三无法构建知识库。")
    elif not has_existing_kb and attachment5_dir is not None:
        report.info["attachment5_dir"] = str(attachment5_dir)

    return report


def run_backend_preflight(config, db) -> PreflightReport:
    report = PreflightReport("后端启动自检")
    report.extend(_check_llm_config(config, strict=False))
    report.extend(_check_embedding_config(config, strict=False))
    report.extend(_check_visualization_environment())

    summary = _database_summary(db)
    report.info["available_report_periods"] = summary["available_report_periods"]
    report.info["sample_companies"] = summary["sample_companies"]

    if summary["income_sheet_rows"] <= 0:
        report.warnings.append("当前财报数据库为空，结构化查询和部分图表功能会返回空结果。")
    return report
