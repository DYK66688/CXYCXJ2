# Core modules for the Financial Report Smart Q&A System
from .config import AppConfig, LLMConfig, EmbeddingConfig, PROJECT_ROOT, DATA_DIR, RESULTS_DIR
from .database import DatabaseManager
from .llm_client import LLMClient
from .embedding import EmbeddingManager
from .pdf_parser import (
    scan_report_files, extract_text_from_pdf, extract_tables_from_pdf,
    classify_report_by_content, extract_financial_data_by_rules,
    parse_report_meta_shanghai, parse_report_meta_shenzhen,
    ReportMeta, FinancialData
)
from .sql_generator import SQLGenerator
from .visualizer import ChartGenerator, generate_chart, CHART_STYLES
from .knowledge_base import KnowledgeBase
from .agent import SmartQAAgent, AgentResponse

__all__ = [
    "AppConfig", "LLMConfig", "EmbeddingConfig",
    "DatabaseManager", "LLMClient", "EmbeddingManager",
    "SQLGenerator", "ChartGenerator", "KnowledgeBase",
    "SmartQAAgent", "AgentResponse",
    "scan_report_files", "extract_text_from_pdf", "extract_tables_from_pdf",
    "classify_report_by_content", "extract_financial_data_by_rules",
    "generate_chart", "CHART_STYLES",
    "PROJECT_ROOT", "DATA_DIR", "RESULTS_DIR",
]
