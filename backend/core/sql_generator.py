"""
SQL生成模块（优化版）
自然语言 → SQL查询语句
改进：更精确的prompt、更好的多轮上下文处理、数据单位规范
"""
import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# 数据库Schema描述模板
# =============================================================================

DB_SCHEMA_DESCRIPTION = """
你是一个专业的上市公司中药行业财报SQL生成助手。负责将用户的自然语言问题转换为SQLite SQL查询语句。

## 数据库表结构

### 1. company_info - 上市公司基本信息表
| 字段 | 类型 | 说明 | 示例值 |
|------|------|------|--------|
| stock_code | VARCHAR(20) | 股票代码 | 000999 |
| stock_abbr | VARCHAR(50) | 股票简称 | 华润三九, 金花股份 |
| company_name | TEXT | 公司全称 | 华润三九医药股份有限公司 |
| industry | TEXT | 所属行业 | 中药 |
| exchange | TEXT | 上市交易所 | 深圳证券交易所 |
| registered_area | TEXT | 注册区域 | 广东 |
| employee_count | INT | 雇员人数 | 15000 |

### 2. core_performance_indicators_sheet - 核心业绩指标表
| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| stock_code | VARCHAR(20) | 股票代码 | |
| stock_abbr | VARCHAR(50) | 股票简称 | |
| eps | DECIMAL(10,4) | 每股收益 | 元 |
| total_operating_revenue | DECIMAL(20,2) | 营业总收入 | 万元 |
| operating_revenue_yoy_growth | DECIMAL(10,4) | 营收同比增长率 | % |
| operating_revenue_qoq_growth | DECIMAL(10,4) | 营收季度环比增长率 | % |
| net_profit_10k_yuan | DECIMAL(20,2) | 净利润 | 万元 |
| net_profit_yoy_growth | DECIMAL(10,4) | 净利润同比增长率 | % |
| net_profit_qoq_growth | DECIMAL(10,4) | 净利润季度环比增长率 | % |
| net_asset_per_share | DECIMAL(10,4) | 每股净资产 | 元 |
| roe | DECIMAL(10,4) | 净资产收益率 | % |
| operating_cf_per_share | DECIMAL(10,4) | 每股经营现金流量 | 元 |
| net_profit_excl_non_recurring | DECIMAL(20,2) | 扣非净利润 | 万元 |
| net_profit_excl_non_recurring_yoy | DECIMAL(10,4) | 扣非净利润同比增长 | % |
| gross_profit_margin | DECIMAL(10,4) | 销售毛利率 | % |
| net_profit_margin | DECIMAL(10,4) | 销售净利率 | % |
| report_period | VARCHAR(20) | 报告期 | 如2023FY,2024Q1 |
| report_year | INT | 报告年份 | 2024 |

### 3. balance_sheet - 资产负债表
| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| stock_code/stock_abbr | | 股票代码/简称 | |
| asset_cash_and_cash_equivalents | DECIMAL(20,2) | 货币资金 | 万元 |
| asset_accounts_receivable | DECIMAL(20,2) | 应收账款 | 万元 |
| asset_inventory | DECIMAL(20,2) | 存货 | 万元 |
| asset_trading_financial_assets | DECIMAL(20,2) | 交易性金融资产 | 万元 |
| asset_construction_in_progress | DECIMAL(20,2) | 在建工程 | 万元 |
| asset_total_assets | DECIMAL(20,2) | 总资产 | 万元 |
| asset_total_assets_yoy_growth | DECIMAL(10,4) | 总资产同比增长 | % |
| liability_accounts_payable | DECIMAL(20,2) | 应付账款 | 万元 |
| liability_advance_from_customers | DECIMAL(20,2) | 预收账款 | 万元 |
| liability_total_liabilities | DECIMAL(20,2) | 总负债 | 万元 |
| liability_total_liabilities_yoy_growth | DECIMAL(10,4) | 总负债同比 | % |
| liability_contract_liabilities | DECIMAL(20,2) | 合同负债 | 万元 |
| liability_short_term_loans | DECIMAL(20,2) | 短期借款 | 万元 |
| asset_liability_ratio | DECIMAL(10,4) | 资产负债率 | % |
| equity_unappropriated_profit | DECIMAL(20,2) | 未分配利润 | 万元 |
| equity_total_equity | DECIMAL(20,2) | 股东权益合计 | 万元 |
| report_period | VARCHAR(20) | 报告期 | |
| report_year | INT | 报告年份 | |

### 4. income_sheet - 利润表
| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| stock_code/stock_abbr | | 股票代码/简称 | |
| net_profit | DECIMAL(20,2) | 净利润 | 万元 |
| net_profit_yoy_growth | DECIMAL(10,4) | 净利润同比 | % |
| other_income | DECIMAL(20,2) | 其他收益 | 万元 |
| total_operating_revenue | DECIMAL(20,2) | 营业总收入 | 万元 |
| operating_revenue_yoy_growth | DECIMAL(10,4) | 营收同比 | % |
| operating_expense_cost_of_sales | DECIMAL(20,2) | 营业成本 | 万元 |
| operating_expense_selling_expenses | DECIMAL(20,2) | 销售费用 | 万元 |
| operating_expense_administrative_expenses | DECIMAL(20,2) | 管理费用 | 万元 |
| operating_expense_financial_expenses | DECIMAL(20,2) | 财务费用 | 万元 |
| operating_expense_rnd_expenses | DECIMAL(20,2) | 研发费用 | 万元 |
| operating_expense_taxes_and_surcharges | DECIMAL(20,2) | 税金及附加 | 万元 |
| total_operating_expenses | DECIMAL(20,2) | 营业总支出 | 万元 |
| operating_profit | DECIMAL(20,2) | 营业利润 | 万元 |
| total_profit | DECIMAL(20,2) | 利润总额 | 万元 |
| asset_impairment_loss | DECIMAL(20,2) | 资产减值损失 | 万元 |
| credit_impairment_loss | DECIMAL(20,2) | 信用减值损失 | 万元 |
| report_period | VARCHAR(20) | 报告期 | |
| report_year | INT | 报告年份 | |

### 5. cash_flow_sheet - 现金流量表
| 字段 | 类型 | 说明 | 单位 |
|------|------|------|------|
| stock_code/stock_abbr | | 股票代码/简称 | |
| net_cash_flow | DECIMAL(20,2) | 净现金流 | 万元 |
| net_cash_flow_yoy_growth | DECIMAL(10,4) | 净现金流同比 | % |
| operating_cf_net_amount | DECIMAL(20,2) | 经营活动现金流净额 | 万元 |
| operating_cf_ratio_of_net_cf | DECIMAL(10,4) | 经营现金流占比 | % |
| operating_cf_cash_from_sales | DECIMAL(20,2) | 销售商品收到的现金 | 万元 |
| investing_cf_net_amount | DECIMAL(20,2) | 投资活动现金流净额 | 万元 |
| investing_cf_cash_for_investments | DECIMAL(20,2) | 投资支付的现金 | 万元 |
| investing_cf_cash_from_investment_recovery | DECIMAL(20,2) | 收回投资收到的现金 | 万元 |
| financing_cf_cash_from_borrowing | DECIMAL(20,2) | 取得借款收到的现金 | 万元 |
| financing_cf_cash_for_debt_repayment | DECIMAL(20,2) | 偿还债务支付的现金 | 万元 |
| financing_cf_net_amount | DECIMAL(20,2) | 融资活动现金流净额 | 万元 |
| report_period | VARCHAR(20) | 报告期 | |
| report_year | INT | 报告年份 | |

## 报告期(report_period)格式说明
- FY = 年报(FullYear)，如 2023FY, 2024FY（全年累计数据）
- Q1 = 一季报，如 2024Q1（1-3月累计数据）
- HY = 半年报，如 2024HY（1-6月累计数据）
- Q3 = 三季报，如 2024Q3（1-9月累计数据）

## 关键SQL生成规则
1. **使用SQLite语法**（不要用MySQL或PostgreSQL特有语法）
2. **金额单位全部为万元**
3. **百分比字段是百分比数值**（如15.5表示15.5%）
4. **使用stock_abbr匹配公司**（不要用company_name，stock_abbr是关键匹配字段）
5. **时间范围查询**：用report_period字段，格式严格为'年份+类型'如'2024FY'
6. **"近三年"理解为最近3个完整年份的年报(FY)**，用report_period LIKE '%FY'和report_year筛选
7. **"最新"指最近可用报告期**，使用ORDER BY report_year DESC, report_period DESC LIMIT 1
8. **对比多家企业**时用IN子句或JOIN，确保按公司分组
9. **排名Top N**用ORDER BY + LIMIT，确保DESC降序排列
10. **利润**一般指net_profit（净利润）或total_profit（利润总额），看上下文判断
11. **"营业收入"或"主营业务收入"**对应字段为total_operating_revenue
12. **同比增长**用对应的_yoy_growth字段，或者自行用LAG窗口函数计算
13. **查询所有企业排名时**不要加stock_abbr的WHERE条件
14. **年报数据优先**：在做年度对比时，优先使用FY（年报）数据，避免混用季报和年报
15. **同比计算**：如果数据库中没有直接的同比字段，使用子查询或LAG函数对比去年同期
"""

