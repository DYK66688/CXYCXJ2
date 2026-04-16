/**
 * 全局状态管理 (Zustand)
 * 支持流式步骤更新、配置管理、图表风格等
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Reference, ChatStep } from './api';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  images?: string[];
  references?: Reference[];
  reasoning_explanation?: string;  // 推理依据说明
  sql?: string;
  steps?: ChatStep[];
  needs_clarification?: boolean;
  clarification_data?: any;
  chart_type?: string;
  loading?: boolean;
  streaming?: boolean;  // 流式输出中
  query_result?: any[];  // 查询结果数据
}

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
}

interface AppState {
  // 聊天状态
  sessions: ChatSession[];
  currentSessionId: string | null;
  enhancedMode: boolean;

  // UI状态
  sidebarCollapsed: boolean;
  activeTab: string;
  theme: 'light' | 'dark';
  chartStyle: 'default' | 'academic' | 'business' | 'minimal' | 'dark' | 'colorful' | 'financial' | 'elegant';
  fontSize: 'small' | 'medium' | 'large';
  showSteps: boolean;  // 是否默认展开步骤

  // Actions
  createSession: () => string;
  deleteSessionById: (id: string) => Promise<void>;
  setCurrentSession: (id: string) => Promise<void>;
  addMessage: (message: ChatMessage) => void;
  updateLastMessage: (updates: Partial<ChatMessage>) => void;
  appendToLastMessageSteps: (step: ChatStep) => void;
  updateLastMessageStep: (stepType: string, updates: Partial<ChatStep>) => void;
  appendToLastMessageContent: (chunk: string) => void;
  setEnhancedMode: (mode: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setActiveTab: (tab: string) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  setChartStyle: (style: 'default' | 'academic' | 'business' | 'minimal' | 'dark' | 'colorful' | 'financial' | 'elegant') => void;
  setFontSize: (size: 'small' | 'medium' | 'large') => void;
  setShowSteps: (show: boolean) => void;
  getCurrentMessages: () => ChatMessage[];
}

const generateId = () => Math.random().toString(36).substring(2, 10);

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      enhancedMode: true,
      sidebarCollapsed: false,
      activeTab: 'chat',
      theme: 'light',
      chartStyle: 'default',
      fontSize: 'medium',
      showSteps: true,
      
      // 初始化时从后端加载所有会话
      _initialized: false,

      createSession: () => {
        const id = generateId();
        const session: ChatSession = {
          id,
          title: '新对话',
          messages: [],
          createdAt: Date.now(),
        };
        set((state) => ({
          sessions: [session, ...state.sessions],
          currentSessionId: id,
        }));
        return id;
      },

      deleteSessionById: async (id) => {
        // 先调用后端API删除数据库中的记录
        try {
          const { deleteSession } = await import('./api');
          await deleteSession(id);
          console.log(`✓ 已从数据库删除会话 ${id}`);
        } catch (e) {
          console.error('删除会话失败:', e);
          // 即使后端删除失败，也继续删除前端状态
        }
        
        // 更新前端状态
        set((state) => {
          const remainingSessions = state.sessions.filter((s) => s.id !== id);
          let newCurrentSessionId = state.currentSessionId;
          
          // 如果删除的是当前会话，切换到其他会话
          if (state.currentSessionId === id) {
            newCurrentSessionId = remainingSessions.length > 0 
              ? remainingSessions[0].id 
              : null;
          }
          
          return {
            sessions: remainingSessions,
            currentSessionId: newCurrentSessionId,
          };
        });
      },

      setCurrentSession: async (id) => {
    set({ currentSessionId: id });
    // 立即从数据库加载历史记录
    try {
      const { getChatHistory } = await import('./api');
      const history = await getChatHistory(id);
      
      if (history.messages && history.messages.length > 0) {
        const formattedMessages = history.messages.map((msg: any, idx: number) => ({
          id: `${id}_${idx}`,
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp || (Date.now() - (history.messages.length - idx) * 1000),
          images: msg.images || [],
          references: msg.references || [],
          sql: msg.sql || undefined,
          chart_type: msg.chart_type || undefined,
          steps: msg.steps || [],
          query_result: msg.query_result || [],
          reasoning_explanation: msg.reasoning_explanation || undefined,
        }));
        
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === id) {
              return { ...s, messages: formattedMessages };
            }
            return s;
          });
          
          // 如果会话不存在，创建一个
          if (!sessions.find(s => s.id === id)) {
            sessions.push({
              id: id,
              title: formattedMessages.find((m: ChatMessage) => m.role === 'user')?.content.substring(0, 30) || '新对话',
              messages: formattedMessages,
              createdAt: formattedMessages[0]?.timestamp || Date.now(),
            });
          }
          
          return { sessions };
        });
        
        console.log(`✓ 切换会话 ${id}，已加载 ${history.messages.length} 条历史记录`);
      } else {
        // 没有历史记录，确保会话存在
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === id) {
              return { ...s, messages: [] };
            }
            return s;
          });
          
          if (!sessions.find(s => s.id === id)) {
            sessions.push({
              id: id,
              title: '新对话',
              messages: [],
              createdAt: Date.now(),
            });
          }
          
          return { sessions };
        });
      }
    } catch (e) {
      console.error('切换会话时加载历史记录失败:', e);
    }
  },

      addMessage: (message) => {
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === state.currentSessionId) {
              const newMessages = [...s.messages, message];
              if (message.role === 'user' && s.title === '新对话') {
                return { ...s, messages: newMessages, title: message.content.substring(0, 30) };
              }
              return { ...s, messages: newMessages };
            }
            return s;
          });
          return { sessions };
        });
      },

      updateLastMessage: (updates) => {
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === state.currentSessionId && s.messages.length > 0) {
              const messages = [...s.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = { ...messages[lastIdx], ...updates };
              return { ...s, messages };
            }
            return s;
          });
          return { sessions };
        });
      },

      appendToLastMessageSteps: (step) => {
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === state.currentSessionId && s.messages.length > 0) {
              const messages = [...s.messages];
              const lastIdx = messages.length - 1;
              const existingSteps = messages[lastIdx].steps || [];
              // Update existing step of same type or add new
              const existingIdx = existingSteps.findIndex(
                (es) => es.step_type === step.step_type && es.status === 'running'
              );
              let newSteps;
              if (existingIdx >= 0) {
                newSteps = [...existingSteps];
                newSteps[existingIdx] = step;
              } else {
                newSteps = [...existingSteps, step];
              }
              messages[lastIdx] = { ...messages[lastIdx], steps: newSteps };
              return { ...s, messages };
            }
            return s;
          });
          return { sessions };
        });
      },

      updateLastMessageStep: (stepType, updates) => {
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === state.currentSessionId && s.messages.length > 0) {
              const messages = [...s.messages];
              const lastIdx = messages.length - 1;
              const steps = [...(messages[lastIdx].steps || [])];
              // Find last step of this type
              for (let i = steps.length - 1; i >= 0; i--) {
                if (steps[i].step_type === stepType) {
                  steps[i] = { ...steps[i], ...updates };
                  break;
                }
              }
              messages[lastIdx] = { ...messages[lastIdx], steps };
              return { ...s, messages };
            }
            return s;
          });
          return { sessions };
        });
      },

      appendToLastMessageContent: (chunk) => {
        set((state) => {
          const sessions = state.sessions.map((s) => {
            if (s.id === state.currentSessionId && s.messages.length > 0) {
              const messages = [...s.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                content: (messages[lastIdx].content || '') + chunk,
              };
              return { ...s, messages };
            }
            return s;
          });
          return { sessions };
        });
      },

      setEnhancedMode: (mode) => set({ enhancedMode: mode }),
      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
      setActiveTab: (tab) => set({ activeTab: tab }),
      setTheme: (theme) => set({ theme }),
      setChartStyle: (style) => set({ chartStyle: style }),
      setFontSize: (size) => set({ fontSize: size }),
      setShowSteps: (show) => set({ showSteps: show }),

      getCurrentMessages: () => {
        const state = get();
        const session = state.sessions.find((s) => s.id === state.currentSessionId);
        return session?.messages || [];
      },
    }),
    {
      name: 'smart-qa-store',
      partialize: (state) => ({
        enhancedMode: state.enhancedMode,
        theme: state.theme,
        chartStyle: state.chartStyle,
        fontSize: state.fontSize,
        showSteps: state.showSteps,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);
