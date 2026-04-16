"""
知识库模块
管理研报数据等非结构化知识，支持向量检索
"""
import os
import json
import logging
import pickle
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from .database import DatabaseManager
from .embedding import EmbeddingManager

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """知识库管理器"""

    def __init__(self, db: DatabaseManager, embedding: EmbeddingManager):
        self.db = db
        self.embedding = embedding
        self._vectors_cache = None
        self._chunks_cache = None

    def add_document(
        self,
        content: str,
        source_type: str,
        source_path: str,
        source_title: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        metadata: Dict = None,
    ) -> int:
        """
        添加文档到知识库
        Args:
            content: 文档全文
            source_type: 来源类型(research_report, financial_report, etc.)
            source_path: 文件路径
            source_title: 文档标题
            chunk_size: 分块大小
            chunk_overlap: 分块重叠
            metadata: 额外元数据
        Returns:
            添加的块数量
        """
        # 分块
        chunks = self._split_text(content, chunk_size, chunk_overlap)
        
        if not chunks:
            return 0

        # 生成嵌入向量
        self.embedding.initialize()
        embeddings = self.embedding.encode(chunks)

        # 存入数据库
        records = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            records.append({
                "source_type": source_type,
                "source_path": source_path,
                "source_title": source_title,
                "chunk_index": i,
                "content": chunk,
                "metadata": json.dumps(metadata or {}, ensure_ascii=False),
                "embedding": pickle.dumps(emb),
            })

        self.db.insert_many("knowledge_chunks", records, replace=False)
        self._invalidate_cache()
        
        logger.info(f"添加文档到知识库: {source_title}, {len(chunks)} 个块")
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type: Optional[str] = None,
        min_score: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        语义检索知识库
        Args:
            query: 查询文本
            top_k: 返回前K个结果
            source_type: 限定来源类型
            min_score: 最小相似度阈值
        Returns:
            [{content, source_path, source_title, score, metadata}, ...]
        """
        self.embedding.initialize()
        query_vec = self.embedding.encode(query)

        # 从数据库加载所有块和向量
        self._load_cache(source_type)
        
        if not self._chunks_cache:
            return []

        # 计算相似度
        scores = self.embedding.compute_similarity(query_vec, self._vectors_cache)
        
        # 排序并过滤
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            chunk = self._chunks_cache[idx]
            results.append({
                "content": chunk["content"],
                "source_path": chunk["source_path"],
                "source_title": chunk["source_title"],
                "source_type": chunk["source_type"],
                "score": score,
                "metadata": json.loads(chunk.get("metadata", "{}") or "{}"),
            })
        
        return results

    def add_research_report(
        self,
        title: str,
        report_type: str,
        file_path: str,
        content: str,
        stock_name: str = "",
        stock_code: str = "",
        org_name: str = "",
        org_sname: str = "",
        publish_date: str = "",
        industry_name: str = "",
        rating_name: str = "",
        researcher: str = "",
    ):
        """添加研报到知识库"""
        # 存入研报信息表
        record = {
            "title": title,
            "report_type": report_type,
            "stock_name": stock_name,
            "stock_code": stock_code,
            "org_name": org_name,
            "org_sname": org_sname,
            "publish_date": publish_date,
            "industry_name": industry_name,
            "rating_name": rating_name,
            "researcher": researcher,
            "file_path": file_path,
            "content": content[:10000],  # 限制存储内容长度
        }
        self.db.insert_record("research_reports", record)

        # 同时加入向量知识库
        metadata = {
            "report_type": report_type,
            "stock_name": stock_name,
            "stock_code": stock_code,
            "org_sname": org_sname,
            "publish_date": publish_date,
            "industry_name": industry_name,
        }
        self.add_document(
            content=content,
            source_type=f"research_{report_type}",
            source_path=file_path,
            source_title=title,
            chunk_size=500,
            chunk_overlap=100,
            metadata=metadata,
        )

    def get_all_documents(self) -> List[Dict]:
        """获取所有知识库文档列表"""
        sql = """
        SELECT source_type, source_path, source_title, 
               COUNT(*) as chunk_count,
               MIN(created_at) as created_at
        FROM knowledge_chunks 
        GROUP BY source_path
        ORDER BY created_at DESC
        """
        return self.db.execute_query(sql)

    def delete_document(self, source_path: str):
        """删除指定文档"""
        self.db.execute_sql(
            "DELETE FROM knowledge_chunks WHERE source_path = ?",
            (source_path,)
        )
        self._invalidate_cache()
        logger.info(f"已删除知识库文档: {source_path}")

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        total_chunks = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM knowledge_chunks"
        )[0]["cnt"]
        total_docs = self.db.execute_query(
            "SELECT COUNT(DISTINCT source_path) as cnt FROM knowledge_chunks"
        )[0]["cnt"]
        total_reports = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM research_reports"
        )[0]["cnt"]
        
        type_stats = self.db.execute_query(
            "SELECT source_type, COUNT(*) as cnt FROM knowledge_chunks GROUP BY source_type"
        )
        
        return {
            "total_chunks": total_chunks,
            "total_documents": total_docs,
            "total_research_reports": total_reports,
            "by_type": {r["source_type"]: r["cnt"] for r in type_stats},
        }

    def _split_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """智能文本分块"""
        if not text:
            return []

        # 按段落分割
        paragraphs = text.split("\n")
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk += para + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # 如果单个段落超过chunk_size，强制分割
                if len(para) > chunk_size:
                    for i in range(0, len(para), chunk_size - overlap):
                        chunks.append(para[i:i+chunk_size])
                    current_chunk = ""
                else:
                    # 保留重叠部分
                    if current_chunk and overlap > 0:
                        current_chunk = current_chunk[-overlap:] + para + "\n"
                    else:
                        current_chunk = para + "\n"

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _load_cache(self, source_type: Optional[str] = None):
        """加载向量缓存"""
        if self._chunks_cache is not None:
            return

        if source_type:
            rows = self.db.execute_query(
                "SELECT * FROM knowledge_chunks WHERE source_type = ?",
                (source_type,)
            )
        else:
            rows = self.db.execute_query("SELECT * FROM knowledge_chunks")

        self._chunks_cache = []
        vectors = []
        
        for row in rows:
            self._chunks_cache.append(dict(row))
            if row["embedding"]:
                vec = pickle.loads(row["embedding"])
                vectors.append(vec)
            else:
                vectors.append(np.zeros(self.embedding.dimension))

        if vectors:
            self._vectors_cache = np.array(vectors)
        else:
            self._vectors_cache = np.array([]).reshape(0, self.embedding.dimension)

    def _invalidate_cache(self):
        """清除缓存"""
        self._chunks_cache = None
        self._vectors_cache = None