INTENT_ANALYSIS_PROMPT = """
分析以下用户问题的意图。这是一个中药上市公司财报智能问数系统。

用户问题：{question}
对话历史（最近几轮）：{history}

请仔细分析后返回严格的JSON格式（不要添加注释）：
{{
    "intent": "查询意图: basic_query | trend_analysis | comparison | ranking | calculation | visualization | knowledge_query | unclear",
    "entities": {{
        "company": "公司名称（如有）",
        "metric": "查询指标（如净利润、营业收入、总资产等）",
        "time_range": "时间范围描述",
        "other": "其他关键约束条件"
    }},
    "needs_clarification": false,
    "clarification_reason": "",
    "needs_chart": false,
    "chart_type": "line | bar | pie | table | none",
    "sql_needed": true,
    "is_followup": false,
    "followup_context": ""
}}

判断逻辑：
1. 如果问题提到"趋势""变化""近几年"，intent=trend_analysis，needs_chart=true，chart_type=line
2. 如果问题提到"排名""top""最高""最大"，intent=ranking，needs_chart=true，chart_type=bar
3. 如果问题提到"对比""比较""vs"，intent=comparison，needs_chart=true，chart_type=bar
4. 如果问题提到"绘图""可视化""图表""画图"，needs_chart=true
5. 如果对话历史中有上文且当前问题不完整（如"2025年第三季度的"），则is_followup=true，需要结合上文理解完整意图
6. 如果问题涉及行业政策、研报观点等非结构化信息，intent=knowledge_query，sql_needed=false
7. 只有当问题非常模糊无法确定任何具体查询目标时才设needs_clarification=true
"""

