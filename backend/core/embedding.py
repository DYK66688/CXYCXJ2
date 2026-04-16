"""
嵌入模型模块
支持本地模型（sentence-transformers）和API嵌入
"""
import logging
import numpy as np
from typing import List, Optional, Union
from pathlib import Path

from .config import AppConfig, EmbeddingConfig

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """嵌入向量管理器"""

    def __init__(self, config: AppConfig):
        self.config = config.embedding
        self.model = None
        self.dimension = self.config.dimension
        self._initialized = False

    def initialize(self):
        """延迟初始化嵌入模型"""
        if self._initialized:
            return

        if self.config.use_local:
            self._init_local_model()
        else:
            self._init_api_model()
        self._initialized = True

    def _init_local_model(self):
        """初始化本地sentence-transformers模型"""
        try:
            from sentence_transformers import SentenceTransformer
            model_path = self.config.local_model_path
            if not Path(model_path).exists():
                logger.warning(f"本地模型不存在: {model_path}，将在首次使用时下载")
                model_path = "BAAI/bge-small-zh-v1.5"

            self.model = SentenceTransformer(
                model_path,
                device=self.config.device,
            )
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"本地嵌入模型加载成功: {model_path}, 维度: {self.dimension}")
        except ImportError:
            logger.error("请安装 sentence-transformers: pip install sentence-transformers")
            raise

    def _init_api_model(self):
        """初始化API嵌入模型（硅基流动等）"""
        if not self.config.api_base_url or not self.config.api_key:
            raise ValueError("API嵌入模型需要配置api_base_url和api_key")
        logger.info(f"使用API嵌入模型: {self.config.api_base_url}")

    def encode(self, texts: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        将文本编码为向量
        Args:
            texts: 单个文本或文本列表
            normalize: 是否L2归一化
        Returns:
            numpy数组，shape=(n, dimension)
        """
        self.initialize()

        if isinstance(texts, str):
            texts = [texts]

        if self.config.use_local and self.model is not None:
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=normalize,
                show_progress_bar=False,
            )
            return np.array(embeddings)
        else:
            # 使用API嵌入模型
            return self._encode_via_api(texts, normalize)

    def _encode_via_api(self, texts: List[str], normalize: bool = True) -> np.ndarray:
        """通过API获取嵌入向量（同步版本）"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base_url,
            )
            
            # 批量处理
            embeddings = []
            batch_size = 10
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                response = client.embeddings.create(
                    model=self.config.api_model or "BAAI/bge-large-zh-v1.5",
                    input=batch,
                )
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            
            embeddings = np.array(embeddings)
            if normalize:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / (norms + 1e-8)
            
            self.dimension = embeddings.shape[1]
            logger.info(f"API嵌入成功，维度: {self.dimension}")
            return embeddings
        except Exception as e:
            logger.error(f"API嵌入失败: {e}")
            # 如果API失败，尝试回退到本地模型
            if not self.config.use_local:
                logger.warning("API嵌入失败，尝试使用本地模型")
                self.config.use_local = True
                self._init_local_model()
                return self.model.encode(texts, normalize_embeddings=normalize, show_progress_bar=False)
            raise

    def compute_similarity(self, query_vec: np.ndarray, doc_vecs: np.ndarray) -> np.ndarray:
        """计算余弦相似度"""
        if query_vec.ndim == 1:
            query_vec = query_vec.reshape(1, -1)
        # 归一化
        query_norm = query_vec / (np.linalg.norm(query_vec, axis=1, keepdims=True) + 1e-8)
        doc_norm = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-8)
        return (query_norm @ doc_norm.T).flatten()

    def search(
        self,
        query: str,
        documents: List[str],
        top_k: int = 5,
    ) -> List[tuple]:
        """
        语义搜索
        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前K个结果
        Returns:
            [(index, score, text), ...]
        """
        if not documents:
            return []

        query_vec = self.encode(query)
        doc_vecs = self.encode(documents)
        scores = self.compute_similarity(query_vec, doc_vecs)

        # 排序
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = [
            (int(idx), float(scores[idx]), documents[idx])
            for idx in top_indices
        ]
        return results
