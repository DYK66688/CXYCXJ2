"""
全局配置模块
支持多LLM API配置、嵌入模型配置、数据库路径等
所有路径统一由 project_root 派生，config.json 中的路径可以使用相对路径
"""
import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path

# ──────── 项目根目录（代码自动检测） ────────
# 这是通过代码位置自动推断的根目录，作为回退值
_AUTO_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# 尝试从 config.json 中读取用户指定的 project_root
_config_file_path = _AUTO_PROJECT_ROOT / "config.json"
_USER_PROJECT_ROOT = None
if _config_file_path.exists():
    try:
        with open(_config_file_path, "r", encoding="utf-8") as _f:
            _raw = json.load(_f)
        if "project_root" in _raw and _raw["project_root"]:
            _candidate_root = Path(_raw["project_root"]).expanduser().resolve()
            if _candidate_root.exists():
                _USER_PROJECT_ROOT = _candidate_root
    except Exception:
        pass

# 最终使用的项目根目录：优先 config.json 中用户配置的值
PROJECT_ROOT = _USER_PROJECT_ROOT if _USER_PROJECT_ROOT else _AUTO_PROJECT_ROOT

# ──────── 由 PROJECT_ROOT 派生的常用目录 ────────
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
LOGS_DIR = PROJECT_ROOT / "logs"
MODELS_DIR = PROJECT_ROOT / "models"
# 配置文件始终保存在仓库根目录，不能依赖可变的 project_root
CONFIG_FILE = _config_file_path

def _detect_sample_data_dir(root: Path) -> Path:
    """自动定位默认示例数据目录。"""
    if root.exists():
        for d in os.listdir(root):
            if d.startswith('\u793a'):
                return root / d
    return root / "示例数据"


SAMPLE_DATA_DIR = _detect_sample_data_dir(PROJECT_ROOT)

# 数据库路径
DB_PATH = DATA_DIR / "financial.db"
KNOWLEDGE_DB_PATH = DATA_DIR / "knowledge.db"

# 向量数据库路径
VECTOR_DB_DIR = DATA_DIR / "vector_store"


def _resolve_path(path_str: str, root: Path) -> str:
    """
    将路径字符串解析为绝对路径。
    - 如果 path_str 是绝对路径，直接返回
    - 如果是相对路径，则相对于 root 解析
    """
    p = Path(path_str)
    if p.is_absolute():
        return str(p)
    return str((root / p).resolve())


@dataclass
class LLMConfig:
    """单个LLM API配置"""
    name: str = "default"
    description: str = ""
    base_url: str = "https://api.siliconflow.cn/v1/"
    api_key: str = ""
    model: str = "Pro/deepseek-ai/DeepSeek-V3"
    temperature: float = 0.7
    top_p: float = 0.9
    max_tokens: int = 4096
    weight: float = 1.0
    enabled: bool = True


@dataclass
class EmbeddingConfig:
    """嵌入模型配置"""
    use_local: bool = True  # 默认使用本地模型
    local_model_path: str = str(MODELS_DIR / "bge-small-zh-v1.5")
    dimension: int = 512
    device: str = "cpu"
    # API嵌入配置（默认使用硅基流动bge模型）
    api_base_url: str = "https://api.siliconflow.cn/v1/"
    api_key: str = "your_api_key"
    api_model: str = "BAAI/bge-large-zh-v1.5"  # 硅基流动的bge模型


@dataclass
class RAGConfig:
    """RAG检索配置"""
    chunk_size: int = 500  # 文本分块大小
    chunk_overlap: int = 100  # 分块重叠大小
    top_k: int = 15  # 检索返回的top_k数量
    min_score: float = 0.2  # 最小相似度阈值
    max_kb_context_chunks: int = 8  # 用于回答生成的最大知识库块数
    max_attribution_results: int = 15  # 归因分析最大结果数
    additional_search_top_k: int = 5  # 额外搜索的top_k数量（用于关键词/公司名搜索）
    additional_search_score_ratio: float = 0.75  # 额外搜索的相似度阈值比例（相对于min_score）


@dataclass
class LLMClientConfig:
    """LLM客户端调用配置"""
    max_retries: int = 3  # 最大重试次数
    retry_delay_base: float = 2.0  # 重试延迟基数（秒），指数退避
    timeout: int = 60  # 请求超时时间（秒）
    json_mode_temperature: float = 0.3  # JSON模式下的温度（更低的温度提高准确性）


@dataclass
class EmbeddingModelConfig:
    """嵌入模型处理配置"""
    batch_size: int = 10  # 批处理大小


