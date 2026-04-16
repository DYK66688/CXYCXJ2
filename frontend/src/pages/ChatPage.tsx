import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  Input, Button, Space, Card, Typography, Tag, Image, Collapse, Table,
  Spin, Modal, Radio, Divider, Empty, message, Tooltip, Timeline, Badge, Drawer,
  Switch, Alert,
} from 'antd';
import {
  SendOutlined, RobotOutlined, UserOutlined,
  CodeOutlined, BarChartOutlined, SearchOutlined,
  CheckCircleOutlined, LoadingOutlined, ExclamationCircleOutlined,
  FileTextOutlined, BulbOutlined, LinkOutlined, DatabaseOutlined,
  CopyOutlined, ExpandOutlined, CloseCircleOutlined, EditOutlined,
  NodeIndexOutlined, ThunderboltOutlined, MessageOutlined,
} from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { sendChatStream, sendClarification, ChatStep } from '../services/api';
import { useAppStore, ChatMessage } from '../services/store';

const { Text, Paragraph, Title } = Typography;
const { TextArea } = Input;

// 步骤类型配置
const stepConfig: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  intent_analysis: { label: '意图分析', icon: <BulbOutlined />, color: '#722ed1' },
  clarification: { label: '意图澄清', icon: <ExclamationCircleOutlined />, color: '#faad14' },
  planning: { label: '任务规划', icon: <NodeIndexOutlined />, color: '#13c2c2' },
  sql_generation: { label: 'SQL生成', icon: <CodeOutlined />, color: '#1677ff' },
  query_execution: { label: '数据查询', icon: <DatabaseOutlined />, color: '#52c41a' },
  query_diagnosis: { label: '结果诊断', icon: <ExclamationCircleOutlined />, color: '#fa8c16' },
  knowledge_search: { label: '知识检索', icon: <SearchOutlined />, color: '#eb2f96' },
  visualization: { label: '图表生成', icon: <BarChartOutlined />, color: '#fa8c16' },
  answer_generation: { label: '回答生成', icon: <EditOutlined />, color: '#1677ff' },
  attribution_analysis: { label: '归因分析', icon: <LinkOutlined />, color: '#2f54eb' },
  merge_results: { label: '结果整合', icon: <CheckCircleOutlined />, color: '#52c41a' },
};

