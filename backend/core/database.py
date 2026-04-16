"""
数据库模块
使用SQLite实现结构化财报数据库，支持四张核心表
"""
import sqlite3
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from contextlib import contextmanager

from .config import AppConfig, DB_PATH, DATA_DIR

logger = logging.getLogger(__name__)

# =============================================================================
# 数据库表结构定义（严格按照附件3）
# =============================================================================

CREATE_COMPANY_INFO_TABLE = """
CREATE TABLE IF NOT EXISTS company_info (
    serial_number INTEGER PRIMARY KEY,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    company_name TEXT,
    english_name TEXT,
    industry TEXT,
    exchange TEXT,
    security_type TEXT,
    registered_area TEXT,
    registered_capital TEXT,
    employee_count INTEGER,
    management_count INTEGER
);
"""

CREATE_CORE_PERFORMANCE_TABLE = """
CREATE TABLE IF NOT EXISTS core_performance_indicators_sheet (
    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    eps DECIMAL(10,4),
    total_operating_revenue DECIMAL(20,2),
    operating_revenue_yoy_growth DECIMAL(10,4),
    operating_revenue_qoq_growth DECIMAL(10,4),
    net_profit_10k_yuan DECIMAL(20,2),
    net_profit_yoy_growth DECIMAL(10,4),
    net_profit_qoq_growth DECIMAL(10,4),
    net_asset_per_share DECIMAL(10,4),
    roe DECIMAL(10,4),
    operating_cf_per_share DECIMAL(10,4),
    net_profit_excl_non_recurring DECIMAL(20,2),
    net_profit_excl_non_recurring_yoy DECIMAL(10,4),
    gross_profit_margin DECIMAL(10,4),
    net_profit_margin DECIMAL(10,4),
    roe_weighted_excl_non_recurring DECIMAL(10,4),
    report_period VARCHAR(20),
    report_year INT,
    UNIQUE(stock_code, report_period)
);
"""

CREATE_BALANCE_SHEET_TABLE = """
CREATE TABLE IF NOT EXISTS balance_sheet (
    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    asset_cash_and_cash_equivalents DECIMAL(20,2),
    asset_accounts_receivable DECIMAL(20,2),
    asset_inventory DECIMAL(20,2),
    asset_trading_financial_assets DECIMAL(20,2),
    asset_construction_in_progress DECIMAL(20,2),
    asset_total_assets DECIMAL(20,2),
    asset_total_assets_yoy_growth DECIMAL(10,4),
    liability_accounts_payable DECIMAL(20,2),
    liability_advance_from_customers DECIMAL(20,2),
    liability_total_liabilities DECIMAL(20,2),
    liability_total_liabilities_yoy_growth DECIMAL(10,4),
    liability_contract_liabilities DECIMAL(20,2),
    liability_short_term_loans DECIMAL(20,2),
    asset_liability_ratio DECIMAL(10,4),
    equity_unappropriated_profit DECIMAL(20,2),
    equity_total_equity DECIMAL(20,2),
    report_period VARCHAR(20),
    report_year INT,
    UNIQUE(stock_code, report_period)
);
"""

CREATE_CASH_FLOW_TABLE = """
CREATE TABLE IF NOT EXISTS cash_flow_sheet (
    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    net_cash_flow DECIMAL(20,2),
    net_cash_flow_yoy_growth DECIMAL(10,4),
    operating_cf_net_amount DECIMAL(20,2),
    operating_cf_ratio_of_net_cf DECIMAL(10,4),
    operating_cf_cash_from_sales DECIMAL(20,2),
    investing_cf_net_amount DECIMAL(20,2),
    investing_cf_ratio_of_net_cf DECIMAL(10,4),
    investing_cf_cash_for_investments DECIMAL(20,2),
    investing_cf_cash_from_investment_recovery DECIMAL(20,2),
    financing_cf_cash_from_borrowing DECIMAL(20,2),
    financing_cf_cash_for_debt_repayment DECIMAL(20,2),
    financing_cf_net_amount DECIMAL(20,2),
    financing_cf_ratio_of_net_cf DECIMAL(10,4),
    report_period VARCHAR(20),
    report_year INT,
    UNIQUE(stock_code, report_period)
);
"""

CREATE_INCOME_TABLE = """
CREATE TABLE IF NOT EXISTS income_sheet (
    serial_number INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code VARCHAR(20),
    stock_abbr VARCHAR(50),
    net_profit DECIMAL(20,2),
    net_profit_yoy_growth DECIMAL(10,4),
    other_income DECIMAL(20,2),
    total_operating_revenue DECIMAL(20,2),
    operating_revenue_yoy_growth DECIMAL(10,4),
    operating_expense_cost_of_sales DECIMAL(20,2),
    operating_expense_selling_expenses DECIMAL(20,2),
    operating_expense_administrative_expenses DECIMAL(20,2),
    operating_expense_financial_expenses DECIMAL(20,2),
    operating_expense_rnd_expenses DECIMAL(20,2),
    operating_expense_taxes_and_surcharges DECIMAL(20,2),
    total_operating_expenses DECIMAL(20,2),
    operating_profit DECIMAL(20,2),
    total_profit DECIMAL(20,2),
    investment_income DECIMAL(20,2),
    fair_value_change_income DECIMAL(20,2),
    asset_disposal_income DECIMAL(20,2),
    non_operating_income DECIMAL(20,2),
    non_operating_expenses DECIMAL(20,2),
    asset_impairment_loss DECIMAL(20,2),
    credit_impairment_loss DECIMAL(20,2),
    report_period VARCHAR(20),
    report_year INT,
    UNIQUE(stock_code, report_period)
);
"""

