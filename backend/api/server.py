"""
FastAPI后端服务器
提供前端所需的所有API接口，支持SSE流式输出
"""
import os
import sys
import json
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core.config import AppConfig, DATA_DIR, RESULTS_DIR, CONFIG_FILE
from backend.core.database import DatabaseManager
from backend.core.llm_client import LLMClient
from backend.core.embedding import EmbeddingManager
from backend.core.knowledge_base import KnowledgeBase
from backend.core.agent import SmartQAAgent
from backend.core.preflight import run_backend_preflight

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="智能问数助手 API", description="上市公司财报智能问数助手后端服务", version="1.0.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

os.makedirs(str(RESULTS_DIR), exist_ok=True)
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")

# 全局状态
config: AppConfig = None
db: DatabaseManager = None
llm: LLMClient = None
embedding: EmbeddingManager = None
kb: KnowledgeBase = None
agent: SmartQAAgent = None
startup_preflight = None


@app.on_event("startup")
async def startup():
    global config, db, llm, embedding, kb, agent, startup_preflight
    config = AppConfig.load()
    db = DatabaseManager(config.db_path)
    db.init_db()
    llm = LLMClient(config)
    embedding = EmbeddingManager(config)
    kb = KnowledgeBase(db, embedding)
    agent = SmartQAAgent(db=db, llm=llm, knowledge_base=kb, results_dir=str(RESULTS_DIR))
    startup_preflight = run_backend_preflight(config, db)
    for warning in startup_preflight.warnings:
        logger.warning("启动自检警告: %s", warning)
    for error in startup_preflight.errors:
        logger.warning("启动自检错误: %s", error)
    logger.info("后端服务初始化完成")


# =============================================================================
# 请求/响应模型
# =============================================================================
class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID")
    enhanced_mode: bool = Field(False, description="是否启用增强模式")
    chart_style: str = Field("default", description="图表风格: default/academic/business/minimal/dark/colorful/financial/elegant")


class ClarificationResponse(BaseModel):
    session_id: str
    selected_option: str = ""
    custom_input: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    llm_configs: Optional[List[Dict]] = None
    agent_llm_indices: Optional[List[int]] = None
    other_llm_indices: Optional[List[int]] = None
    embedding: Optional[Dict] = None
    rag: Optional[Dict] = None
    llm_client: Optional[Dict] = None
    embedding_model: Optional[Dict] = None
    sql_generator: Optional[Dict] = None
    chart_generator: Optional[Dict] = None
    agent: Optional[Dict] = None
    max_concurrent_requests: Optional[int] = None


class SQLQueryRequest(BaseModel):
    sql: str


class KnowledgeDocRequest(BaseModel):
    content: str
    source_type: str = "custom"
    source_title: str = ""
    source_path: str = ""


# =============================================================================
# 图表风格API
# =============================================================================
@app.get("/api/chart/styles")
async def list_chart_styles():
    """返回可用的图表风格列表"""
    from backend.core.visualizer import CHART_STYLES
    styles = []
    for key, cfg in CHART_STYLES.items():
        styles.append({
            "key": key,
            "name": cfg["name"],
            "colors": cfg["colors"][:3],
        })
    return {"styles": styles}