@dataclass
class SQLGeneratorConfig:
    """SQL生成器配置"""
    max_sql_length: int = 2000  # 最大SQL长度
    enable_fuzzy_match: bool = True  # 启用模糊匹配
    fuzzy_match_threshold: float = 0.7  # 模糊匹配阈值


@dataclass
class ChartGeneratorConfig:
    """图表生成器配置"""
    default_figsize_width: float = 10.0  # 默认图表宽度（英寸）
    default_figsize_height: float = 6.0  # 默认图表高度（英寸）
    dpi: int = 100  # 图表分辨率
    max_data_points: int = 50  # 最大数据点数（超过则采样）


@dataclass
class AgentConfig:
    """Agent配置"""
    max_history_turns: int = 10  # 最大历史轮次（用于上下文）
    enable_multi_intent_planning: bool = True  # 启用多意图规划
    enable_intent_clarification: bool = True  # 启用意图澄清
    clarification_confidence_threshold: float = 0.6  # 澄清置信度阈值
    max_sub_tasks: int = 5  # 最大子任务数


@dataclass
class AppConfig:
    """应用全局配置"""
    # LLM配置列表
    llm_configs: List[LLMConfig] = field(default_factory=list)
    # 主Agent使用的LLM索引
    agent_llm_indices: List[int] = field(default_factory=lambda: [0])
    # 其他任务使用的LLM索引
    other_llm_indices: List[int] = field(default_factory=lambda: [0])
    # 嵌入模型配置（API/本地模型选择）
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    # RAG配置
    rag: RAGConfig = field(default_factory=RAGConfig)
    # LLM客户端调用配置
    llm_client: LLMClientConfig = field(default_factory=LLMClientConfig)
    # 嵌入模型处理配置（批处理等）
    embedding_model: EmbeddingModelConfig = field(default_factory=EmbeddingModelConfig)
    # SQL生成器配置
    sql_generator: SQLGeneratorConfig = field(default_factory=SQLGeneratorConfig)
    # 图表生成器配置
    chart_generator: ChartGeneratorConfig = field(default_factory=ChartGeneratorConfig)
    # Agent配置
    agent: AgentConfig = field(default_factory=AgentConfig)
    # 并发控制
    max_concurrent_requests: int = 50
    # 当前任务脚本读取的数据目录
    sample_data_path: str = str(SAMPLE_DATA_DIR)
    # 数据库路径
    db_path: str = str(DB_PATH)
    knowledge_db_path: str = str(KNOWLEDGE_DB_PATH)
    vector_db_dir: str = str(VECTOR_DB_DIR)
    # 日志级别
    log_level: str = "INFO"

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AppConfig":
        """从JSON文件加载配置"""
        path = Path(config_path).resolve() if config_path else CONFIG_FILE
        if not path.exists():
            # 返回默认配置
            config = cls()
            config.llm_configs = [
                LLMConfig(
                    name="硅基流动-DeepSeek-V3",
                    description="硅基流动DeepSeek-V3模型",
                    base_url="https://api.siliconflow.cn/v1/",
                    api_key="your_api_key",
                    model="Pro/deepseek-ai/DeepSeek-V3",
                ),
                LLMConfig(
                    name="智谱-GLM-4-Flash",
                    description="智谱官方免费版模型API",
                    base_url="https://open.bigmodel.cn/api/paas/v4/",
                    api_key="your_api_key",
                    model="glm-4-flash",
                    enabled=False,
                ),
            ]
            config.save(path)
            return config

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        config = cls()

        # ── 确定项目根目录 ──
        # 优先使用 config.json 中用户指定的 project_root，
        # 否则使用代码位置自动推断的根目录
        if "project_root" in data and data["project_root"]:
            configured_root = Path(data["project_root"]).expanduser().resolve()
            root = configured_root if configured_root.exists() else _AUTO_PROJECT_ROOT
        else:
            root = _AUTO_PROJECT_ROOT
        default_sample_data_dir = _detect_sample_data_dir(root)

        # 解析LLM配置
        if "llm_configs" in data:
            config.llm_configs = [LLMConfig(**c) for c in data["llm_configs"]]
        if "agent_llm_indices" in data:
            config.agent_llm_indices = data["agent_llm_indices"]
        if "other_llm_indices" in data:
            config.other_llm_indices = data["other_llm_indices"]
        if "embedding" in data:
            emb_data = dict(data["embedding"])
            # 解析嵌入模型的本地路径（支持相对路径）
            if "local_model_path" in emb_data:
                emb_data["local_model_path"] = _resolve_path(emb_data["local_model_path"], root)
            config.embedding = EmbeddingConfig(**emb_data)
        if "rag" in data:
            config.rag = RAGConfig(**data["rag"])
        if "llm_client" in data:
            config.llm_client = LLMClientConfig(**data["llm_client"])
        if "embedding_model" in data:
            config.embedding_model = EmbeddingModelConfig(**data["embedding_model"])
        if "sql_generator" in data:
            config.sql_generator = SQLGeneratorConfig(**data["sql_generator"])
        if "chart_generator" in data:
            config.chart_generator = ChartGeneratorConfig(**data["chart_generator"])
        if "agent" in data:
            config.agent = AgentConfig(**data["agent"])
        if "max_concurrent_requests" in data:
            config.max_concurrent_requests = data["max_concurrent_requests"]
        if "sample_data_path" in data:
            config.sample_data_path = _resolve_path(data["sample_data_path"], root)
        else:
            config.sample_data_path = str(default_sample_data_dir)

        # 解析数据库路径（支持相对路径）
        if "db_path" in data:
            config.db_path = _resolve_path(data["db_path"], root)
        if "knowledge_db_path" in data:
            config.knowledge_db_path = _resolve_path(data["knowledge_db_path"], root)

        if "log_level" in data:
            config.log_level = data["log_level"]
        return config

    def save(self, path: Optional[Path] = None):
        """保存配置到JSON文件"""
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "project_root": str(PROJECT_ROOT),
            "llm_configs": [
                {
                    "name": c.name, "description": c.description,
                    "base_url": c.base_url, "api_key": c.api_key,
                    "model": c.model, "temperature": c.temperature,
                    "top_p": c.top_p, "max_tokens": c.max_tokens,
                    "weight": c.weight, "enabled": c.enabled,
                }
                for c in self.llm_configs
            ],
            "agent_llm_indices": self.agent_llm_indices,
            "other_llm_indices": self.other_llm_indices,
            "embedding": {
                "use_local": self.embedding.use_local,
                "local_model_path": self.embedding.local_model_path,
                "dimension": self.embedding.dimension,
                "device": self.embedding.device,
                "api_base_url": self.embedding.api_base_url,
                "api_key": self.embedding.api_key,
                "api_model": self.embedding.api_model,
            },
            "rag": {
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
                "top_k": self.rag.top_k,
                "min_score": self.rag.min_score,
                "max_kb_context_chunks": self.rag.max_kb_context_chunks,
                "max_attribution_results": self.rag.max_attribution_results,
                "additional_search_top_k": self.rag.additional_search_top_k,
                "additional_search_score_ratio": self.rag.additional_search_score_ratio,
            },
            "llm_client": {
                "max_retries": self.llm_client.max_retries,
                "retry_delay_base": self.llm_client.retry_delay_base,
                "timeout": self.llm_client.timeout,
                "json_mode_temperature": self.llm_client.json_mode_temperature,
            },
            "embedding_model": {
                "batch_size": self.embedding_model.batch_size,
            },
            "sql_generator": {
                "max_sql_length": self.sql_generator.max_sql_length,
                "enable_fuzzy_match": self.sql_generator.enable_fuzzy_match,
                "fuzzy_match_threshold": self.sql_generator.fuzzy_match_threshold,
            },
            "chart_generator": {
                "default_figsize_width": self.chart_generator.default_figsize_width,
                "default_figsize_height": self.chart_generator.default_figsize_height,
                "dpi": self.chart_generator.dpi,
                "max_data_points": self.chart_generator.max_data_points,
            },
            "agent": {
                "max_history_turns": self.agent.max_history_turns,
                "enable_multi_intent_planning": self.agent.enable_multi_intent_planning,
                "enable_intent_clarification": self.agent.enable_intent_clarification,
                "clarification_confidence_threshold": self.agent.clarification_confidence_threshold,
                "max_sub_tasks": self.agent.max_sub_tasks,
            },
            "max_concurrent_requests": self.max_concurrent_requests,
            "sample_data_path": self.sample_data_path,
            "db_path": self.db_path,
            "knowledge_db_path": self.knowledge_db_path,
            "log_level": self.log_level,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_sample_data_dir(self) -> Path:
        """返回当前任务脚本使用的数据目录。"""
        return Path(self.sample_data_path).expanduser().resolve()

    def get_agent_llm(self) -> LLMConfig:
        """获取Agent使用的主LLM配置"""
        for idx in self.agent_llm_indices:
            if idx < len(self.llm_configs) and self.llm_configs[idx].enabled:
                return self.llm_configs[idx]
        # 回退到第一个启用的
        for c in self.llm_configs:
            if c.enabled:
                return c
        raise ValueError("没有可用的LLM配置")

    def get_enabled_llms(self) -> List[LLMConfig]:
        """获取所有启用的LLM配置"""
        return [c for c in self.llm_configs if c.enabled]
