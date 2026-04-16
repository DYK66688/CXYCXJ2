/**
 * API服务层 - 与后端FastAPI通信，支持SSE流式输出
 */
import axios from 'axios';

// Use relative URL in production (proxy handles it in dev)
const API_BASE = import.meta.env.DEV ? '' : 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
});

const BACKEND_UNAVAILABLE_HINT = '无法连接后端，请确认已启动 `python -m backend.api.server`，并检查 http://localhost:8000/docs 是否可访问。';

const toFriendlyErrorMessage = (error: any): string => {
  const responseMessage = error?.response?.data?.detail || error?.response?.data?.message;
  if (responseMessage) {
    return String(responseMessage);
  }

  const message = String(error?.message || '');
  if (
    message.includes('Network Error') ||
    message.includes('Failed to fetch') ||
    message.includes('ECONNREFUSED')
  ) {
    return BACKEND_UNAVAILABLE_HINT;
  }
  if (message.toLowerCase().includes('timeout')) {
    return '请求超时，可能是模型响应较慢或后端未正常返回结果。';
  }
  return message || '请求失败，请检查后端日志。';
};

api.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(new Error(toFriendlyErrorMessage(error)))
);

// ==================== 类型定义 ====================
export interface ChatRequest {
  question: string;
  session_id?: string;
  enhanced_mode?: boolean;
  chart_style?: string;
}

export interface ChatStep {
  step_type: string;
  status: string;
  detail?: string;
  data?: any;
  timestamp?: string;
}

export interface Reference {
  paper_path: string;
  text: string;
  paper_image?: string;
  source_title?: string;
  score?: number;
}

export interface ChatResponse {
  content: string;
  images: string[];
  references: Reference[];
  sql: string;
  steps: ChatStep[];
  needs_clarification: boolean;
  clarification_data: {
    message?: string;
    options?: { label: string; value: string }[];
  };
  session_id: string;
  chart_type: string;
  query_result?: any[];
}

export type SSEEventHandler = {
  onStep?: (step: ChatStep) => void;
  onContentChunk?: (chunk: string, accumulated: string) => void;
  onClarification?: (data: any) => void;
  onResult?: (result: any) => void;
  onError?: (error: string) => void;
  onDone?: () => void;
};

// ==================== SSE流式聊天（核心） ====================
export const sendChatStream = (req: ChatRequest, handlers: SSEEventHandler): AbortController => {
  const controller = new AbortController();

  fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
    signal: controller.signal,
  }).then(async (response) => {
    if (!response.ok) {
      handlers.onError?.(`HTTP ${response.status}: ${response.statusText}`);
      handlers.onDone?.();
      return;
    }
    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data === '[DONE]') {
            handlers.onDone?.();
            return;
          }
          try {
            const parsed = JSON.parse(data);
            switch (parsed.type) {
              case 'step':
                handlers.onStep?.(parsed);
                break;
              case 'content_chunk':
                handlers.onContentChunk?.(parsed.content, parsed.accumulated);
                break;
              case 'clarification':
                handlers.onClarification?.(parsed);
                break;
              case 'result':
                handlers.onResult?.(parsed);
                break;
              case 'error':
                handlers.onError?.(parsed.detail);
                break;
            }
          } catch (e) {
            // Skip malformed JSON
          }
        }
      }
    }
    handlers.onDone?.();
  }).catch((error) => {
    if (error.name !== 'AbortError') {
      handlers.onError?.(toFriendlyErrorMessage(error));
      handlers.onDone?.();
    }
  });

  return controller;
};

// ==================== 普通聊天（兼容） ====================
export const sendChat = async (req: ChatRequest): Promise<ChatResponse> => {
  const res = await api.post('/chat', req);
  return res.data;
};

export const sendClarification = async (data: {
  session_id: string;
  selected_option: string;
  custom_input?: string;
}): Promise<ChatResponse> => {
  const res = await api.post('/chat/clarify', data);
  return res.data;
};

export const getChatHistory = async (sessionId: string) => {
  const res = await api.get(`/chat/history/${sessionId}`);
  return res.data;
};

export const listSessions = async () => {
  const res = await api.get('/chat/sessions');
  return res.data.sessions;
};

export const deleteSession = async (sessionId: string) => {
  await api.delete(`/chat/sessions/${sessionId}`);
};

// ==================== 数据库 ====================
export const getDatabaseSchema = async () => {
  const res = await api.get('/database/schema');
  return res.data.schema;
};

export const getDatabaseTables = async () => {
  const res = await api.get('/database/tables');
  return res.data.tables;
};

export const executeQuery = async (sql: string) => {
  const res = await api.post('/database/query', { sql });
  return res.data;
};

export const getDatabaseStats = async () => {
  const res = await api.get('/database/stats');
  return res.data.stats;
};

// ==================== 知识库 ====================
export const getKnowledgeStats = async () => {
  const res = await api.get('/knowledge/stats');
  return res.data;
};

export const listKnowledgeDocs = async () => {
  const res = await api.get('/knowledge/documents');
  return res.data.documents;
};

export const searchKnowledge = async (query: string, topK = 5) => {
  const res = await api.post(`/knowledge/search?query=${encodeURIComponent(query)}&top_k=${topK}`);
  return res.data.results;
};

export const addKnowledgeDoc = async (data: {
  content: string;
  source_type?: string;
  source_title?: string;
}) => {
  const res = await api.post('/knowledge/add', data);
  return res.data;
};

export const deleteKnowledgeDoc = async (sourcePath: string) => {
  await api.delete(`/knowledge/documents/${encodeURIComponent(sourcePath)}`);
};

export const uploadKnowledgeFile = async (
  file: File,
  onProgress?: (progress: { stage: string; message: string; progress: number }) => void
) => {
  const formData = new FormData();
  formData.append('file', file);
  
  // 使用fetch支持SSE进度
  const response = await fetch(`${API_BASE}/knowledge/upload`, {
    method: 'POST',
    body: formData,
    headers: {
      // 不设置Content-Type，让浏览器自动设置multipart/form-data边界
    },
  });

  if (!response.ok) {
    throw new Error('上传失败');
  }

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  if (reader) {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'progress' && onProgress) {
              onProgress(data);
            } else if (data.type === 'complete') {
              return { status: 'ok', filename: data.filename, chunks_added: data.chunks_added };
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  }

  throw new Error('上传未完成');
};

// ==================== 配置 ====================
export const getConfig = async () => {
  const res = await api.get('/config');
  return res.data;
};

export const updateConfig = async (data: any) => {
  const res = await api.put('/config', data);
  return res.data;
};

export const testLLMConnection = async (data: { api_key: string; base_url: string; model: string; llm_index?: number }) => {
  const res = await api.post('/config/test-llm', data);
  return res.data;
};

export const testEmbeddingConnection = async (data: {
  use_local: boolean;
  api_base_url?: string;
  api_key?: string;
  api_model?: string;
  local_model_path?: string;
}) => {
  const res = await api.post('/config/test-embedding', data);
  return res.data;
};

export const healthCheck = async () => {
  const res = await api.get('/health');
  return res.data;
};

export default api;