# =============================================================================
# SSE流式聊天API（核心改进）
# =============================================================================
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """SSE流式聊天 - 实时推送每个步骤和最终结果"""
    async def event_generator():
        try:
            session_id = request.session_id
            if not session_id or session_id not in agent.sessions:
                session_id = agent.get_or_create_session(request.session_id)

            # 定义步骤回调
            step_events = []

            async def on_step_update(step_type, status, detail="", data=None):
                event = {
                    "type": "step",
                    "step_type": step_type,
                    "status": status,
                    "detail": str(detail)[:2000] if detail else "",
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
                step_events.append(event)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # Step 1: 意图分析
            yield f"data: {json.dumps({'type':'step','step_type':'intent_analysis','status':'running','detail':'正在分析您的问题意图...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            intent = await agent.sql_gen.analyze_intent(
                request.question,
                agent.sessions.get(session_id, [])
            )

            yield f"data: {json.dumps({'type':'step','step_type':'intent_analysis','status':'completed','detail':json.dumps(intent, ensure_ascii=False)[:500],'data':intent,'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            history = agent.sessions.get(session_id, [])

            # Step 2: 意图澄清判断
            if intent.get("needs_clarification"):
                yield f"data: {json.dumps({'type':'step','step_type':'clarification','status':'running','detail':'检测到意图模糊，生成澄清选项...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                clarification = await agent.sql_gen.generate_clarification(request.question, intent)

                yield f"data: {json.dumps({'type':'step','step_type':'clarification','status':'completed','detail':json.dumps(clarification, ensure_ascii=False)[:500],'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'type':'clarification','needs_clarification':True,'clarification_data':clarification,'content':clarification.get('message','请补充更多信息'),'session_id':session_id}, ensure_ascii=False)}\n\n"

                history.append({"role": "user", "content": request.question})
                history.append({"role": "assistant", "content": clarification.get("message", "")})
                yield "data: [DONE]\n\n"
                return

            # Step 2b: 多意图规划（增强模式）
            if request.enhanced_mode:
                yield f"data: {json.dumps({'type':'step','step_type':'planning','status':'running','detail':'正在进行多意图任务规划...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                sub_tasks = await agent._plan_multi_intent(request.question, intent, history)

                yield f"data: {json.dumps({'type':'step','step_type':'planning','status':'completed','detail':f'规划出 {len(sub_tasks)} 个子任务','data':sub_tasks,'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 3: SQL生成
            yield f"data: {json.dumps({'type':'step','step_type':'sql_generation','status':'running','detail':'正在生成SQL查询语句...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            sql_result = await agent.sql_gen.generate_sql(request.question, intent, history)
            sql = sql_result.get("sql", "")

            yield f"data: {json.dumps({'type':'step','step_type':'sql_generation','status':'completed','detail':sql,'data':sql_result,'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 4: 执行查询
            query_data = []
            if sql:
                yield f"data: {json.dumps({'type':'step','step_type':'query_execution','status':'running','detail':f'正在执行: {sql[:100]}...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                success, query_data_raw = db.safe_execute_query(sql)

                if success:
                    query_data = query_data_raw
                    # 发送查询结果预览（前5行）
                    preview = query_data[:5] if len(query_data) > 5 else query_data
                    yield f"data: {json.dumps({'type':'step','step_type':'query_execution','status':'completed','detail':f'查询成功，返回 {len(query_data)} 条结果','data':{'row_count':len(query_data),'preview':preview},'timestamp':datetime.now().isoformat()}, ensure_ascii=False, default=str)}\n\n"
                else:
                    yield f"data: {json.dumps({'type':'step','step_type':'query_execution','status':'failed','detail':f'查询失败: {query_data_raw}','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 5: 知识库检索（始终进行，不仅限于增强模式）
            kb_context = ""
            if kb:
                yield f"data: {json.dumps({'type':'step','step_type':'knowledge_search','status':'running','detail':'正在检索知识库...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                # 使用配置中的RAG参数
                rag_config = config.rag if config else None
                top_k = rag_config.top_k if rag_config else 15
                min_score = rag_config.min_score if rag_config else 0.2
                max_context = rag_config.max_kb_context_chunks if rag_config else 8
                
                kb_results = kb.search(request.question, top_k=top_k, min_score=min_score)
                if kb_results:
                    # 构建知识库上下文（用于回答生成，使用配置的最大上下文块数）
                    kb_context = "\n\n---\n\n".join([
                        f"来源: {r.get('source_title', r.get('source_path', '未知'))}\n内容: {r['content']}"
                        for r in kb_results[:max_context]
                    ])
                    # 展示所有检索到的结果用于归因分析（使用配置的最大结果数）
                    max_attr = rag_config.max_attribution_results if rag_config else 15
                    kb_preview = [{"title": r.get("source_title",""), "score": round(r["score"],3), "snippet": r["content"][:200]} for r in kb_results[:max_attr]]

                    yield f"data: {json.dumps({'type':'step','step_type':'knowledge_search','status':'completed','detail':f'找到 {len(kb_results)} 条相关知识','data':kb_preview,'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json.dumps({'type':'step','step_type':'knowledge_search','status':'completed','detail':'未找到相关知识库内容','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 6: 图表生成
            images = []
            chart_type = ""
            if intent.get("needs_chart") and query_data:
                yield f"data: {json.dumps({'type':'step','step_type':'visualization','status':'running','detail':'正在生成可视化图表...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                chart_path = await agent.chart_gen.auto_generate_chart(
                    question=request.question,
                    sql_result=query_data,
                    intent=intent,
                    save_dir=str(RESULTS_DIR),
                    file_prefix=f"chart_{datetime.now().strftime('%H%M%S')}",
                    style=request.chart_style or "default",
                )
                if chart_path:
                    images.append(chart_path.replace("\\", "/"))
                    chart_type = intent.get("chart_type", "")

                yield f"data: {json.dumps({'type':'step','step_type':'visualization','status':'completed','detail':chart_path or '未生成图表','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 7: 生成回答（流式）- 同时使用SQL结果和知识库内容
            yield f"data: {json.dumps({'type':'step','step_type':'answer_generation','status':'running','detail':'正在生成分析回答（结合SQL查询结果和知识库内容）...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            answer = await agent.sql_gen.generate_answer(
                request.question, sql, query_data, intent, kb_context=kb_context
            )

            # 流式输出回答文本（模拟逐段输出）
            chunks = _split_answer_to_chunks(answer)
            accumulated = ""
            for chunk in chunks:
                accumulated += chunk
                yield f"data: {json.dumps({'type':'content_chunk','content':chunk,'accumulated':accumulated}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.03)

            yield f"data: {json.dumps({'type':'step','step_type':'answer_generation','status':'completed','detail':f'回答生成完成，共 {len(answer)} 字','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # Step 8: 归因分析（增强模式）- 增强版
            references = []
            reasoning_explanation = ""
            if request.enhanced_mode and kb:
                yield f"data: {json.dumps({'type':'step','step_type':'attribution_analysis','status':'running','detail':'正在进行归因分析，追溯证据来源和推理依据...','timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

                attr_result = await agent._attribution_analysis(request.question, answer)
                references = attr_result.get("references", [])
                reasoning_explanation = attr_result.get("reasoning_explanation", "")

                # 展示更多归因信息
                yield f"data: {json.dumps({'type':'step','step_type':'attribution_analysis','status':'completed','detail':f'找到 {len(references)} 条参考来源，包含完整推理依据','data':[{'path':r.get('paper_path',''),'title':r.get('source_title',''),'score':r.get('score',0),'snippet':r.get('text','')[:200]} for r in references[:10]],'timestamp':datetime.now().isoformat()}, ensure_ascii=False)}\n\n"

            # 最终完整结果
            yield f"data: {json.dumps({'type':'result','content':answer,'images':images,'references':references,'reasoning_explanation':reasoning_explanation,'sql':sql,'query_result':query_data[:20] if query_data else [],'chart_type':chart_type,'session_id':session_id,'needs_clarification':False}, ensure_ascii=False, default=str)}\n\n"

            # 记录历史到内存
            history.append({"role": "user", "content": request.question})
            history.append({"role": "assistant", "content": answer})
            
            # 保存到数据库（包含完整信息）
            try:
                import json as json_lib
                import time
                timestamp = int(time.time() * 1000)
                
                # 保存用户消息
                db.execute_sql(
                    "INSERT INTO chat_history (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                    (session_id, "user", request.question, timestamp)
                )
                
                # 保存助手消息（包含完整信息）
                images_json = json_lib.dumps(images, ensure_ascii=False) if images else None
                references_json = json_lib.dumps(references, ensure_ascii=False) if references else None
                
                db.execute_sql(
                    """INSERT INTO chat_history 
                       (session_id, role, content, images, "references", sql, chart_type, timestamp) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, "assistant", answer, images_json, references_json, sql, chart_type, timestamp + 1)
                )
                logger.info(f"已保存会话 {session_id} 的历史记录到数据库")
            except Exception as save_error:
                logger.warning(f"保存历史记录到数据库失败: {save_error}")

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"SSE处理失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'type':'error','detail':str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


def _split_answer_to_chunks(text: str, chunk_size: int = 15) -> List[str]:
    """将回答文本分割为小块用于流式输出"""
    chunks = []
    i = 0
    while i < len(text):
        # 在换行符处分割以保持格式
        end = min(i + chunk_size, len(text))
        nl = text.find('\n', i, end + 10)
        if nl != -1 and nl < end + 10:
            end = nl + 1
        chunks.append(text[i:end])
        i = end
    return chunks


# =============================================================================
# 普通聊天API（兼容旧版）
# =============================================================================
@app.post("/api/chat")
async def chat(request: ChatRequest):
    """非流式聊天"""
    try:
        response = await agent.process_question(
            question=request.question,
            session_id=request.session_id,
            enhanced_mode=request.enhanced_mode,
        )
        session_id = request.session_id or (list(agent.sessions.keys())[-1] if agent.sessions else "")
        return {
            "content": response.content,
            "images": [img.replace("\\", "/") for img in response.images],
            "references": response.references,
            "sql": response.sql,
            "steps": [s.to_dict() for s in response.steps],
            "needs_clarification": response.needs_clarification,
            "clarification_data": response.clarification_data,
            "session_id": session_id,
            "chart_type": response.chart_type,
            "query_result": response.query_result[:20] if response.query_result else [],
        }
    except Exception as e:
        logger.error(f"聊天处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/clarify")
async def handle_clarification(request: ClarificationResponse):
    """处理用户的澄清回复"""
    combined_input = request.custom_input or request.selected_option
    response = await agent.process_question(
        question=combined_input,
        session_id=request.session_id,
        enhanced_mode=True,
    )
    return {
        "content": response.content,
        "images": [img.replace("\\", "/") for img in response.images],
        "references": response.references,
        "sql": response.sql,
        "steps": [s.to_dict() for s in response.steps],
        "session_id": request.session_id,
        "query_result": response.query_result[:20] if response.query_result else [],
    }


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取会话历史（从数据库加载，包含完整消息信息）"""
    try:
        # 从数据库加载历史，包含所有字段
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content, timestamp, images, "references", sql, chart_type
                FROM chat_history 
                WHERE session_id = ? 
                ORDER BY timestamp ASC, created_at ASC
            """, (session_id,))
            rows = cursor.fetchall()
            
            messages = []
            for row in rows:
                msg = {
                    "role": row[0],
                    "content": row[1],
                    "timestamp": row[2] if isinstance(row[2], (int, float)) else None,
                }
                # 解析JSON字段
                if row[3]:  # images
                    try:
                        import json
                        msg["images"] = json.loads(row[3]) if isinstance(row[3], str) else row[3]
                    except Exception as e:
                        logger.debug(f"解析images失败: {e}")
                        msg["images"] = []
                else:
                    msg["images"] = []
                    
                if row[4]:  # references
                    try:
                        import json
                        msg["references"] = json.loads(row[4]) if isinstance(row[4], str) else row[4]
                    except Exception as e:
                        logger.debug(f"解析references失败: {e}")
                        msg["references"] = []
                else:
                    msg["references"] = []
                    
                if row[5]:  # sql
                    msg["sql"] = row[5]
                else:
                    msg["sql"] = None
                    
                if row[6]:  # chart_type
                    msg["chart_type"] = row[6]
                else:
                    msg["chart_type"] = None
                    
                messages.append(msg)
            
            # 同步到内存sessions
            agent.sessions[session_id] = [{"role": m["role"], "content": m["content"]} for m in messages]
            
            return {"session_id": session_id, "messages": messages}
    except Exception as e:
        logger.warning(f"加载会话历史失败: {e}")
        # 回退到agent的方法
        history = agent.load_chat_history(session_id)
        return {"session_id": session_id, "messages": history}


@app.get("/api/chat/sessions")
async def list_sessions():
    """从数据库加载所有会话列表"""
    sessions = []
    try:
        # 从数据库查询所有会话
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id 
                FROM chat_history 
                GROUP BY session_id
                ORDER BY MAX(timestamp) DESC
            """)
            session_ids = [row[0] for row in cursor.fetchall()]
            
            for sid in session_ids:
                # 获取该会话的消息数量
                cursor.execute("""
                    SELECT COUNT(*) FROM chat_history WHERE session_id = ?
                """, (sid,))
                msg_count = cursor.fetchone()[0]
                
                # 获取最后一条消息
                cursor.execute("""
                    SELECT content FROM chat_history 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC LIMIT 1
                """, (sid,))
                last_msg_row = cursor.fetchone()
                last_message = last_msg_row[0][:50] if last_msg_row else ""
                
                sessions.append({
                    "session_id": sid,
                    "message_count": msg_count,
                    "last_message": last_message,
                })
    except Exception as e:
        logger.warning(f"从数据库加载会话列表失败: {e}")
        # 回退到内存中的会话
        for sid, msgs in agent.sessions.items():
            sessions.append({
                "session_id": sid,
                "message_count": len(msgs),
                "last_message": msgs[-1]["content"][:50] if msgs else "",
            })
    return {"sessions": sessions}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话及其所有历史记录"""
    try:
        # 删除内存中的会话
        if session_id in agent.sessions:
            del agent.sessions[session_id]
        
        # 删除数据库中的历史记录
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
            deleted_count = cursor.rowcount
            logger.info(f"已删除会话 {session_id} 的 {deleted_count} 条历史记录")
        
        return {"status": "ok", "deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"删除会话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败: {str(e)}")


# =============================================================================
# 数据库API
# =============================================================================
@app.get("/api/database/schema")
async def get_schema():
    return {"schema": db.get_database_schema()}


@app.get("/api/database/tables")
async def get_tables():
    tables = db.get_table_names()
    result = []
    for t in tables:
        result.append({"name": t, "row_count": db.get_table_row_count(t), "columns": db.get_table_info(t)})
    return {"tables": result}


@app.post("/api/database/query")
async def execute_query(request: SQLQueryRequest):
    success, result = db.safe_execute_query(request.sql)
    if success:
        return {"success": True, "data": result, "row_count": len(result)}
    return {"success": False, "error": result}


@app.get("/api/database/stats")
async def get_db_stats():
    stats = {}
    for table in ["company_info", "core_performance_indicators_sheet", "balance_sheet", "income_sheet", "cash_flow_sheet"]:
        try:
            stats[table] = db.get_table_row_count(table)
        except Exception:
            stats[table] = 0
    return {"stats": stats}


# =============================================================================
# 知识库API
# =============================================================================
@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    return kb.get_stats()


@app.get("/api/knowledge/documents")
async def list_knowledge_documents():
    return {"documents": kb.get_all_documents()}


@app.post("/api/knowledge/search")
async def search_knowledge(query: str, top_k: int = 15):
    """搜索知识库（提高检索多样性）"""
    return {"results": kb.search(query, top_k=top_k, min_score=0.2)}


@app.post("/api/knowledge/add")
async def add_knowledge_document(request: KnowledgeDocRequest):
    count = kb.add_document(content=request.content, source_type=request.source_type, source_path=request.source_path, source_title=request.source_title)
    return {"status": "ok", "chunks_added": count}


@app.delete("/api/knowledge/documents/{source_path:path}")
async def delete_knowledge_document(source_path: str):
    kb.delete_document(source_path)
    return {"status": "ok"}


@app.post("/api/knowledge/upload")
async def upload_knowledge_file(file: UploadFile = File(...)):
    """上传知识库文件（支持进度反馈）"""
    async def progress_generator():
        try:
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'reading', 'message': '正在读取文件...', 'progress': 10}, ensure_ascii=False)}\n\n"
            
            content = await file.read()
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'parsing', 'message': '正在解析文件内容...', 'progress': 30}, ensure_ascii=False)}\n\n"
            
            text = content.decode("utf-8", errors="ignore")
            if file.filename and file.filename.endswith(".pdf"):
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                from backend.core.pdf_parser import extract_text_from_pdf
                text = extract_text_from_pdf(tmp_path)
                os.unlink(tmp_path)
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'chunking', 'message': '正在分块处理...', 'progress': 50}, ensure_ascii=False)}\n\n"
            
            # 使用配置中的RAG参数
            rag_config = config.rag if config else None
            chunk_size = rag_config.chunk_size if rag_config else 500
            chunk_overlap = rag_config.chunk_overlap if rag_config else 100
            
            yield f"data: {json.dumps({'type': 'progress', 'stage': 'embedding', 'message': '正在生成向量嵌入...', 'progress': 70}, ensure_ascii=False)}\n\n"
            
            count = kb.add_document(
                content=text, 
                source_type="uploaded", 
                source_path=file.filename or "", 
                source_title=file.filename or "",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            yield f"data: {json.dumps({'type': 'complete', 'status': 'ok', 'filename': file.filename, 'chunks_added': count, 'progress': 100}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"上传知识库文件失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        progress_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


# =============================================================================
# 配置API（新增：支持前端修改配置）
# =============================================================================
@app.get("/api/config")
async def get_config():
    """获取完整配置"""
    return {
        "llm_configs": [
            {
                "name": c.name, "description": c.description, "model": c.model,
                "enabled": c.enabled, "base_url": c.base_url,
                "temperature": c.temperature, "top_p": c.top_p,
                "max_tokens": c.max_tokens, "weight": c.weight,
                "api_key_set": bool(c.api_key),
            }
            for c in config.llm_configs
        ],
        "agent_llm_indices": config.agent_llm_indices,
        "other_llm_indices": config.other_llm_indices,
        "embedding": {
            "use_local": config.embedding.use_local,
            "local_model_path": config.embedding.local_model_path,
            "dimension": config.embedding.dimension,
            "device": config.embedding.device,
            "api_base_url": config.embedding.api_base_url,
            "api_key": config.embedding.api_key if config.embedding.api_key else "",
            "api_model": config.embedding.api_model,
        },
        "rag": {
            "chunk_size": config.rag.chunk_size,
            "chunk_overlap": config.rag.chunk_overlap,
            "top_k": config.rag.top_k,
            "min_score": config.rag.min_score,
            "max_kb_context_chunks": config.rag.max_kb_context_chunks,
            "max_attribution_results": config.rag.max_attribution_results,
            "additional_search_top_k": config.rag.additional_search_top_k,
            "additional_search_score_ratio": config.rag.additional_search_score_ratio,
        },
        "llm_client": {
            "max_retries": config.llm_client.max_retries,
            "retry_delay_base": config.llm_client.retry_delay_base,
            "timeout": config.llm_client.timeout,
            "json_mode_temperature": config.llm_client.json_mode_temperature,
        },
        "embedding_model": {
            "batch_size": config.embedding_model.batch_size,
        },
        "sql_generator": {
            "max_sql_length": config.sql_generator.max_sql_length,
            "enable_fuzzy_match": config.sql_generator.enable_fuzzy_match,
            "fuzzy_match_threshold": config.sql_generator.fuzzy_match_threshold,
        },
        "chart_generator": {
            "default_figsize_width": config.chart_generator.default_figsize_width,
            "default_figsize_height": config.chart_generator.default_figsize_height,
            "dpi": config.chart_generator.dpi,
            "max_data_points": config.chart_generator.max_data_points,
        },
        "agent": {
            "max_history_turns": config.agent.max_history_turns,
            "enable_multi_intent_planning": config.agent.enable_multi_intent_planning,
            "enable_intent_clarification": config.agent.enable_intent_clarification,
            "clarification_confidence_threshold": config.agent.clarification_confidence_threshold,
            "max_sub_tasks": config.agent.max_sub_tasks,
        },
        "max_concurrent_requests": config.max_concurrent_requests,
        "db_path": config.db_path,
        "log_level": config.log_level,
    }


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """更新配置"""
    global config, llm
    if request.llm_configs is not None:
        from backend.core.config import LLMConfig
        new_configs = []
        for c in request.llm_configs:
            existing = next((ec for ec in config.llm_configs if ec.name == c.get("name")), None)
            api_key = c.get("api_key", existing.api_key if existing else "")
            new_configs.append(LLMConfig(
                name=c.get("name", ""), description=c.get("description", ""),
                base_url=c.get("base_url", ""), api_key=api_key,
                model=c.get("model", ""), temperature=c.get("temperature", 0.7),
                top_p=c.get("top_p", 0.9), max_tokens=c.get("max_tokens", 4096),
                weight=c.get("weight", 1.0), enabled=c.get("enabled", True),
            ))
        config.llm_configs = new_configs
    if request.agent_llm_indices is not None:
        config.agent_llm_indices = request.agent_llm_indices
    if request.other_llm_indices is not None:
        config.other_llm_indices = request.other_llm_indices
    if request.max_concurrent_requests is not None:
        config.max_concurrent_requests = request.max_concurrent_requests
    if request.embedding is not None:
        for k, v in request.embedding.items():
            if hasattr(config.embedding, k):
                setattr(config.embedding, k, v)
    
    if request.rag is not None:
        from backend.core.config import RAGConfig
        for k, v in request.rag.items():
            if hasattr(config.rag, k):
                setattr(config.rag, k, v)
    
    if request.llm_client is not None:
        from backend.core.config import LLMClientConfig
        for k, v in request.llm_client.items():
            if hasattr(config.llm_client, k):
                setattr(config.llm_client, k, v)
    
    if request.embedding_model is not None:
        from backend.core.config import EmbeddingModelConfig
        for k, v in request.embedding_model.items():
            if hasattr(config.embedding_model, k):
                setattr(config.embedding_model, k, v)
    
    if request.sql_generator is not None:
        from backend.core.config import SQLGeneratorConfig
        for k, v in request.sql_generator.items():
            if hasattr(config.sql_generator, k):
                setattr(config.sql_generator, k, v)
    
    if request.chart_generator is not None:
        from backend.core.config import ChartGeneratorConfig
        for k, v in request.chart_generator.items():
            if hasattr(config.chart_generator, k):
                setattr(config.chart_generator, k, v)
    
    if request.agent is not None:
        from backend.core.config import AgentConfig
        for k, v in request.agent.items():
            if hasattr(config.agent, k):
                setattr(config.agent, k, v)

    config.save()
    llm = LLMClient(config)
    agent.llm = llm
    agent.sql_gen.llm = llm
    agent.chart_gen.llm = llm
    # 更新agent的RAG配置
    agent._rag_config = config.rag
    return {"status": "ok", "message": "配置已更新并重新加载"}


@app.post("/api/config/add-llm")
async def add_llm_config(data: Dict[str, Any]):
    """添加新的LLM配置"""
    from backend.core.config import LLMConfig
    new_llm = LLMConfig(**data)
    config.llm_configs.append(new_llm)
    config.save()
    return {"status": "ok", "message": f"已添加 LLM 配置: {new_llm.name}"}


@app.post("/api/config/test-llm")
async def test_llm(data: Dict[str, Any]):
    """测试LLM连接（简化版，避免401错误）"""
    try:
        from openai import AsyncOpenAI
        api_key = data.get("api_key", "").strip()
        base_url = data.get("base_url", "").strip()
        model = data.get("model", "").strip()
        
        # 如果前端传的api_key为空，尝试从配置中读取
        if not api_key and config and config.llm_configs:
            # 尝试从配置中找到匹配的LLM配置
            llm_idx = data.get("llm_index", -1)
            if llm_idx >= 0 and llm_idx < len(config.llm_configs):
                llm_config = config.llm_configs[llm_idx]
                api_key = llm_config.api_key or ""
                if not base_url:
                    base_url = llm_config.base_url or ""
                if not model:
                    model = llm_config.model or ""
        
        if not api_key or not base_url or not model:
            return {"status": "error", "message": "API Key、Base URL和模型名称不能为空，请先配置"}
        
        client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        # 使用最简单的测试请求
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "test"}],
            max_tokens=5,
        )
        return {"status": "ok", "response": "连接成功"}
    except Exception as e:
        error_msg = str(e)
        # 简化错误信息
        if "401" in error_msg or "Invalid" in error_msg or "token" in error_msg.lower():
            return {"status": "error", "message": "API Key无效，请检查配置"}
        return {"status": "error", "message": f"连接失败: {error_msg[:100]}"}


@app.post("/api/config/test-embedding")
async def test_embedding(data: Dict[str, Any]):
    """测试嵌入模型连接"""
    try:
        use_local = data.get("use_local", True)
        if use_local:
            # 测试本地模型
            local_path = data.get("local_model_path", "")
            if not local_path:
                return {"status": "error", "message": "本地模型路径不能为空"}
            # 简单检查路径是否存在
            from pathlib import Path
            if not Path(local_path).exists():
                return {"status": "error", "message": f"模型路径不存在: {local_path}"}
            return {"status": "ok", "message": "本地模型路径验证成功"}
        else:
            # 测试云端模型
            api_key = data.get("api_key", "").strip()
            api_base_url = data.get("api_base_url", "").strip()
            api_model = data.get("api_model", "").strip()
            
            if not api_key or not api_base_url:
                return {"status": "error", "message": "API Key和Base URL不能为空"}
            
            # 使用OpenAI兼容API测试
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key, base_url=api_base_url)
            # 简单的embedding测试
            response = await client.embeddings.create(
                model=api_model or "text-embedding-ada-002",
                input=["test"],
            )
            return {"status": "ok", "message": "云端模型连接成功"}
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Invalid" in error_msg or "token" in error_msg.lower():
            return {"status": "error", "message": "API Key无效，请检查配置"}
        return {"status": "error", "message": f"连接失败: {error_msg[:100]}"}


# =============================================================================
# 系统信息
# =============================================================================
@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "db_path": config.db_path,
        "llm_count": len(config.get_enabled_llms()),
        "db_tables": {t: db.get_table_row_count(t) for t in db.get_table_names()},
        "warnings": startup_preflight.warnings if startup_preflight else [],
        "errors": startup_preflight.errors if startup_preflight else [],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
