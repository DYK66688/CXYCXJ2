"""
智能问答Agent模块（优化版）
改进：
1. 更好的多轮对话上下文处理
2. 知识库优先判断（非SQL问题直接走知识库）
3. 更精确的意图澄清触发
4. 完整的归因分析链路
5. 步骤详情包含更多可展示数据
"""
import logging
import json
import re
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from .database import DatabaseManager
from .llm_client import LLMClient
from .sql_generator import SQLGenerator
from .visualizer import ChartGenerator
from .knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


@dataclass
class AgentStep:
    """Agent执行步骤"""
    step_type: str
    input_data: Any = None
    output_data: Any = None
    status: str = "pending"
    error: str = ""
    timestamp: str = ""
    duration_ms: int = 0

    def to_dict(self):
        return {
            "step_type": self.step_type,
            "status": self.status,
            "input": str(self.input_data)[:500] if self.input_data else None,
            "output": str(self.output_data)[:1000] if self.output_data else None,
            "error": self.error,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
        }


@dataclass
class AgentResponse:
    """Agent回复"""
    content: str = ""
    images: List[str] = field(default_factory=list)
    references: List[Dict] = field(default_factory=list)
    reasoning_explanation: str = ""  # 推理依据说明
    sql: str = ""
    steps: List[AgentStep] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_data: Dict = field(default_factory=dict)
    chart_type: str = ""
    query_result: Any = None

    def to_dict(self):
        result = {
            "content": self.content,
            "images": self.images,
            "sql": self.sql,
            "steps": [s.to_dict() for s in self.steps],
            "needs_clarification": self.needs_clarification,
            "chart_type": self.chart_type,
        }
        if self.references:
            result["references"] = self.references
        if self.clarification_data:
            result["clarification_data"] = self.clarification_data
        if self.query_result:
            result["query_result"] = self.query_result[:20] if isinstance(self.query_result, list) else self.query_result
        return result

    def to_submission_format(self, question: str) -> Dict:
        """转换为提交格式（包含SQL和chart_type）"""
        submission = {
            "Q": question,
            "A": {"content": self.content}
        }
        if self.images:
            submission["A"]["image"] = self.images
        if self.references:
            submission["A"]["references"] = self.references
        # 添加SQL和chart_type到结果中（用于result_3.xlsx）
        if self.sql:
            submission["sql"] = self.sql
        if self.chart_type:
            submission["chart_type"] = self.chart_type
        return submission