SQL_GENERATION_PROMPT = """
{schema}

## 用户问题
{question}

## 对话历史
{history}

## 意图分析
{intent}

请生成一条精确的SQLite SQL查询语句。

### 关键要求：
1. 只输出一条完整的SQL语句
2. 严格使用上述表名和字段名，不要臆造不存在的字段
3. 如果需要年度数据对比，筛选report_period LIKE '%FY'以只获取年报数据
4. 如果是查询"近三年"某公司，使用：WHERE stock_abbr = '公司名' AND report_period LIKE '%FY' ORDER BY report_year DESC LIMIT 3
5. 如果是Top N排名，确保使用正确的聚合和排序
6. 金额字段已经是万元单位，不需要额外换算
7. 如果问题是续问（多轮对话），结合历史推断完整查询意图
8. 对于"利润总额"使用income_sheet表的total_profit字段
9. 对于"净利润"使用core_performance_indicators_sheet的net_profit_10k_yuan或income_sheet的net_profit
10. 对于"营业收入/主营业务收入"使用total_operating_revenue字段

返回严格JSON格式（不要添加注释）：
{{
    "sql": "SELECT ... FROM ...",
    "explanation": "SQL查询的中文说明"
}}
"""

ANSWER_GENERATION_PROMPT = """
你是一个专业的中药上市公司财报分析师。请根据以下信息生成准确、专业的分析回答。

## 用户问题
{question}

## 执行的SQL查询
```sql
{sql}
```

## 查询返回数据
{result}

{knowledge_context}

## 意图分析
{intent}

### 回答要求：
1. **直接回答问题**：开头先给出明确的答案，再做分析展开
2. **数据准确**：使用查询结果中的具体数字，金额单位为万元
3. **格式清晰**：使用Markdown格式，包括标题、列表、表格等
4. **综合信息**：
   - **优先使用SQL查询结果**：如果SQL查询返回了数据，必须基于这些数据进行分析
   - **结合知识库内容**：如果提供了知识库参考资料，要结合这些资料提供更深入的分析和背景信息
   - **数据为主，知识为辅**：SQL查询的数据是核心，知识库内容用于补充说明、解释原因、提供行业背景等
5. **专业分析**：
   - 趋势分析要指出变化方向、幅度和可能原因（可参考知识库中的行业趋势）
   - 排名分析要点评排名靠前企业的特点（可结合知识库中的企业信息）
   - 对比分析要突出差异点（可用知识库内容解释差异原因）
6. **数据异常说明**：如果数据看起来异常（如数量级不对），主动说明可能原因
7. **结论建议**：最后给出简要结论

注意：
- SQL查询结果中的数据是回答的核心依据，必须准确使用
- 知识库内容用于补充分析、提供背景和解释，但不能替代SQL查询结果
- 不要杜撰数据，所有数据必须来源于查询结果或知识库
- 如果查询结果为空，说明可能的原因并给出建议
"""


