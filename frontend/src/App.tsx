import React from 'react';
import { Layout, Menu, Switch, Typography, Space, Badge, Tooltip, Dropdown, Tag, Card, Divider, Modal, message } from 'antd';
import {
  MessageOutlined,
  DatabaseOutlined,
  BookOutlined,
  SettingOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RocketOutlined,
  PlusOutlined,
  DeleteOutlined,
  PictureOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  GlobalOutlined,
  GithubOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import ChatPage from './pages/ChatPage';
import DatabasePage from './pages/DatabasePage';
import KnowledgePage from './pages/KnowledgePage';
import SettingsPage from './pages/SettingsPage';
import { useAppStore, ChatMessage } from './services/store';

const { Header, Sider, Content } = Layout;
const { Text, Title, Paragraph } = Typography;

const tabTitleMap: Record<string, string> = {
  chat: '智能对话',
  database: '数据库管理',
  knowledge: '知识库管理',
  settings: '系统设置',
};

const chartStyleLabelMap: Record<string, string> = {
  default: '默认风格',
  academic: '学术风格',
  business: '商务风格',
  minimal: '极简风格',
};

const App: React.FC = () => {
  const {
    activeTab, setActiveTab,
    sidebarCollapsed, setSidebarCollapsed,
    sessions, currentSessionId,
    createSession, deleteSessionById, setCurrentSession,
    chartStyle, setChartStyle,
  } = useAppStore();

  // 页面加载时从后端加载所有会话历史
  React.  useEffect(() => {
    const loadAllSessions = async () => {
      try {
        const { listSessions, getChatHistory } = await import('./services/api');
        const sessionList = await listSessions();
        
        if (sessionList && sessionList.length > 0) {
          const loadedSessions = await Promise.all(
            sessionList.map(async (s: any) => {
              try {
                const history = await getChatHistory(s.session_id);
                const messages: ChatMessage[] = (history.messages || []).map((msg: any, idx: number) => ({
                  id: `${s.session_id}_${idx}`,
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
                
                return {
                  id: s.session_id,
                  title: messages.length > 0 
                    ? (messages.find((m: ChatMessage) => m.role === 'user')?.content || messages[0].content).substring(0, 30)
                    : '新对话',
                  messages: messages,
                  createdAt: messages.length > 0 && messages[0].timestamp 
                    ? messages[0].timestamp 
                    : Date.now() - (messages.length * 1000),
                };
              } catch (e) {
                console.error(`加载会话 ${s.session_id} 失败:`, e);
                return {
                  id: s.session_id,
                  title: '新对话',
                  messages: [],
                  createdAt: Date.now(),
                };
              }
            })
          );
          
          // 按创建时间排序（最新的在前）
          loadedSessions.sort((a, b) => b.createdAt - a.createdAt);
          
          // 更新store
          const currentState = useAppStore.getState();
          const currentId = currentState.currentSessionId;
          
          useAppStore.setState({ sessions: loadedSessions });
          
          // 如果有当前会话ID，确保它存在；否则选择第一个
          if (currentId && loadedSessions.find(s => s.id === currentId)) {
            // 当前会话存在，保持不变
          } else if (loadedSessions.length > 0) {
            // 选择第一个会话
            useAppStore.setState({ currentSessionId: loadedSessions[0].id });
          }
          
          console.log(`已从数据库加载 ${loadedSessions.length} 个会话`);
        } else {
          // 没有会话，创建一个新的
          const newSessionId = useAppStore.getState().createSession();
          console.log('创建新会话:', newSessionId);
        }
      } catch (e) {
        console.error('加载会话列表失败:', e);
        // 即使失败也创建一个新会话
        const newSessionId = useAppStore.getState().createSession();
        console.log('加载失败，创建新会话:', newSessionId);
      }
    };
    
    loadAllSessions();
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'chat': return <ChatPage />;
      case 'database': return <DatabasePage />;
      case 'knowledge': return <KnowledgePage />;
      case 'settings': return <SettingsPage />;
      case 'about': return (
        <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
          <Card title={<><RocketOutlined /> 项目介绍</>}>
            <Title level={3}>上市公司财报"智能问数"助手</Title>
            <Paragraph>
              本项目是2026年（第14届）"泰迪杯"数据挖掘挑战赛B题的完整解决方案。
              系统通过自然语言理解、SQL生成、数据查询、知识库检索和可视化分析，
              实现零技术门槛的财报数据查询与分析。
            </Paragraph>
            <Title level={4}>核心功能</Title>
            <ul>
              <li><strong>任务一</strong>：构建结构化财报数据库，从PDF财报中提取结构化数据</li>
              <li><strong>任务二</strong>：搭建智能问数助手，支持自然语言查询、多轮对话、意图澄清和可视化</li>
              <li><strong>任务三</strong>：增强系统可靠性，实现多意图规划、知识库融合和归因分析</li>
            </ul>
            <Title level={4}>技术特点</Title>
            <ul>
              <li>基于大语言模型的NL2SQL转换</li>
              <li>RAG（检索增强生成）技术融合知识库</li>
              <li>完整的归因分析和可解释性展示</li>
              <li>流式输出和实时进度反馈</li>
            </ul>
          </Card>
        </div>
      );
      case 'framework': return (
        <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
          <Card title={<><ThunderboltOutlined /> 技术框架</>}>
            <Title level={4}>后端技术栈</Title>
            <ul>
              <li><strong>FastAPI</strong>：高性能异步Web框架</li>
              <li><strong>SQLite</strong>：轻量级数据库，存储结构化财报数据</li>
              <li><strong>sentence-transformers</strong>：本地文本嵌入模型</li>
              <li><strong>pdfplumber</strong>：PDF解析和表格提取</li>
              <li><strong>matplotlib</strong>：专业图表生成</li>
              <li><strong>OpenAI API</strong>：大语言模型调用（支持硅基流动、智谱等）</li>
            </ul>
            <Title level={4}>前端技术栈</Title>
            <ul>
              <li><strong>React + TypeScript</strong>：现代化前端框架</li>
              <li><strong>Ant Design</strong>：企业级UI组件库</li>
              <li><strong>Vite</strong>：快速构建工具</li>
              <li><strong>Zustand</strong>：轻量级状态管理</li>
              <li><strong>React Markdown</strong>：Markdown渲染</li>
            </ul>
            <Title level={4}>核心算法</Title>
            <ul>
              <li><strong>意图分析</strong>：LLM驱动的意图识别和澄清</li>
              <li><strong>NL2SQL</strong>：自然语言到SQL的转换</li>
              <li><strong>语义检索</strong>：向量相似度搜索</li>
              <li><strong>多意图规划</strong>：复杂问题的任务分解</li>
              <li><strong>归因分析</strong>：结果生成链路追溯</li>
            </ul>
          </Card>
        </div>
      );
      case 'apis': return (
        <div style={{ padding: 24, maxWidth: 900, margin: '0 auto' }}>
          <Card title={<><ApiOutlined /> API资源</>}>
            <Title level={4}>大模型API服务商</Title>
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <Card size="small" hoverable>
                <Space>
                  <GlobalOutlined style={{ color: '#1677ff', fontSize: 20 }} />
                  <div>
                    <Text strong>硅基流动 (SiliconFlow)</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      提供DeepSeek、Qwen等多种模型API
                    </Text>
                    <br />
                    <a href="https://siliconflow.cn" target="_blank" rel="noopener noreferrer">
                      <LinkOutlined /> 访问官网
                    </a>
                  </div>
                </Space>
              </Card>
              <Card size="small" hoverable>
                <Space>
                  <GlobalOutlined style={{ color: '#52c41a', fontSize: 20 }} />
                  <div>
                    <Text strong>智谱AI (Zhipu AI)</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      提供GLM-4系列模型API
                    </Text>
                    <br />
                    <a href="https://open.bigmodel.cn" target="_blank" rel="noopener noreferrer">
                      <LinkOutlined /> 访问官网
                    </a>
                  </div>
                </Space>
              </Card>
              <Card size="small" hoverable>
                <Space>
                  <GlobalOutlined style={{ color: '#fa8c16', fontSize: 20 }} />
                  <div>
                    <Text strong>OpenAI</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      提供GPT系列模型API（需配置代理）
                    </Text>
                    <br />
                    <a href="https://platform.openai.com" target="_blank" rel="noopener noreferrer">
                      <LinkOutlined /> 访问官网
                    </a>
                  </div>
                </Space>
              </Card>
            </Space>
            <Divider />
            <Title level={4}>相关资源</Title>
            <ul>
              <li><a href="https://github.com" target="_blank" rel="noopener noreferrer"><GithubOutlined /> GitHub</a></li>
              <li><a href="https://huggingface.co" target="_blank" rel="noopener noreferrer">🤗 Hugging Face</a></li>
              <li><a href="https://pytorch.org" target="_blank" rel="noopener noreferrer">PyTorch</a></li>
            </ul>
          </Card>
        </div>
      );
      default: return <ChatPage />;
    }
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 左侧边栏 */}
      <Sider
        width={260}
        collapsed={sidebarCollapsed}
        collapsedWidth={60}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          overflow: 'auto',
          transition: 'all 0.2s',
        }}
      >
        {/* Logo */}
        <div style={{
          padding: sidebarCollapsed ? '16px 8px' : '18px 20px',
          borderBottom: '1px solid #f0f0f0',
          textAlign: 'center',
        }}>
          {!sidebarCollapsed ? (
            <Space direction="vertical" size={2}>
              <Title level={5} style={{ margin: 0, color: '#1677ff', fontSize: 16 }}>
                <RocketOutlined /> 智能问数助手
              </Title>
              <Text type="secondary" style={{ fontSize: 11 }}>上市公司财报分析系统</Text>
            </Space>
          ) : (
            <RocketOutlined style={{ fontSize: 22, color: '#1677ff' }} />
          )}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[activeTab]}
          onClick={({ key }) => setActiveTab(key)}
          style={{ borderRight: 0 }}
          items={[
            { key: 'chat', icon: <MessageOutlined />, label: '智能对话' },
            { key: 'database', icon: <DatabaseOutlined />, label: '数据库管理' },
            { key: 'knowledge', icon: <BookOutlined />, label: '知识库管理' },
            { type: 'divider' as any },
            { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
            { type: 'divider' as any },
            { key: 'about', icon: <RocketOutlined />, label: '项目介绍' },
            { key: 'framework', icon: <ThunderboltOutlined />, label: '技术框架' },
            { key: 'apis', icon: <ApiOutlined />, label: 'API资源' },
          ]}
        />

        {/* 会话列表 */}
        {!sidebarCollapsed && activeTab === 'chat' && (
          <div style={{ padding: '10px 12px' }}>
            <div
              onClick={createSession}
              className="new-chat-btn"
              style={{
                padding: '8px 12px', borderRadius: 8,
                border: '1px dashed #bae0ff', cursor: 'pointer',
                textAlign: 'center', marginBottom: 8, fontSize: 13,
                color: '#1677ff', background: '#f0f5ff',
                transition: 'all 0.2s',
              }}
            >
              <PlusOutlined /> 新建对话
            </div>
            <div style={{ maxHeight: 'calc(100vh - 420px)', overflow: 'auto' }}>
              {sessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => { setCurrentSession(session.id).catch(console.error); }}
                  style={{
                    padding: '8px 12px', borderRadius: 8,
                    cursor: 'pointer', marginBottom: 4, fontSize: 13,
                    display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', transition: 'all 0.15s',
                    background: currentSessionId === session.id ? '#e6f4ff' : 'transparent',
                    border: currentSessionId === session.id ? '1px solid #91caff' : '1px solid transparent',
                  }}
                >
                  <Text ellipsis style={{ flex: 1, fontSize: 13, color: currentSessionId === session.id ? '#1677ff' : '#333' }}>
                    {session.title}
                  </Text>
                  <DeleteOutlined
                    style={{ color: '#ccc', fontSize: 12, transition: 'color 0.2s' }}
                    onClick={async (e) => { 
                      e.stopPropagation(); 
                      Modal.confirm({
                        title: '确认删除',
                        content: '确定要删除这个对话吗？删除后将无法恢复。',
                        okText: '删除',
                        okType: 'danger',
                        cancelText: '取消',
                        onOk: async () => {
                          try {
                            await deleteSessionById(session.id);
                            message.success('对话已删除');
                          } catch (error) {
                            message.error('删除失败，请重试');
                          }
                        },
                      });
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.color = '#ff4d4f')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '#ccc')}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </Sider>

      <Layout>
        {/* 顶部栏 */}
        <Header style={{
          background: '#fff', padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between', height: 56,
          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
        }}>
          <Space>
            {React.createElement(
              sidebarCollapsed ? MenuUnfoldOutlined : MenuFoldOutlined,
              {
                style: { fontSize: 18, cursor: 'pointer', color: '#666' },
                onClick: () => setSidebarCollapsed(!sidebarCollapsed),
              }
            )}
            <Text strong style={{ fontSize: 16 }}>{tabTitleMap[activeTab] || ''}</Text>
          </Space>
          <Space size={16}>
            {/* 增强模式状态已在ChatPage输入框上方显示 */}
          </Space>
        </Header>

        {/* 内容区 */}
        <Content style={{ margin: 0, background: '#f8f9fc' }}>
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  );
};

export default App;