const ChatPage: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [clarificationVisible, setClarificationVisible] = useState(false);
  const [clarificationData, setClarificationData] = useState<any>(null);
  const [selectedOption, setSelectedOption] = useState('');
  const [customInput, setCustomInput] = useState('');
  const [clarificationMode, setClarificationMode] = useState<'select' | 'input'>('select');
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [attributionDrawer, setAttributionDrawer] = useState(false);
  const [activeAttribution, setActiveAttribution] = useState<any[]>([]);
  const [activeAttributionMsgId, setActiveAttributionMsgId] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    currentSessionId, createSession,
    addMessage, updateLastMessage, appendToLastMessageSteps,
    appendToLastMessageContent,
    getCurrentMessages, enhancedMode, chartStyle, showSteps, setEnhancedMode,
  } = useAppStore();

  const messages = getCurrentMessages();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 页面加载或切换会话时，从数据库加载历史记录
  useEffect(() => {
    const loadHistory = async () => {
      if (!currentSessionId) return;
      
      try {
        const { getChatHistory } = await import('../services/api');
        const history = await getChatHistory(currentSessionId);
        
        if (history.messages && history.messages.length > 0) {
          // 确保消息格式完整
          const formattedMessages = history.messages.map((msg: any, idx: number) => ({
            id: `${currentSessionId}_${idx}`,
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
          
          // 检查当前消息是否需要更新
          const currentMessages = getCurrentMessages();
          const needsUpdate = 
            currentMessages.length !== formattedMessages.length ||
            currentMessages.some((m, idx) => {
              const fm = formattedMessages[idx];
              return !fm || m.role !== fm.role || m.content !== fm.content;
            });
          
          if (needsUpdate) {
            // 更新store中的会话消息
            useAppStore.setState((state) => {
              const sessions = state.sessions.map((s) => {
                if (s.id === currentSessionId) {
                  return { ...s, messages: formattedMessages };
                }
                return s;
              });
              
              // 如果会话不存在，创建一个
              if (!sessions.find(s => s.id === currentSessionId)) {
                sessions.push({
                  id: currentSessionId,
                      title: formattedMessages.find((m: ChatMessage) => m.role === 'user')?.content.substring(0, 30) || '新对话',
                  messages: formattedMessages,
                  createdAt: formattedMessages[0]?.timestamp || Date.now(),
                });
              }
              
              return { sessions };
            });
            
            console.log(`✓ 已从数据库加载会话 ${currentSessionId} 的历史记录: ${history.messages.length} 条消息`);
          }
        } else {
          // 没有历史记录，确保会话存在但消息为空
          useAppStore.setState((state) => {
            const sessions = state.sessions.map((s) => {
              if (s.id === currentSessionId) {
                return { ...s, messages: [] };
              }
              return s;
            });
            
            if (!sessions.find(s => s.id === currentSessionId)) {
              sessions.push({
                id: currentSessionId,
                title: '新对话',
                messages: [],
                createdAt: Date.now(),
              });
            }
            
            return { sessions };
          });
        }
      } catch (e) {
        console.error('加载历史记录失败:', e);
      }
    };
    
    loadHistory();
  }, [currentSessionId, getCurrentMessages]);

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || loading) return;

    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = createSession();
    }

    // 确保当前会话ID与发送请求的会话ID一致，防止切换会话时的消息混乱
    const currentSessionIdRef = sessionId;
    
    const userMsg: ChatMessage = {
      id: `${currentSessionIdRef}_${Date.now()}`,
      role: 'user',
      content: inputValue.trim(),
      timestamp: Date.now(),
    };
    addMessage(userMsg);

    const question = inputValue.trim();
    setInputValue('');
    setLoading(true);

    // 添加空的AI消息用于流式填充，使用会话ID确保消息归属正确
    const aiMsgId = `${currentSessionIdRef}_${Date.now() + 1}`;
    addMessage({
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      loading: true,
      streaming: true,
      steps: [],
    });

    // SSE流式请求
    const controller = sendChatStream(
      { question, session_id: currentSessionIdRef, enhanced_mode: enhancedMode, chart_style: chartStyle },
      {
        onStep: (step: ChatStep) => {
          // 检查当前会话ID是否仍然匹配，防止切换会话时的更新混乱
          if (currentSessionId === currentSessionIdRef) {
            appendToLastMessageSteps(step);
          }
          // 不再自动展开步骤结果
        },
        onContentChunk: (_chunk: string, accumulated: string) => {
          // 检查当前会话ID是否仍然匹配
          if (currentSessionId === currentSessionIdRef) {
            updateLastMessage({ content: accumulated, loading: false });
          }
        },
        onClarification: (data: any) => {
          // 检查当前会话ID是否仍然匹配
          if (currentSessionId === currentSessionIdRef) {
            setClarificationData({ ...data.clarification_data, session_id: currentSessionIdRef, message: data.content });
            setClarificationVisible(true);
            updateLastMessage({
              content: data.content,
              loading: false,
              streaming: false,
              needs_clarification: true,
              clarification_data: data.clarification_data,
            });
          }
        },
        onResult: (result: any) => {
          // 检查当前会话ID是否仍然匹配
          if (currentSessionId === currentSessionIdRef) {
            updateLastMessage({
              content: result.content,
              images: result.images,
              references: result.references,
              reasoning_explanation: result.reasoning_explanation,
              sql: result.sql,
              chart_type: result.chart_type,
              query_result: result.query_result,
              loading: false,
              streaming: false,
            });
          }
        },
        onError: (error: string) => {
          // 检查当前会话ID是否仍然匹配
          if (currentSessionId === currentSessionIdRef) {
            updateLastMessage({
              content: `请求失败: ${error}`,
              loading: false,
              streaming: false,
            });
            message.error('请求失败，请检查后端服务');
          }
        },
        onDone: () => {
          // 检查当前会话ID是否仍然匹配
          if (currentSessionId === currentSessionIdRef) {
            setLoading(false);
            updateLastMessage({ loading: false, streaming: false });
          }
        },
      }
    );

    abortControllerRef.current = controller;
  }, [inputValue, loading, currentSessionId, enhancedMode, chartStyle, addMessage, updateLastMessage, appendToLastMessageSteps]);

  const handleStop = () => {
    abortControllerRef.current?.abort();
    setLoading(false);
    updateLastMessage({ loading: false, streaming: false });
  };

  const handleClarify = async () => {
    if (!selectedOption && !customInput) return;
    setClarificationVisible(false);

    const input = clarificationMode === 'input' ? customInput : selectedOption;
    setLoading(true);

    const aiMsgId = (Date.now() + 1).toString();
    // Add user's clarification as a message
    addMessage({
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: Date.now(),
    });
    addMessage({
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      loading: true,
      streaming: true,
      steps: [],
    });

    try {
      const response = await sendClarification({
        session_id: clarificationData?.session_id,
        selected_option: clarificationMode === 'select' ? selectedOption : '',
        custom_input: clarificationMode === 'input' ? customInput : undefined,
      });

      updateLastMessage({
        content: response.content,
        images: response.images,
        references: response.references,
        sql: response.sql,
        steps: response.steps,
        query_result: response.query_result,
        loading: false,
        streaming: false,
      });
    } catch (error: any) {
      updateLastMessage({
        content: `处理失败: ${error.message}`,
        loading: false,
        streaming: false,
      });
    }
    setLoading(false);
    setSelectedOption('');
    setCustomInput('');
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    message.success('已复制到剪贴板');
  };

  // ================= 步骤渲染 =================
  const renderStepTimeline = (steps: ChatStep[]) => {
    if (!steps || steps.length === 0) return null;

    return (
      <div className="steps-timeline" style={{ marginBottom: 12 }}>
        <div style={{
          background: 'linear-gradient(135deg, #f8f9ff 0%, #f0f5ff 100%)',
          borderRadius: 12,
          padding: '16px 20px',
          border: '1px solid #e6edff',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
            <ThunderboltOutlined style={{ color: '#1677ff', marginRight: 8 }} />
            <Text strong style={{ fontSize: 14 }}>处理步骤</Text>
            <Badge count={steps.length} style={{ backgroundColor: '#1677ff', marginLeft: 8 }} />
          </div>
          <Timeline
            items={steps.map((step, idx) => {
              const cfg = stepConfig[step.step_type] || { label: step.step_type, icon: <CheckCircleOutlined />, color: '#999' };
              const isRunning = step.status === 'running';
              const isFailed = step.status === 'failed';
              const isCompleted = step.status === 'completed';
              // 不自动展开，需要手动点击
              const isExpanded = expandedSteps.has(`${idx}`);

              return {
                color: isFailed ? 'red' : isRunning ? 'blue' : isCompleted ? 'green' : 'gray',
                dot: isRunning ? (
                  <LoadingOutlined style={{ fontSize: 14, color: cfg.color }} className="step-running" />
                ) : isFailed ? (
                  <CloseCircleOutlined style={{ fontSize: 14, color: '#ff4d4f' }} />
                ) : (
                  <span style={{ color: isCompleted ? cfg.color : '#ccc' }}>{cfg.icon}</span>
                ),
                children: (
                  <div
                    style={{ cursor: 'pointer', padding: '2px 0' }}
                    onClick={() => {
                      const next = new Set(expandedSteps);
                      if (isExpanded) next.delete(`${idx}`);
                      else next.add(`${idx}`);
                      setExpandedSteps(next);
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <Text strong style={{ fontSize: 13, color: isRunning ? cfg.color : undefined }}>
                        {cfg.label}
                      </Text>
                      {isRunning && (
                        <Tag color="processing" style={{ fontSize: 11, margin: 0 }}>进行中</Tag>
                      )}
                      {isCompleted && step.detail && !isExpanded && (
                        <Text type="secondary" style={{ fontSize: 12, flex: 1 }} ellipsis>
                          {step.detail.substring(0, 60)}{step.detail.length > 60 ? '...' : ''}
                        </Text>
                      )}
                    </div>
                    {/* 展开的详细信息 */}
                    {isExpanded && step.detail && (
                      <div className="step-detail-enter" style={{
                        marginTop: 8, padding: '10px 12px',
                        background: '#fff', borderRadius: 8,
                        border: '1px solid #f0f0f0', fontSize: 12,
                      }}>
                        {step.step_type === 'sql_generation' ? (
                          <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                              <Text type="secondary" style={{ fontSize: 11 }}>SQL查询语句</Text>
                              <CopyOutlined
                                style={{ cursor: 'pointer', color: '#1677ff' }}
                                onClick={(e) => { e.stopPropagation(); copyToClipboard(step.detail || ''); }}
                              />
                            </div>
                            <pre style={{
                              background: '#1a1a2e', color: '#e0e0e0',
                              padding: 12, borderRadius: 6,
                              fontSize: 12, overflow: 'auto', margin: 0,
                              fontFamily: "'Fira Code', 'Consolas', monospace",
                            }}>
                              {step.detail}
                            </pre>
                          </div>
                        ) : step.step_type === 'query_execution' && step.data?.preview ? (
                          <div>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              查询结果（共 {step.data.row_count} 条，显示前 {Math.min(5, step.data.preview?.length || 0)} 条）
                            </Text>
                            <div style={{ marginTop: 8, overflow: 'auto', maxHeight: 300 }}>
                              {step.data.preview && step.data.preview.length > 0 && (
                                <Table
                                  dataSource={step.data.preview.map((r: any, i: number) => ({ ...r, _key: i }))}
                                  columns={Object.keys(step.data.preview[0] || {}).map((col) => ({
                                    title: col, dataIndex: col, key: col, ellipsis: true,
                                    width: 150,
                                  }))}
                                  rowKey="_key"
                                  pagination={false}
                                  size="small"
                                  scroll={{ x: true }}
                                  bordered
                                />
                              )}
                            </div>
                          </div>
                        ) : step.step_type === 'intent_analysis' && step.data ? (
                          <div>
                            <Text type="secondary" style={{ fontSize: 11 }}>识别的意图</Text>
                            <div style={{ marginTop: 4 }}>
                              {Object.entries(step.data).map(([k, v]) => (
                                <Tag key={k} style={{ marginBottom: 4 }}>
                                  {k}: {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                                </Tag>
                              ))}
                            </div>
                          </div>
                        ) : step.step_type === 'knowledge_search' && step.data ? (
                          <div>
                            <Text type="secondary" style={{ fontSize: 11 }}>检索到的知识片段</Text>
                            {(step.data as any[]).map((item: any, i: number) => (
                              <div key={i} style={{
                                padding: '6px 8px', background: '#fafafa',
                                borderRadius: 4, marginTop: 6, borderLeft: '3px solid #eb2f96',
                              }}>
                                <Text style={{ fontSize: 11 }}>{item.snippet || item.title}</Text>
                                {item.score && (
                                  <Tag color="pink" style={{ marginLeft: 4, fontSize: 10 }}>
                                    相似度: {item.score}
                                  </Tag>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : step.step_type === 'planning' && step.data ? (
                          <div>
                            <Text type="secondary" style={{ fontSize: 11 }}>子任务规划</Text>
                            {(step.data as any[]).map((task: any, i: number) => (
                              <div key={i} style={{
                                padding: '6px 8px', background: '#fafafa',
                                borderRadius: 4, marginTop: 6, borderLeft: '3px solid #13c2c2',
                              }}>
                                <Text style={{ fontSize: 12 }}>
                                  <Badge count={i + 1} size="small" style={{ backgroundColor: '#13c2c2', marginRight: 6 }} />
                                  {task.question}
                                </Text>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <Text style={{ fontSize: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                            {step.detail}
                          </Text>
                        )}
                      </div>
                    )}
                  </div>
                ),
              };
            })}
          />
        </div>
      </div>
    );
  };

  // ================= 消息渲染 =================
  const renderMessage = (msg: ChatMessage, idx: number) => {
    if (msg.role === 'user') {
      return (
        <div className="message-enter" style={{
          display: 'flex', justifyContent: 'flex-end', marginBottom: 20, padding: '0 16px',
        }}>
          <div style={{
            maxWidth: '70%', background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
            color: '#fff', padding: '12px 18px', borderRadius: '18px 18px 4px 18px',
            fontSize: 14, lineHeight: 1.7, boxShadow: '0 2px 8px rgba(22,119,255,0.15)',
          }}>
            {msg.content}
          </div>
          <div style={{
            width: 38, height: 38, borderRadius: '50%',
            background: 'linear-gradient(135deg, #1677ff, #4096ff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginLeft: 10, flexShrink: 0, boxShadow: '0 2px 6px rgba(22,119,255,0.2)',
          }}>
            <UserOutlined style={{ color: '#fff', fontSize: 16 }} />
          </div>
        </div>
      );
    }

    return (
      <div className="message-enter" style={{
        display: 'flex', marginBottom: 20, padding: '0 16px', alignItems: 'flex-start',
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: '50%',
          background: 'linear-gradient(135deg, #f0f5ff, #e6f4ff)',
          border: '1.5px solid #bae0ff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginRight: 10, flexShrink: 0, boxShadow: '0 2px 6px rgba(22,119,255,0.08)',
        }}>
          <RobotOutlined style={{ color: '#1677ff', fontSize: 17 }} />
        </div>
        <div style={{ flex: 1, minWidth: 0, maxWidth: 'calc(100% - 56px)' }}>
          {/* 加载状态 */}
          {msg.loading && (!msg.steps || msg.steps.length === 0) && (
            <div className="typing-indicator" style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '12px 16px', background: '#fff', borderRadius: 12,
              border: '1px solid #f0f0f0',
            }}>
              <div className="dot-pulse" />
              <Text type="secondary" style={{ fontSize: 13 }}>正在思考...</Text>
            </div>
          )}

          {/* 处理步骤（始终展开显示） */}
          {showSteps && msg.steps && msg.steps.length > 0 && renderStepTimeline(msg.steps)}

          {/* 主内容区 */}
          {msg.content && (
            <div style={{
              background: '#fff', borderRadius: 12, padding: '16px 20px',
              border: '1px solid #f0f0f0', marginBottom: 8,
              boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
            }}>
              <div className="markdown-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              </div>
              {msg.streaming && (
                <span className="cursor-blink" style={{ color: '#1677ff' }}>|</span>
              )}
            </div>
          )}

          {/* SQL展示 */}
          {msg.sql && (
            <div style={{ marginBottom: 8 }}>
              <Collapse
                size="small"
                style={{ borderRadius: 8, border: '1px solid #e6edff' }}
                items={[{
                  key: 'sql',
                  label: (
                    <Space>
                      <CodeOutlined style={{ color: '#1677ff' }} />
                      <Text style={{ fontSize: 13, fontWeight: 500 }}>SQL查询语句</Text>
                    </Space>
                  ),
                  extra: (
                    <CopyOutlined
                      style={{ color: '#1677ff' }}
                      onClick={(e) => { e.stopPropagation(); copyToClipboard(msg.sql || ''); }}
                    />
                  ),
                  children: (
                    <pre style={{
                      background: '#1a1a2e', color: '#a8e6cf', padding: 14, borderRadius: 8,
                      fontSize: 13, overflow: 'auto', margin: 0,
                      fontFamily: "'Fira Code', 'Consolas', monospace",
                      lineHeight: 1.6,
                    }}>
                      {msg.sql}
                    </pre>
                  ),
                }]}
              />
            </div>
          )}

          {/* 查询结果展示 */}
          {msg.query_result && msg.query_result.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <Collapse
                size="small"
                style={{ borderRadius: 8, border: '1px solid #e6f7e6' }}
                items={[{
                  key: 'result',
                  label: (
                    <Space>
                      <DatabaseOutlined style={{ color: '#52c41a' }} />
                      <Text style={{ fontSize: 13, fontWeight: 500 }}>查询结果</Text>
                      <Tag color="green">{msg.query_result.length} 条</Tag>
                    </Space>
                  ),
                  children: (
                    <div style={{ overflow: 'auto', maxHeight: 400 }}>
                      <Table
                        dataSource={msg.query_result.slice(0, 20).map((r, i) => ({ ...r, _key: i }))}
                        columns={Object.keys(msg.query_result[0] || {}).map((col) => ({
                          title: col, dataIndex: col, key: col, ellipsis: true, width: 160,
                          render: (val: any) => <span style={{ fontSize: 12 }}>{String(val ?? '')}</span>,
                        }))}
                        rowKey="_key"
                        pagination={false}
                        size="small"
                        scroll={{ x: true }}
                        bordered
                      />
                    </div>
                  ),
                }]}
              />
            </div>
          )}

          {/* 图表展示 */}
          {msg.images && msg.images.length > 0 && (
            <div style={{
              background: '#fff', borderRadius: 12, padding: '12px 16px',
              border: '1px solid #f0f0f0', marginBottom: 8,
            }}>
              <Space style={{ marginBottom: 8 }}>
                <BarChartOutlined style={{ color: '#fa8c16' }} />
                <Text style={{ fontSize: 13, fontWeight: 500 }}>生成的图表</Text>
                {msg.chart_type && <Tag color="orange">{msg.chart_type}</Tag>}
              </Space>
              <div>
                <Image.PreviewGroup>
                  {msg.images.map((img, imgIdx) => {
                    const imgSrc = img.startsWith('http')
                      ? img
                      : `/results/${img.split(/[/\\]/).pop()}`;
                    return (
                      <Image
                        key={imgIdx}
                        src={imgSrc}
                        alt={`图表${imgIdx + 1}`}
                        style={{ maxWidth: '100%', borderRadius: 8, maxHeight: 500 }}
                        fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMzAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjOTk5Ij7lm77niYfliqDovb3lpLHotKU8L3RleHQ+PC9zdmc+"
                      />
                    );
                  })}
                </Image.PreviewGroup>
              </div>
            </div>
          )}

          {/* 引用来源/归因分析 */}
          {msg.references && msg.references.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{
                background: 'linear-gradient(135deg, #f6ffed 0%, #fff7e6 100%)',
                borderRadius: 12, padding: '12px 16px',
                border: '1px solid #b7eb8f',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <Space>
                    <LinkOutlined style={{ color: '#52c41a' }} />
                    <Text strong style={{ fontSize: 13 }}>归因分析 - 参考来源</Text>
                    <Tag color="green">{msg.references.length}条</Tag>
                  </Space>
                  <Button
                    type="link"
                    size="small"
                    icon={<ExpandOutlined />}
                    onClick={() => {
                      setActiveAttribution(msg.references || []);
                      setAttributionDrawer(true);
                    }}
                  >
                    查看完整链路
                  </Button>
                </div>
                {msg.references.map((ref, refIdx) => (
                  <div key={refIdx} style={{
                    padding: '10px 14px', background: '#fff', borderRadius: 8,
                    marginBottom: 8, fontSize: 12, borderLeft: '3px solid #52c41a',
                    cursor: 'pointer', transition: 'all 0.2s',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                  }}
                    onClick={() => {
                      setActiveAttribution(msg.references || []);
                      setActiveAttributionMsgId(msg.id);
                      setAttributionDrawer(true);
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLDivElement).style.boxShadow = '0 2px 8px rgba(82,196,26,0.15)';
                      (e.currentTarget as HTMLDivElement).style.transform = 'translateX(2px)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLDivElement).style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)';
                      (e.currentTarget as HTMLDivElement).style.transform = 'translateX(0)';
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <FileTextOutlined style={{ color: '#52c41a' }} />
                        <Text strong style={{ fontSize: 13 }}>
                          {ref.source_title || ref.paper_path?.split(/[/\\]/).pop()}
                        </Text>
                        {ref.score && (
                          <Tag color="green" style={{ fontSize: 10, marginLeft: 4 }}>
                            相似度: {ref.score}
                          </Tag>
                        )}
                      </div>
                      <Tag color="blue" style={{ fontSize: 10 }}>来源 {refIdx + 1}</Tag>
                    </div>
                    <Text style={{ fontSize: 12, lineHeight: 1.6, color: '#555', display: 'block' }}>
                      {ref.text}
                    </Text>
                    {ref.paper_path && (
                      <Text type="secondary" style={{ fontSize: 10, marginTop: 4, display: 'block', wordBreak: 'break-all' }}>
                        路径: {ref.paper_path}
                      </Text>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 意图澄清内联卡片 */}
          {msg.needs_clarification && msg.clarification_data && (
            <div style={{
              background: 'linear-gradient(135deg, #fffbe6 0%, #fff7e6 100%)',
              borderRadius: 12, padding: '12px 16px',
              border: '1px solid #ffe58f', marginBottom: 8,
            }}>
              <Space style={{ marginBottom: 8 }}>
                <ExclamationCircleOutlined style={{ color: '#faad14' }} />
                <Text strong style={{ fontSize: 13 }}>需要补充信息</Text>
              </Space>
              <div>
                {msg.clarification_data.options?.map((opt: any, optIdx: number) => (
                  <Tag
                    key={optIdx}
                    style={{
                      cursor: 'pointer', padding: '6px 14px', borderRadius: 16,
                      marginBottom: 6, fontSize: 13,
                      background: selectedOption === opt.value ? '#1677ff' : '#fff',
                      color: selectedOption === opt.value ? '#fff' : '#333',
                      border: `1px solid ${selectedOption === opt.value ? '#1677ff' : '#d9d9d9'}`,
                    }}
                    onClick={() => {
                      setSelectedOption(opt.value);
                      setClarificationMode('select');
                    }}
                  >
                    {opt.label}
                  </Tag>
                ))}
                <div style={{ marginTop: 8 }}>
                  <Input
                    placeholder="或者直接输入补充信息..."
                    value={customInput}
                    onChange={(e) => { setCustomInput(e.target.value); setClarificationMode('input'); }}
                    onPressEnter={handleClarify}
                    suffix={
                      <Button
                        type="primary"
                        size="small"
                        onClick={handleClarify}
                        disabled={!selectedOption && !customInput}
                      >
                        确认
                      </Button>
                    }
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ================= 主界面 =================
  return (
    <div style={{
      height: 'calc(100vh - 56px)',
      display: 'flex', flexDirection: 'column',
      background: '#f8f9fc',
    }}>
      {/* 消息区域 */}
      <div style={{ flex: 1, overflow: 'auto', padding: '20px 0' }}>
        <div style={{ maxWidth: 900, margin: '0 auto' }}>
          {messages.length === 0 ? (
            <div style={{
              display: 'flex', flexDirection: 'column',
              alignItems: 'center', justifyContent: 'center',
              height: 'calc(100vh - 200px)', color: '#999',
            }}>
              <div className="hero-icon" style={{
                width: 80, height: 80, borderRadius: 20,
                background: 'linear-gradient(135deg, #1677ff 0%, #4096ff 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 20, boxShadow: '0 8px 24px rgba(22,119,255,0.25)',
              }}>
                <RobotOutlined style={{ fontSize: 36, color: '#fff' }} />
              </div>
              <Title level={4} style={{ color: '#333', marginBottom: 8 }}>
                上市公司财报智能问数助手
              </Title>
              <Text type="secondary" style={{ textAlign: 'center', maxWidth: 460, lineHeight: 1.8 }}>
                支持自然语言查询、多轮对话、可视化图表生成、知识库检索与归因分析。
                试着问我下面的问题吧：
              </Text>
              <div style={{ marginTop: 24, display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                {[
                  '金花股份利润总额是多少',
                  '华润三九近三年的营业收入趋势',
                  '2024年利润最高的企业有哪些',
                  '国家医保目录新增的中药产品有哪些',
                ].map((q) => (
                  <div
                    key={q}
                    className="suggestion-card"
                    style={{
                      padding: '10px 18px', borderRadius: 12,
                      background: '#fff', border: '1px solid #e6edff',
                      cursor: 'pointer', fontSize: 13, color: '#333',
                      transition: 'all 0.2s',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                    }}
                    onClick={() => setInputValue(q)}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLDivElement).style.borderColor = '#1677ff';
                      (e.currentTarget as HTMLDivElement).style.boxShadow = '0 2px 8px rgba(22,119,255,0.12)';
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLDivElement).style.borderColor = '#e6edff';
                      (e.currentTarget as HTMLDivElement).style.boxShadow = '0 1px 3px rgba(0,0,0,0.04)';
                    }}
                  >
                    <BulbOutlined style={{ marginRight: 6, color: '#faad14' }} />
                    {q}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => (
                <div key={msg.id}>{renderMessage(msg, idx)}</div>
              ))}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 输入区域 */}
      <div style={{
        padding: '12px 24px 20px',
        background: '#fff',
        borderTop: '1px solid #eee',
        boxShadow: '0 -2px 8px rgba(0,0,0,0.04)',
      }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          {/* 增强模式和多轮对话开关 - 类似"深度研究" */}
          <div style={{
            display: 'flex', gap: 12, marginBottom: 10,
            padding: '8px 12px', background: '#f8f9fc',
            borderRadius: 8, border: '1px solid #e6edff',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <ThunderboltOutlined style={{ color: enhancedMode ? '#52c41a' : '#999', fontSize: 14 }} />
              <Text style={{ fontSize: 12, color: enhancedMode ? '#52c41a' : '#666' }}>深度研究</Text>
              <Switch
                checked={enhancedMode}
                onChange={(checked) => {
                  setEnhancedMode(checked);
                  message.info(checked ? '深度研究模式已开启' : '深度研究模式已关闭');
                }}
                size="small"
                style={{ marginLeft: 4 }}
              />
            </div>
            {enhancedMode && (
              <>
                <Divider type="vertical" style={{ height: 20, margin: '0 4px' }} />
                <Tag color="green" style={{ fontSize: 11, margin: 0 }}>
                  知识库+归因分析已启用
                </Tag>
              </>
            )}
          </div>

          <div style={{
            display: 'flex', gap: 8, alignItems: 'flex-end',
            background: '#f8f9fc', borderRadius: 16,
            padding: '8px 12px', border: '1px solid #e6edff',
            transition: 'border-color 0.2s, box-shadow 0.2s',
          }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="输入您的问题，例如：华润三九2024年的营业收入是多少？"
              autoSize={{ minRows: 1, maxRows: 5 }}
              style={{
                border: 'none', background: 'transparent',
                resize: 'none', boxShadow: 'none',
                fontSize: 14,
              }}
              disabled={loading}
            />
            {loading ? (
              <Button
                danger
                shape="circle"
                icon={<CloseCircleOutlined />}
                onClick={handleStop}
                style={{ flexShrink: 0 }}
              />
            ) : (
              <Button
                type="primary"
                shape="circle"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={!inputValue.trim()}
                style={{ flexShrink: 0 }}
              />
            )}
          </div>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginTop: 6, padding: '0 4px',
          }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              Enter 发送 | Shift+Enter 换行
            </Text>
          </div>
        </div>
      </div>

      {/* 归因分析抽屉 - 完整链路可视化 */}
      <Drawer
        title={
          <Space>
            <NodeIndexOutlined style={{ color: '#52c41a' }} />
            归因分析 - 完整生成链路追溯
            <Tag color="green">{activeAttribution.length}条证据</Tag>
          </Space>
        }
        width={900}
        placement="right"
        open={attributionDrawer}
        onClose={() => setAttributionDrawer(false)}
        extra={
          <Space>
            <Text type="secondary" style={{ fontSize: 12 }}>
              点击卡片可查看完整文档
            </Text>
          </Space>
        }
      >
        {activeAttributionMsgId && messages.find(m => m.id === activeAttributionMsgId) ? (
          (() => {
            const activeMsg = messages.find(m => m.id === activeAttributionMsgId)!;
            return (
              <div>
                {/* 完整生成链路时间线 */}
                <Card
                  size="small"
                  title={
                    <Space>
                      <NodeIndexOutlined style={{ color: '#1677ff' }} />
                      <Text strong>生成链路追溯</Text>
                    </Space>
                  }
                  style={{ marginBottom: 16, background: 'linear-gradient(135deg, #f0f5ff 0%, #fff 100%)' }}
                >
                  <Timeline
                    items={activeMsg.steps?.map((step: any, idx: number) => {
                      const cfg = stepConfig[step.step_type] || { label: step.step_type, icon: <CheckCircleOutlined />, color: '#999' };
                      const isCompleted = step.status === 'completed';
                      const isFailed = step.status === 'failed';
                      return {
                        color: isFailed ? 'red' : isCompleted ? 'green' : 'blue',
                        dot: isCompleted ? (
                          <CheckCircleOutlined style={{ color: cfg.color, fontSize: 16 }} />
                        ) : isFailed ? (
                          <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 16 }} />
                        ) : (
                          <LoadingOutlined style={{ color: cfg.color, fontSize: 16 }} />
                        ),
                        children: (
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 4 }}>
                              <span style={{ marginRight: 8 }}>{cfg.icon}</span>
                              <Text strong style={{ fontSize: 13 }}>{cfg.label}</Text>
                              <Tag color={isFailed ? 'red' : isCompleted ? 'green' : 'blue'} style={{ marginLeft: 8, fontSize: 10 }}>
                                {isFailed ? '失败' : isCompleted ? '完成' : '进行中'}
                              </Tag>
                            </div>
                            {step.detail && (
                              <Text type="secondary" style={{ fontSize: 12, display: 'block', marginLeft: 24 }}>
                                {step.detail}
                              </Text>
                            )}
                            {step.data && isCompleted && (
                              <div style={{ marginTop: 8, marginLeft: 24, padding: 8, background: '#fafafa', borderRadius: 4 }}>
                                {step.step_type === 'sql_generation' && step.data.sql && (
                                  <div>
                                    <Text strong style={{ fontSize: 11 }}>SQL: </Text>
                                    <Text code style={{ fontSize: 11 }}>{step.data.sql}</Text>
                                  </div>
                                )}
                                {step.step_type === 'query_execution' && step.data.preview && (
                                  <div>
                                    <Text strong style={{ fontSize: 11 }}>查询结果预览: </Text>
                                    <Table
                                      size="small"
                                      dataSource={step.data.preview}
                                      columns={Object.keys(step.data.preview[0] || {}).map(k => ({ title: k, dataIndex: k, key: k }))}
                                      pagination={false}
                                      style={{ marginTop: 4 }}
                                    />
                                  </div>
                                )}
                                {step.step_type === 'knowledge_search' && step.data && (
                                  <div>
                                    <Text strong style={{ fontSize: 11 }}>检索到 {step.data.length} 条知识: </Text>
                                    <div style={{ marginTop: 4 }}>
                                      {step.data.slice(0, 3).map((item: any, i: number) => (
                                        <Tag key={i} style={{ marginBottom: 4 }}>
                                          {item.title || '未知'} (相似度: {item.score?.toFixed(3)})
                                        </Tag>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ),
                      };
                    }) || []}
                  />
                </Card>

                {/* SQL查询信息 */}
                {activeMsg.sql && (
                  <Card
                    size="small"
                    title={
                      <Space>
                        <CodeOutlined style={{ color: '#1677ff' }} />
                        <Text strong>SQL查询语句</Text>
                      </Space>
                    }
                    style={{ marginBottom: 16 }}
                  >
                    <Text code style={{ fontSize: 12, whiteSpace: 'pre-wrap', display: 'block' }}>
                      {activeMsg.sql}
                    </Text>
                  </Card>
                )}

                {/* 查询结果数据 */}
                {activeMsg.query_result && activeMsg.query_result.length > 0 && (
                  <Card
                    size="small"
                    title={
                      <Space>
                        <DatabaseOutlined style={{ color: '#52c41a' }} />
                        <Text strong>查询结果数据</Text>
                        <Tag>{activeMsg.query_result.length} 条</Tag>
                      </Space>
                    }
                    style={{ marginBottom: 16 }}
                  >
                    <Table
                      size="small"
                      dataSource={activeMsg.query_result.slice(0, 10).map((r: any, i: number) => ({ ...r, key: i }))}
                      columns={Object.keys(activeMsg.query_result[0] || {}).map(k => ({
                        title: k,
                        dataIndex: k,
                        key: k,
                        ellipsis: true,
                      }))}
                      pagination={false}
                      scroll={{ x: 'max-content' }}
                    />
                  </Card>
                )}

                {/* 知识库证据来源 */}
                <Alert
                  type="info"
                  message="知识库证据来源"
                  description="以下展示了回答生成过程中参考的所有知识库来源。每条证据包含原文摘要、相似度分数和文件路径，用于追溯结果的生成逻辑和支撑信息。"
                  style={{ marginBottom: 16 }}
                />
                {activeAttribution.map((ref, idx) => (
              <Card
                key={idx}
                size="small"
                style={{
                  marginBottom: 12,
                  borderLeft: '4px solid #52c41a',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                }}
                title={
                  <Space>
                    <FileTextOutlined style={{ color: '#52c41a' }} />
                    <Text strong style={{ fontSize: 13 }}>
                      {ref.source_title || ref.paper_path?.split(/[/\\]/).pop()}
                    </Text>
                    {ref.score && (
                      <Tag color="green" style={{ fontSize: 11 }}>
                        相似度: {ref.score}
                      </Tag>
                    )}
                  </Space>
                }
                extra={
                  <Space>
                    <Tag color="blue">证据 {idx + 1}</Tag>
                    {ref.score && ref.score > 0.5 && (
                      <Tag color="red">高相关性</Tag>
                    )}
                  </Space>
                }
              >
                <Paragraph style={{
                  fontSize: 13,
                  lineHeight: 1.8,
                  whiteSpace: 'pre-wrap',
                  color: '#333',
                  background: '#fafafa',
                  padding: 12,
                  borderRadius: 6,
                  marginBottom: 8,
                }}>
                  {ref.text}
                </Paragraph>
                <Divider style={{ margin: '8px 0' }} />
                <div style={{ fontSize: 11 }}>
                  <div style={{ marginBottom: 4 }}>
                    <Text type="secondary">文件路径: </Text>
                    <Text code style={{ fontSize: 10, wordBreak: 'break-all' }}>
                      {ref.paper_path}
                    </Text>
                  </div>
                  {ref.source_title && (
                    <div>
                      <Text type="secondary">文档标题: </Text>
                      <Text>{ref.source_title}</Text>
                    </div>
                  )}
                </div>
              </Card>
                ))}
                
                {/* 推理依据说明 */}
                <Card
                  size="small"
                  style={{
                    marginTop: 16,
                    background: 'linear-gradient(135deg, #f6ffed 0%, #fff7e6 100%)',
                    border: '1px solid #b7eb8f',
                  }}
                >
                  <Paragraph style={{ fontSize: 12, margin: 0, color: '#666', lineHeight: 1.8 }}>
                    <Text strong>推理依据说明：</Text>
                    <br />
                    {activeMsg.reasoning_explanation ? (
                      <Text>{activeMsg.reasoning_explanation}</Text>
                    ) : (
                      <Text>系统通过语义检索从知识库中找到与问题相关的文档片段，并按照相似度排序。这些证据片段构成了回答的支撑依据，确保了结果的可追溯性和可解释性。当用户质疑结果合理性时，可以查看这些完整的证据链路。</Text>
                    )}
                  </Paragraph>
                </Card>
              </div>
            );
          })()
        ) : (
          <Empty description="暂无归因数据" />
        )}
      </Drawer>
    </div>
  );
};

export default ChatPage;