class SQLGenerator:
    """SQL生成器"""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def analyze_intent(
        self,
        question: str,
        history: List[Dict] = None,
    ) -> Dict[str, Any]:
        """分析用户意图"""
        history_text = ""
        if history:
            recent = history[-6:]  # 最近3轮对话
            for h in recent:
                history_text += f"{h['role']}: {h['content'][:200]}\n"

        prompt = INTENT_ANALYSIS_PROMPT.format(
            question=question,
            history=history_text or "无"
        )

        try:
            result = await self.llm.query_json(prompt)
            # 如果是多轮对话的续问，自动补全问题上下文
            if result.get("is_followup") and history:
                for h in reversed(history):
                    if h["role"] == "user":
                        result["original_question"] = h["content"]
                        result["full_question"] = f"{h['content']}（用户补充：{question}）"
                        break
            return result
        except Exception as e:
            logger.warning(f"意图分析失败: {e}")
            return {
                "intent": "basic_query",
                "entities": {},
                "needs_clarification": False,
                "needs_chart": False,
                "chart_type": "none",
                "sql_needed": True,
            }

    async def generate_sql(
        self,
        question: str,
        intent: Dict[str, Any],
        history: List[Dict] = None,
    ) -> Dict[str, str]:
        """生成SQL查询"""
        # 如果是续问，使用完整问题
        effective_question = intent.get("full_question", question)

        history_text = ""
        if history:
            for h in history[-6:]:
                history_text += f"{h['role']}: {h['content'][:200]}\n"

        prompt = SQL_GENERATION_PROMPT.format(
            schema=DB_SCHEMA_DESCRIPTION,
            question=effective_question,
            history=history_text or "无",
            intent=json.dumps(intent, ensure_ascii=False),
        )

        try:
            result = await self.llm.query_json(prompt)
            # 基本SQL验证
            sql = result.get("sql", "")
            if sql:
                sql = self._clean_sql(sql)
                result["sql"] = sql
            return result
        except Exception as e:
            logger.error(f"SQL生成失败: {e}")
            return {"sql": "", "explanation": f"SQL生成失败: {str(e)}"}

    def _clean_sql(self, sql: str) -> str:
        """清理和规范化SQL语句"""
        # 移除markdown代码块标记
        sql = re.sub(r'```sql\s*', '', sql)
        sql = re.sub(r'```\s*', '', sql)
        sql = sql.strip().rstrip(';')
        # 移除多余空白行
        sql = re.sub(r'\n\s*\n', '\n', sql)
        return sql

    async def generate_answer(
        self,
        question: str,
        sql: str,
        query_result: Any,
        intent: Dict[str, Any],
        kb_context: str = "",
    ) -> str:
        """根据查询结果和知识库内容生成回答"""
        effective_question = intent.get("full_question", question)
        
        # 限制结果大小但保留完整性
        result_str = json.dumps(query_result, ensure_ascii=False, default=str)
        if len(result_str) > 4000:
            # 截断但保持JSON完整性
            result_str = json.dumps(query_result[:30], ensure_ascii=False, default=str)
            result_str += f"\n（共{len(query_result)}条结果，此处显示前30条）"

        # 构建知识库上下文部分
        if kb_context:
            knowledge_section = f"""
## 知识库参考资料
以下是从知识库中检索到的相关参考资料，可用于补充分析和提供背景信息：

{kb_context}

注意：这些参考资料用于补充SQL查询结果的分析，提供行业背景、解释原因等，但不能替代SQL查询的数据。
"""
        else:
            knowledge_section = ""

        prompt = ANSWER_GENERATION_PROMPT.format(
            question=effective_question,
            sql=sql,
            result=result_str,
            knowledge_context=knowledge_section,
            intent=json.dumps(intent, ensure_ascii=False),
        )

        return await self.llm.query(prompt)

    async def generate_clarification(
        self,
        question: str,
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        """生成澄清问题"""
        prompt = f"""
用户在一个中药上市公司财报智能问数系统中提问了一个需要补充信息的问题：
问题："{question}"

意图分析结果：{json.dumps(intent, ensure_ascii=False)}

请生成2-4个帮助用户明确查询意图的选项。选项要具体且与中药行业财报分析相关。

返回严格JSON格式（不要添加注释）：
{{
    "message": "向用户说明需要什么信息的友好提示",
    "options": [
        {{"label": "选项1的描述文字（用户看到的）", "value": "对应的具体查询意图"}},
        {{"label": "选项2的描述文字", "value": "对应的具体查询意图"}},
        {{"label": "选项3的描述文字", "value": "对应的具体查询意图"}}
    ]
}}

示例：对于模糊问题"金花股份怎么样"
{{
    "message": "请问您想了解金花股份的哪方面信息？",
    "options": [
        {{"label": "查看金花股份最新的财务指标（营收、净利润等）", "value": "查询金花股份最新一期的营业收入、净利润、每股收益等核心财务指标"}},
        {{"label": "分析金花股份近三年的业绩变化趋势", "value": "分析金花股份近三年的营业收入和净利润变化趋势并绘图"}},
        {{"label": "查看金花股份的基本信息", "value": "查询金花股份的股票代码、所属行业、注册区域等基本信息"}}
    ]
}}
"""
        try:
            return await self.llm.query_json(prompt)
        except Exception as e:
            logger.error(f"生成澄清问题失败: {e}")
            return {
                "message": "您的问题还需要更多信息以便精确查询：",
                "options": [
                    {"label": "请指定具体的公司名称", "value": "请补充要查询的具体公司"},
                    {"label": "请指定查询的时间范围", "value": "请补充查询的具体时间范围"},
                    {"label": "请指定要查询的财务指标", "value": "请补充要查询的具体财务指标"},
                ],
            }