# 知识库相关表
CREATE_KNOWLEDGE_CHUNKS_TABLE = """
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type VARCHAR(50),
    source_path TEXT,
    source_title TEXT,
    chunk_index INTEGER,
    content TEXT,
    metadata TEXT,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_RESEARCH_REPORTS_TABLE = """
CREATE TABLE IF NOT EXISTS research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    report_type VARCHAR(20),
    stock_name VARCHAR(50),
    stock_code VARCHAR(20),
    org_name TEXT,
    org_sname VARCHAR(50),
    publish_date TEXT,
    industry_name VARCHAR(50),
    rating_name VARCHAR(20),
    researcher TEXT,
    file_path TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CHAT_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(50),
    role VARCHAR(20),
    content TEXT,
    metadata TEXT,
    images TEXT,
    "references" TEXT,
    sql TEXT,
    chart_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    timestamp INTEGER
);
"""


class DatabaseManager:
    """SQLite数据库管理器"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(DB_PATH)
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def get_connection(self):
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """初始化数据库，创建所有表"""
        with self.get_connection() as conn:
            conn.execute(CREATE_COMPANY_INFO_TABLE)
            conn.execute(CREATE_CORE_PERFORMANCE_TABLE)
            conn.execute(CREATE_BALANCE_SHEET_TABLE)
            conn.execute(CREATE_CASH_FLOW_TABLE)
            conn.execute(CREATE_INCOME_TABLE)
            conn.execute(CREATE_KNOWLEDGE_CHUNKS_TABLE)
            conn.execute(CREATE_RESEARCH_REPORTS_TABLE)
            conn.execute(CREATE_CHAT_HISTORY_TABLE)
            logger.info(f"数据库初始化完成: {self.db_path}")

    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """执行查询SQL并返回字典列表"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            columns = [description[0] for description in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

    def execute_sql(self, sql: str, params: tuple = ()) -> int:
        """执行非查询SQL，返回影响行数"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.rowcount

    def insert_many(self, table: str, records: List[Dict], replace: bool = True):
        """批量插入记录"""
        if not records:
            return

        columns = list(records[0].keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        action = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        sql = f"{action} INTO {table} ({col_names}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            data = [tuple(r.get(c) for c in columns) for r in records]
            conn.executemany(sql, data)
            logger.info(f"批量插入 {table}: {len(records)} 条记录")

    def insert_record(self, table: str, record: Dict, replace: bool = True) -> int:
        """插入单条记录，返回rowid"""
        columns = list(record.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_names = ", ".join(columns)
        action = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE"
        sql = f"{action} INTO {table} ({col_names}) VALUES ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.execute(sql, tuple(record.values()))
            return cursor.lastrowid

    def get_table_info(self, table: str) -> List[Dict]:
        """获取表结构信息"""
        return self.execute_query(f"PRAGMA table_info({table})")

    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        rows = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [r["name"] for r in rows]

    def get_table_row_count(self, table: str) -> int:
        """获取表行数"""
        result = self.execute_query(f"SELECT COUNT(*) as cnt FROM {table}")
        return result[0]["cnt"] if result else 0

    def get_database_schema(self) -> str:
        """获取完整的数据库Schema描述（供LLM使用）"""
        tables = self.get_table_names()
        schema_parts = []
        for table in tables:
            info = self.get_table_info(table)
            cols = []
            for col in info:
                col_desc = f"  {col['name']} {col['type']}"
                if col['pk']:
                    col_desc += " PRIMARY KEY"
                if col['notnull']:
                    col_desc += " NOT NULL"
                cols.append(col_desc)
            count = self.get_table_row_count(table)
            schema_parts.append(
                f"表名: {table} (共{count}条记录)\n" + "\n".join(cols)
            )
        return "\n\n".join(schema_parts)

    def safe_execute_query(self, sql: str) -> Tuple[bool, Any]:
        """安全执行SQL查询（用于用户输入的SQL）"""
        # 安全检查：只允许SELECT语句
        sql_stripped = sql.strip().upper()
        if not sql_stripped.startswith("SELECT"):
            return False, "安全限制：只允许执行SELECT查询语句"

        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
        for kw in dangerous_keywords:
            if kw in sql_stripped:
                return False, f"安全限制：不允许包含 {kw} 关键字"

        try:
            results = self.execute_query(sql)
            return True, results
        except Exception as e:
            return False, f"SQL执行错误: {str(e)}"