class SmartQAAgent:
    """智能问数Agent（优化版）"""

    def __init__(
        self,
        db: DatabaseManager,
        llm: LLMClient,
        knowledge_base: Optional[KnowledgeBase] = None,
        results_dir: str = "./results",
    ):
        self.db = db
        self.llm = llm
        self.sql_gen = SQLGenerator(llm)
        self.chart_gen = ChartGenerator(llm)
        self.kb = knowledge_base
        self.results_dir = results_dir
        self.sessions: Dict[str, List[Dict]] = {}
        
        # 加载RAG配置
        try:
            from backend.core.config import AppConfig
            self._rag_config = AppConfig.load().rag
        except:
            self._rag_config = None

    def get_or_create_session(self, session_id: str = None) -> str:
        if session_id:
            if session_id in self.sessions:
                return session_id
            # 尝试从数据库加载历史
            history = self.load_chat_history(session_id)
            if history:
                self.sessions[session_id] = history
                return session_id
        new_id = session_id or str(uuid.uuid4())[:8]
        self.sessions[new_id] = []
        return new_id

    async def process_question(
        self,
        question: str,
        session_id: str = None,
        enhanced_mode: bool = False,
        question_id: str = "",
    ) -> AgentResponse:
        """处理用户问题（完整流程）"""
        session_id = self.get_or_create_session(session_id)
        history = self.sessions[session_id]
        response = AgentResponse()

        def add_step(step_type, input_data=None):
            step = AgentStep(
                step_type=step_type,
                input_data=input_data,
                timestamp=datetime.now().isoformat(),
            )
            response.steps.append(step)
            return step

        try:
            # ===== Step 1: 意图分析 =====
            step = add_step("intent_analysis", question)
            step.status = "running"
            logger.info(f"[{session_id}] Step 1: 意图分析 - {question}")

            intent = await self.sql_gen.analyze_intent(question, history)
            step.output_data = intent
            step.status = "completed"

            intent_type = intent.get("intent", "basic_query")
            logger.info(f"[{session_id}] 意图: {intent_type}, 需要图表: {intent.get('needs_chart')}")

            # ===== Step 2: 判断是否需要澄清 =====
            if intent.get("needs_clarification"):
                step = add_step("clarification")
                step.status = "running"
                clarification = await self.sql_gen.generate_clarification(question, intent)
                response.needs_clarification = True
                response.clarification_data = clarification
                response.content = clarification.get("message", "请补充更多信息")
                step.output_data = clarification
                step.status = "completed"

                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": response.content})
                self._save_chat_history(session_id, question, response.content, response)
                return response

            # ===== Step 2b: 知识库查询路径（非SQL问题） =====
            if intent_type == "knowledge_query" or not intent.get("sql_needed", True):
                response = await self._handle_knowledge_query(
                    question, intent, history, question_id, enhanced_mode
                )
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": response.content})
                self._save_chat_history(session_id, question, response.content, response)
                return response

            # ===== Step 2c: 增强模式 - 多意图规划 =====
            if enhanced_mode:
                step = add_step("planning", question)
                step.status = "running"
                sub_tasks = await self._plan_multi_intent(question, intent, history)
                step.output_data = sub_tasks
                step.status = "completed"
                logger.info(f"[{session_id}] 规划子任务: {len(sub_tasks)} 个")

                if len(sub_tasks) > 1:
                    all_results = []
                    all_sql = []
                    all_chart_types = []
                    for i, sub_task in enumerate(sub_tasks):
                        sub_response = await self._execute_single_query(
                            sub_task["question"], intent, history, question_id, i + 1
                        )
                        all_results.append(sub_response)
                        if sub_response.sql:
                            all_sql.append(sub_response.sql)
                        if sub_response.chart_type:
                            all_chart_types.append(sub_response.chart_type)
                        response.images.extend(sub_response.images)
                        response.steps.extend(sub_response.steps)

                    # 整合结果
                    step = add_step("merge_results")
                    step.status = "running"
                    response.content = await self._merge_results(question, all_results)
                    response.sql = "; ".join(all_sql)
                    response.chart_type = ", ".join(all_chart_types) if all_chart_types else ""
                    # 合并查询结果
                    all_query_results = []
                    for r in all_results:
                        if r.query_result:
                            all_query_results.extend(r.query_result[:10])
                    response.query_result = all_query_results
                    step.status = "completed"

                    # 归因分析
                    if self.kb:
                        attr_step = add_step("attribution_analysis")
                        attr_step.status = "running"
                        attr_result = await self._attribution_analysis(question, response.content)
                        response.references = attr_result.get("references", [])
                        response.reasoning_explanation = attr_result.get("reasoning_explanation", "")
                        attr_step.output_data = f"找到 {len(response.references)} 条参考来源"
                        attr_step.status = "completed"

                    history.append({"role": "user", "content": question})
                    history.append({"role": "assistant", "content": response.content})
                    self._save_chat_history(session_id, question, response.content, response)
                    return response

            # ===== Step 3: 单一查询处理 =====
            single_response = await self._execute_single_query(
                question, intent, history, question_id, 1
            )
            response.content = single_response.content
            response.sql = single_response.sql
            response.images = single_response.images
            response.chart_type = single_response.chart_type
            response.query_result = single_response.query_result
            response.steps.extend(single_response.steps)

            # 增强模式：归因分析（知识库检索已在_execute_single_query中完成）
            if enhanced_mode and self.kb:
                # 归因分析
                attr_step = add_step("attribution_analysis")
                attr_step.status = "running"
                attr_result = await self._attribution_analysis(question, response.content)
                response.references = attr_result.get("references", [])
                response.reasoning_explanation = attr_result.get("reasoning_explanation", "")
                attr_step.output_data = f"找到 {len(response.references)} 条参考来源"
                attr_step.status = "completed"

            # 记录历史并持久化
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": response.content})
            self._save_chat_history(session_id, question, response.content)

        except Exception as e:
            logger.error(f"[{session_id}] 处理失败: {e}", exc_info=True)
            response.content = f"处理过程中出现错误: {str(e)}"
            if response.steps:
                response.steps[-1].status = "failed"
                response.steps[-1].error = str(e)

        return response

    async def _handle_knowledge_query(
        self,
        question: str,
        intent: Dict,
        history: List[Dict],
        question_id: str,
        enhanced_mode: bool,
    ) -> AgentResponse:
        """处理知识库查询（非SQL问题）"""
        response = AgentResponse()

        step = AgentStep(step_type="knowledge_search", timestamp=datetime.now().isoformat())
        step.status = "running"
        response.steps.append(step)

        if self.kb:
            kb_results = self.kb.search(question, top_k=15, min_score=0.2)
            step.output_data = f"找到 {len(kb_results)} 条相关知识"
            step.status = "completed"

            if kb_results:
                context = "\n\n---\n\n".join([
                    f"来源: {r.get('source_title', r.get('source_path', '未知'))}\n{r['content']}"
                    for r in kb_results[:5]
                ])

                # 生成基于知识库的回答
                answer_step = AgentStep(step_type="answer_generation", timestamp=datetime.now().isoformat())
                answer_step.status = "running"
                response.steps.append(answer_step)

                prompt = f"""
你是一个专业的中药行业上市公司财报分析师。请根据以下知识库检索到的参考资料回答用户问题。

## 用户问题
{question}

## 参考资料
{context}

## 回答要求：
1. 直接回答用户问题，引用具体数据和事实
2. 标注信息来源（如"根据XX研报"）
3. 使用Markdown格式，包括标题、列表、表格等
4. 如果资料中没有直接答案，基于已有信息做合理推断并说明
5. 给出专业分析和结论
"""
                response.content = await self.llm.query(prompt)
                answer_step.status = "completed"

                # 添加归因引用
                response.references = [
                    {
                        "paper_path": r.get("source_path", ""),
                        "text": r["content"][:500],
                    }
                    for r in kb_results[:5]
                ]
            else:
                response.content = await self.llm.query(
                    question,
                    system="你是一个专业的中药行业上市公司财报分析师。如果你无法回答问题，请说明原因并给出建议。"
                )
        else:
            response.content = await self.llm.query(
                question,
                system="你是一个专业的中药行业上市公司财报分析师。"
            )

        return response

    async def _execute_single_query(
        self,
        question: str,
        intent: Dict,
        history: List[Dict],
        question_id: str = "",
        chart_index: int = 1,
    ) -> AgentResponse:
        """执行单个SQL查询"""
        response = AgentResponse()
        # 如果是续问，使用完整问题
        effective_question = intent.get("full_question", question)

        # SQL生成
        step = AgentStep(step_type="sql_generation", timestamp=datetime.now().isoformat())
        step.status = "running"
        response.steps.append(step)

        sql_result = await self.sql_gen.generate_sql(effective_question, intent, history)
        sql = sql_result.get("sql", "")
        response.sql = sql
        step.output_data = sql_result
        step.status = "completed"
        logger.info(f"生成SQL: {sql}")

        # 执行查询
        if sql:
            step = AgentStep(step_type="query_execution", timestamp=datetime.now().isoformat())
            step.status = "running"
            response.steps.append(step)

            success, query_data = self.db.safe_execute_query(sql)
            step.output_data = {
                "success": success,
                "row_count": len(query_data) if isinstance(query_data, list) else 0,
            }

            if success:
                response.query_result = query_data
                step.status = "completed"
                logger.info(f"查询结果: {len(query_data)} 行")

                if not query_data:
                    diagnosis_step = AgentStep(step_type="query_diagnosis", timestamp=datetime.now().isoformat())
                    diagnosis_step.status = "running"
                    response.steps.append(diagnosis_step)
                    diagnosis = self._diagnose_empty_query_result(sql)
                    diagnosis_step.output_data = diagnosis
                    diagnosis_step.status = "completed"
                    response.content = diagnosis["message"]
                    return response

                # 图表生成
                if intent.get("needs_chart") and query_data:
                    chart_step = AgentStep(step_type="visualization", timestamp=datetime.now().isoformat())
                    chart_step.status = "running"
                    response.steps.append(chart_step)

                    prefix = f"{question_id}_{chart_index}" if question_id else f"chart_{chart_index}"
                    chart_path = await self.chart_gen.auto_generate_chart(
                        question=effective_question,
                        sql_result=query_data,
                        intent=intent,
                        save_dir=self.results_dir,
                        file_prefix=prefix,
                    )
                    if chart_path:
                        response.images.append(chart_path)
                        response.chart_type = intent.get("chart_type", "")
                        chart_step.output_data = chart_path
                    chart_step.status = "completed"

                # 知识库检索（在生成回答之前进行，使用配置参数）
                kb_context = ""
                if self.kb:
                    kb_step = AgentStep(step_type="knowledge_search", timestamp=datetime.now().isoformat())
                    kb_step.status = "running"
                    response.steps.append(kb_step)
                    
                    rag_config = getattr(self, '_rag_config', None)
                    top_k = rag_config.top_k if rag_config else 10
                    min_score = rag_config.min_score if rag_config else 0.2
                    max_context = rag_config.max_kb_context_chunks if rag_config else 8
                    
                    kb_results = self.kb.search(effective_question, top_k=top_k, min_score=min_score)
                    if kb_results:
                        kb_context = "\n\n---\n\n".join([
                            f"来源: {r.get('source_title', r.get('source_path', '未知'))}\n内容: {r['content']}"
                            for r in kb_results[:max_context]
                        ])
                    kb_step.output_data = f"找到 {len(kb_results)} 条相关知识"
                    kb_step.status = "completed"

                # 生成回答（包含SQL结果和知识库内容）
                answer_step = AgentStep(step_type="answer_generation", timestamp=datetime.now().isoformat())
                answer_step.status = "running"
                response.steps.append(answer_step)

                response.content = await self.sql_gen.generate_answer(
                    effective_question, sql, query_data, intent, kb_context=kb_context
                )
                answer_step.status = "completed"
            else:
                step.status = "failed"
                step.error = str(query_data)
                # SQL执行失败，尝试知识库（使用配置参数）
                if self.kb:
                    rag_config = getattr(self, '_rag_config', None)
                    top_k = rag_config.top_k if rag_config else 10
                    min_score = rag_config.min_score if rag_config else 0.2
                    kb_results = self.kb.search(question, top_k=top_k, min_score=min_score)
                    if kb_results:
                        context = "\n\n".join([r["content"] for r in kb_results])
                        response.content = await self.llm.query(
                            f"SQL查询执行失败。请基于以下参考资料回答问题：\n\n问题：{question}\n\n参考资料：\n{context}"
                        )
                    else:
                        response.content = f"查询执行失败: {query_data}\n\n建议：请检查查询条件是否正确。"
                else:
                    response.content = f"查询执行失败: {query_data}"
        else:
            # 没有SQL生成，走知识库（使用配置参数）
            if self.kb:
                rag_config = getattr(self, '_rag_config', None)
                top_k = rag_config.top_k if rag_config else 10
                min_score = rag_config.min_score if rag_config else 0.2
                kb_results = self.kb.search(question, top_k=top_k, min_score=min_score)
                if kb_results:
                    context = "\n\n".join([r["content"] for r in kb_results])
                    response.content = await self.llm.query(
                        f"基于以下参考资料回答问题：\n\n问题：{question}\n\n参考资料：\n{context}",
                        system="你是一个专业的中药行业上市公司财报分析师。请用专业、准确的语言回答。"
                    )
                else:
                    response.content = await self.llm.query(
                        question,
                        system="你是一个专业的中药行业上市公司财报分析师。如果你无法回答问题，请说明原因。"
                    )
            else:
                response.content = "抱歉，无法生成有效的查询语句。请尝试更具体的提问。"

        return response

    async def _plan_multi_intent(
        self,
        question: str,
        intent: Dict,
        history: List[Dict],
    ) -> List[Dict]:
        """多意图规划"""
        prompt = f"""
分析以下用户问题，将其拆解为多个独立的、可按顺序执行的子任务。

用户问题：{question}

这是一个中药上市公司财报分析系统，可以查询的数据包括：
- 核心业绩指标（营收、净利润、每股收益、毛利率等）
- 资产负债表（总资产、总负债、应收账款等）
- 利润表（营业收入、营业成本、各项费用等）
- 现金流量表（经营/投资/融资现金流等）
- 知识库（行业研报、个股研报）

返回严格JSON格式（不要添加注释）：
{{
    "sub_tasks": [
        {{
            "question": "子任务1的完整、独立可查询的问题",
            "type": "sql_query | knowledge_query | analysis",
            "priority": 1,
            "depends_on": []
        }}
    ]
}}

规则：
1. 如果问题只有一个意图，只返回一个子任务
2. 每个子任务的question必须是完整的、独立可执行的查询
3. 子任务按执行优先级排序
4. 如果子任务之间有依赖关系，在depends_on中标注前置任务的索引
"""
        try:
            result = await self.llm.query_json(prompt)
            tasks = result.get("sub_tasks", [{"question": question, "type": "sql_query", "priority": 1}])
            # 确保至少有一个任务
            if not tasks:
                tasks = [{"question": question, "type": "sql_query", "priority": 1}]
            return tasks
        except Exception:
            return [{"question": question, "type": "sql_query", "priority": 1}]

    async def _merge_results(self, question: str, sub_responses: List[AgentResponse]) -> str:
        """整合多个子任务的结果"""
        parts = []
        for i, resp in enumerate(sub_responses):
            parts.append(f"### 子任务{i+1}分析结果：\n{resp.content}")

        # 先计算joined字符串，避免f-string中表达式部分包含反斜杠
        joined_parts = "\n\n".join(parts)

        prompt = f"""
用户的原始问题是：{question}

以下是各个子任务的分析结果：

{joined_parts}

请将以上结果整合为一个连贯、完整的回答。要求：
1. 使用Markdown格式，逻辑清晰，结构完整
2. 包含所有子任务的关键信息和数据
3. 给出综合分析和结论
4. 直接在开头回答用户的核心问题
5. 如果有数据表格，保持表格格式
"""
        return await self.llm.query(prompt)

    async def _attribution_analysis(self, question: str, answer: str) -> Dict:
        """归因分析 - 查找回答的证据来源（增强版），并生成推理依据说明"""
        if not self.kb:
            return {"references": [], "reasoning_explanation": ""}

        # 使用配置中的RAG参数
        rag_config = getattr(self, '_rag_config', None)
        if not rag_config:
            # 尝试从全局config获取
            try:
                from backend.core.config import AppConfig
                rag_config = AppConfig.load().rag
            except:
                rag_config = None
        
        top_k = rag_config.top_k if rag_config else 10
        min_score = rag_config.min_score if rag_config else 0.2
        max_results = rag_config.max_attribution_results if rag_config else 15
        
        # 策略1: 使用原始问题搜索（使用配置参数）
        results = self.kb.search(question, top_k=top_k, min_score=min_score)

        # 策略2: 如果结果不足，从回答中提取关键词再次搜索
        if len(results) < 5:
            # 提取回答中的关键实体（公司名、指标名等）
            import re
            # 提取中文公司名（2-6个字符）
            companies = re.findall(r'[\u4e00-\u9fa5]{2,6}(?:股份|集团|企业|公司)', answer)
            for company in companies[:3]:
                if company:
                    additional = self.kb.search(company, top_k=min(5, top_k), min_score=min_score * 0.75)
                    # 去重合并
                    seen_paths = {r.get("source_path", "") for r in results}
                    for r in additional:
                        if r.get("source_path", "") not in seen_paths:
                            results.append(r)
                            seen_paths.add(r.get("source_path", ""))

        # 策略3: 如果仍然不足，使用问题关键词
        if len(results) < 5:
            keywords = question[:50]
            additional = self.kb.search(keywords, top_k=min(5, top_k), min_score=min_score * 0.75)
            seen_paths = {r.get("source_path", "") for r in results}
            for r in additional:
                if r.get("source_path", "") not in seen_paths:
                    results.append(r)
                    seen_paths.add(r.get("source_path", ""))

        # 按相似度排序并去重
        results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        references = []
        seen_paths = set()
        for r in results[:max_results]:  # 使用配置的最大结果数
            path = r.get("source_path", "")
            if path in seen_paths:
                continue
            seen_paths.add(path)
            ref = {
                "paper_path": path,
                "text": r["content"][:800],  # 增加文本长度以提供更完整的引用
                "score": round(r.get("score", 0), 3),
                "source_title": r.get("source_title", ""),
            }
            if r.get("metadata", {}).get("paper_image"):
                ref["paper_image"] = r["metadata"]["paper_image"]
            references.append(ref)

        # 使用LLM生成推理依据说明
        reasoning_explanation = ""
        if references:
            # 准备参考文档摘要
            ref_summary = "\n\n".join([
                f"证据{i+1}（相似度{ref['score']}）: {ref['source_title'] or ref['paper_path']}\n{ref['text'][:200]}"
                for i, ref in enumerate(references[:5])
            ])
            
            prompt = f"""你是一个专业的财务分析师。请根据以下信息，生成一段关于回答生成逻辑的推理依据说明。

用户问题：{question}

回答摘要：{answer[:500]}

参考的知识库证据：
{ref_summary}

请生成一段200-300字的推理依据说明，要求：
1. 说明系统如何通过语义检索找到相关证据
2. 解释这些证据如何支撑最终回答
3. 强调结果的可追溯性和可解释性
4. 语言专业、清晰、有说服力

直接输出说明文字，不要包含标题或格式标记。"""

            try:
                reasoning_explanation = await self.llm.query(prompt)
            except Exception as e:
                logger.warning(f"生成推理依据说明失败: {e}")
                reasoning_explanation = "系统通过语义检索从知识库中找到与问题相关的文档片段，并按照相似度排序。这些证据片段构成了回答的支撑依据，确保了结果的可追溯性和可解释性。"

        return {
            "references": references,
            "reasoning_explanation": reasoning_explanation
        }

    async def process_conversation(
        self,
        questions: List[Dict],
        enhanced_mode: bool = False,
        question_id: str = "",
    ) -> List[Dict]:
        """处理一组多轮对话问题（用于提交格式）"""
        session_id = self.get_or_create_session()
        results = []

        for i, q in enumerate(questions):
            question_text = q["Q"]
            chart_index = i + 1

            response = await self.process_question(
                question=question_text,
                session_id=session_id,
                enhanced_mode=enhanced_mode,
                question_id=f"{question_id}_{chart_index}" if question_id else "",
            )

            submission = response.to_submission_format(question_text)
            # 确保SQL和chart_type也包含在结果中
            if response.sql:
                submission["sql"] = response.sql
            if response.chart_type:
                submission["chart_type"] = response.chart_type
            results.append(submission)
            logger.info(f"完成问题 [{question_id}] 第{chart_index}轮: {question_text[:50]}...")

        return results

    def _save_chat_history(self, session_id: str, question: str, answer: str, response: AgentResponse = None):
        """保存聊天历史到数据库（包含完整信息）"""
        try:
            import json
            import time
            timestamp = int(time.time() * 1000)
            
            # 保存用户消息
            self.db.execute_sql(
                "INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, "user", question, timestamp)
            )
            
            # 保存助手消息（包含完整信息）
            images_json = json.dumps(response.images, ensure_ascii=False) if response and response.images else None
            references_json = json.dumps(response.references, ensure_ascii=False) if response and response.references else None
            
            self.db.execute_sql(
                """INSERT INTO chat_history 
                   (session_id, role, content, images, "references", sql, chart_type, timestamp) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, "assistant", answer, images_json, references_json, 
                 response.sql if response else None, 
                 response.chart_type if response else None, 
                 timestamp + 1)
            )
        except Exception as e:
            logger.warning(f"保存聊天历史失败: {e}")
            # 如果表结构不支持新字段，回退到基本保存
            try:
                self.db.execute_sql(
                    "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "user", question)
                )
                self.db.execute_sql(
                    "INSERT INTO chat_history (session_id, role, content) VALUES (?, ?, ?)",
                    (session_id, "assistant", answer)
                )
            except:
                pass

    def load_chat_history(self, session_id: str) -> List[Dict]:
        """从数据库加载聊天历史"""
        try:
            rows = self.db.execute_query(
                "SELECT role, content FROM chat_history WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,)
            )
            history = [{"role": r["role"], "content": r["content"]} for r in rows]
            # 同步到内存sessions
            if session_id not in self.sessions:
                self.sessions[session_id] = history
            else:
                self.sessions[session_id] = history
            return history
        except Exception as e:
            logger.warning(f"加载聊天历史失败: {e}")
            return []

    def _diagnose_empty_query_result(self, sql: str) -> Dict[str, Any]:
        """对空查询结果给出更具体的诊断信息。"""
        available_periods = []
        sample_companies = []
        sample_codes = []

        try:
            period_rows = self.db.execute_query(
                """
                SELECT DISTINCT report_period, report_year
                FROM income_sheet
                WHERE report_period IS NOT NULL AND report_period != ''
                ORDER BY report_year DESC, report_period DESC
                LIMIT 12
                """
            )
            available_periods = [row["report_period"] for row in period_rows]
        except Exception:
            pass

        try:
            company_rows = self.db.execute_query(
                """
                SELECT DISTINCT stock_abbr, stock_code
                FROM company_info
                WHERE stock_abbr IS NOT NULL AND stock_abbr != ''
                ORDER BY stock_abbr
                LIMIT 12
                """
            )
            sample_companies = [row["stock_abbr"] for row in company_rows if row.get("stock_abbr")]
            sample_codes = [str(row["stock_code"]) for row in company_rows if row.get("stock_code")]
        except Exception:
            try:
                fallback_rows = self.db.execute_query(
                    """
                    SELECT DISTINCT stock_abbr, stock_code
                    FROM income_sheet
                    WHERE stock_abbr IS NOT NULL AND stock_abbr != ''
                    ORDER BY stock_abbr
                    LIMIT 12
                    """
                )
                sample_companies = [row["stock_abbr"] for row in fallback_rows if row.get("stock_abbr")]
                sample_codes = [str(row["stock_code"]) for row in fallback_rows if row.get("stock_code")]
            except Exception:
                pass

        reasons: List[str] = []
        company_match = re.search(r"stock_abbr\s*=\s*'([^']+)'", sql, re.IGNORECASE)
        if company_match:
            requested_company = company_match.group(1)
            if sample_companies and requested_company not in sample_companies:
                reasons.append(f"SQL 中的公司简称 `{requested_company}` 不在当前数据库样本中。")

        code_match = re.search(r"stock_code\s*=\s*'?(\d{6})'?", sql, re.IGNORECASE)
        if code_match:
            requested_code = code_match.group(1)
            if sample_codes and requested_code not in sample_codes:
                reasons.append(f"SQL 中的股票代码 `{requested_code}` 不在当前数据库样本中。")

        requested_periods = re.findall(r"report_period\s*=\s*'([^']+)'", sql, re.IGNORECASE)
        missing_periods = [period for period in requested_periods if available_periods and period not in available_periods]
        if missing_periods:
            reasons.append(f"SQL 中的报告期 `{', '.join(missing_periods)}` 当前数据库不存在。")

        if not reasons:
            reasons.append("公司、报告期或筛选条件组合后没有匹配到记录。")

        message_lines = [
            "查询执行成功，但没有返回任何数据。",
            "",
            "可能原因：",
        ]
        message_lines.extend([f"1. {reason}" if idx == 0 else f"{idx + 1}. {reason}" for idx, reason in enumerate(reasons)])

        if sample_companies:
            message_lines.append("")
            message_lines.append(f"当前数据库中的示例公司：{', '.join(sample_companies[:8])}")
        if available_periods:
            message_lines.append(f"当前数据库中的可用报告期：{', '.join(available_periods[:8])}")
        message_lines.append("建议先检查公司简称、股票代码、报告期是否与数据库中的实际值一致。")

        return {
            "message": "\n".join(message_lines),
            "available_report_periods": available_periods,
            "sample_companies": sample_companies,
            "sample_codes": sample_codes,
        }
