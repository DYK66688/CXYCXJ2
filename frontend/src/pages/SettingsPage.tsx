import React, { useState, useEffect } from 'react';
import {
  Card, Form, Input, InputNumber, Select, Switch, Button, Space,
  Typography, Divider, message, Tag, Collapse, Spin, Alert,
  Segmented, Tooltip, Badge, Row, Col, Slider, Tabs,
} from 'antd';
import {
  SettingOutlined, ApiOutlined, ThunderboltOutlined,
  SaveOutlined, ReloadOutlined, CheckCircleOutlined,
  ExperimentOutlined, PictureOutlined, FontSizeOutlined,
  EyeOutlined, RobotOutlined, DatabaseOutlined, CloudOutlined,
} from '@ant-design/icons';
import { getConfig, updateConfig, testLLMConnection, testEmbeddingConnection, healthCheck } from '../services/api';
import { useAppStore } from '../services/store';

const { Text, Title, Paragraph } = Typography;

const SettingsPage: React.FC = () => {
  const [configData, setConfigData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testingLLM, setTestingLLM] = useState<number | null>(null);
  const [testingEmbedding, setTestingEmbedding] = useState(false);
  const [health, setHealth] = useState<any>(null);

  const {
    enhancedMode, setEnhancedMode,
    chartStyle, setChartStyle,
    fontSize, setFontSize,
    showSteps, setShowSteps,
    theme, setTheme,
  } = useAppStore();

  useEffect(() => {
    loadConfig();
    loadHealth();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const data = await getConfig();
      // 确保所有配置存在
      if (!data.rag) {
        data.rag = {
          chunk_size: 500,
          chunk_overlap: 100,
          top_k: 15,
          min_score: 0.2,
          max_kb_context_chunks: 8,
          max_attribution_results: 15,
          additional_search_top_k: 5,
          additional_search_score_ratio: 0.75,
        };
      }
      if (!data.llm_client) {
        data.llm_client = {
          max_retries: 3,
          retry_delay_base: 2.0,
          timeout: 60,
          json_mode_temperature: 0.3,
        };
      }
      if (!data.embedding_model) {
        data.embedding_model = { batch_size: 10 };
      }
      if (!data.sql_generator) {
        data.sql_generator = {
          max_sql_length: 2000,
          enable_fuzzy_match: true,
          fuzzy_match_threshold: 0.7,
        };
      }
      if (!data.chart_generator) {
        data.chart_generator = {
          default_figsize_width: 10.0,
          default_figsize_height: 6.0,
          dpi: 100,
          max_data_points: 50,
        };
      }
      if (!data.agent) {
        data.agent = {
          max_history_turns: 10,
          enable_multi_intent_planning: true,
          enable_intent_clarification: true,
          clarification_confidence_threshold: 0.6,
          max_sub_tasks: 5,
        };
      }
      setConfigData(data);
    } catch (e) {
      message.error('加载配置失败，请确认后端已启动');
    } finally {
      setLoading(false);
    }
  };

  const loadHealth = async () => {
    try {
      const h = await healthCheck();
      setHealth(h);
    } catch { }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateConfig(configData);
      message.success('配置已保存');
    } catch (e: any) {
      message.error(`保存失败: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTestLLM = async (idx: number) => {
    const llm = configData?.llm_configs[idx];
    if (!llm) return;
    setTestingLLM(idx);
    try {
      const result = await testLLMConnection({
        api_key: llm.api_key || '',
        base_url: llm.base_url || '',
        model: llm.model || '',
        llm_index: idx, // 传递索引，后端可以从配置中读取
      });
      if (result.status === 'ok') {
        message.success(`连接成功: ${result.response}`);
      } else {
        message.error(`连接失败: ${result.message}`);
      }
    } catch (e: any) {
      message.error(`测试失败: ${e.message}`);
    } finally {
      setTestingLLM(null);
    }
  };

  const handleTestEmbedding = async () => {
    const emb = configData?.embedding;
    if (!emb) return;
    setTestingEmbedding(true);
    try {
      const result = await testEmbeddingConnection({
        use_local: emb.use_local,
        api_base_url: emb.api_base_url || '',
        api_key: emb.api_key || '',
        api_model: emb.api_model || '',
        local_model_path: emb.local_model_path || '',
      });
      if (result.status === 'ok') {
        message.success(`连接成功: ${result.message}`);
      } else {
        message.error(`连接失败: ${result.message}`);
      }
    } catch (e: any) {
      message.error(`测试失败: ${e.message}`);
    } finally {
      setTestingEmbedding(false);
    }
  };

  const updateLLMConfig = (idx: number, field: string, value: any) => {
    setConfigData((prev: any) => {
      const configs = [...prev.llm_configs];
      configs[idx] = { ...configs[idx], [field]: value };
      return { ...prev, llm_configs: configs };
    });
  };

  const updateEmbeddingConfig = (field: string, value: any) => {
    setConfigData((prev: any) => ({
      ...prev,
      embedding: { ...prev.embedding, [field]: value }
    }));
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Spin size="large" tip="加载配置中..." />
      </div>
    );
  }

  return (
    <div style={{
      padding: 24,
      maxWidth: 1200,
      margin: '0 auto',
      height: 'calc(100vh - 56px)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* 系统状态 */}
      {health && (
        <Alert
          type="success"
          showIcon
          icon={<CheckCircleOutlined />}
          message={
            <Space wrap>
              <Text>系统运行正常</Text>
              <Tag color="blue">LLM: {health.llm_count} 个</Tag>
              <Tag color="green">数据库: {health.db_path?.split(/[/\\]/).pop()}</Tag>
              {health.db_tables && Object.entries(health.db_tables).map(([k, v]) => (
                <Tag key={k} color="cyan">{k}: {String(v)}条</Tag>
              ))}
            </Space>
          }
          style={{ marginBottom: 20, borderRadius: 12, flexShrink: 0 }}
        />
      )}

      {health && ((health.warnings && health.warnings.length > 0) || (health.errors && health.errors.length > 0)) && (
        <Alert
          type={health.errors && health.errors.length > 0 ? 'error' : 'warning'}
          showIcon
          message="启动自检提示"
          description={
            <Space direction="vertical" size={4}>
              {(health.errors || []).map((item: string, idx: number) => (
                <Text key={`error_${idx}`} type="danger">{item}</Text>
              ))}
              {(health.warnings || []).map((item: string, idx: number) => (
                <Text key={`warning_${idx}`}>{item}</Text>
              ))}
            </Space>
          }
          style={{ marginBottom: 20, borderRadius: 12, flexShrink: 0 }}
        />
      )}

      {/* 主内容区域 - 使用flex布局避免滚动条问题 */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <Tabs
          defaultActiveKey="llm"
          style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}
          items={[
            {
              key: 'llm',
              label: <Space><ApiOutlined />大模型配置</Space>,
              children: (
                <div style={{ overflow: 'auto', flex: 1 }}>
                  <Card
                    extra={
                      <Space>
                        <Button icon={<ReloadOutlined />} onClick={loadConfig} size="small">刷新</Button>
                        <Button icon={<SaveOutlined />} type="primary" onClick={handleSave} loading={saving} size="small">
                          保存配置
                        </Button>
                      </Space>
                    }
                    style={{ borderRadius: 12 }}
                  >
                    <Collapse
                      accordion
                      items={configData?.llm_configs?.map((llm: any, idx: number) => ({
                        key: idx.toString(),
                        label: (
                          <Space>
                            <Badge status={llm.enabled ? 'success' : 'default'} />
                            <Text strong>{llm.name}</Text>
                            <Tag>{llm.model}</Tag>
                            {!llm.api_key_set && !llm.api_key && <Tag color="warning">未配置API Key</Tag>}
                          </Space>
                        ),
                        extra: (
                          <Space onClick={(e) => e.stopPropagation()}>
                            <Switch
                              checked={llm.enabled}
                              size="small"
                              onChange={(v) => updateLLMConfig(idx, 'enabled', v)}
                            />
                            <Button
                              size="small"
                              loading={testingLLM === idx}
                              onClick={(e) => { e.stopPropagation(); handleTestLLM(idx); }}
                            >
                              测试
                            </Button>
                          </Space>
                        ),
                        children: (
                          <div style={{ padding: '8px 0' }}>
                            <Form layout="vertical" size="small">
                              <Row gutter={12}>
                                <Col span={12}>
                                  <Form.Item label="名称">
                                    <Input value={llm.name} onChange={(e) => updateLLMConfig(idx, 'name', e.target.value)} />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="模型">
                                    <Input value={llm.model} onChange={(e) => updateLLMConfig(idx, 'model', e.target.value)} />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Form.Item label="API Base URL">
                                <Input value={llm.base_url} onChange={(e) => updateLLMConfig(idx, 'base_url', e.target.value)} />
                              </Form.Item>
                              <Form.Item label="API Key">
                                <Input.Password
                                  value={llm.api_key || ''}
                                  onChange={(e) => updateLLMConfig(idx, 'api_key', e.target.value)}
                                  placeholder={llm.api_key_set ? '已配置（留空保持不变）' : '请输入API Key'}
                                />
                              </Form.Item>
                              <Row gutter={12}>
                                <Col span={8}>
                                  <Form.Item label="Temperature">
                                    <Slider min={0} max={2} step={0.1} value={llm.temperature}
                                      onChange={(v) => updateLLMConfig(idx, 'temperature', v)} />
                                    <Text type="secondary" style={{ fontSize: 11 }}>{llm.temperature}</Text>
                                  </Form.Item>
                                </Col>
                                <Col span={8}>
                                  <Form.Item label="Top P">
                                    <Slider min={0} max={1} step={0.05} value={llm.top_p}
                                      onChange={(v) => updateLLMConfig(idx, 'top_p', v)} />
                                    <Text type="secondary" style={{ fontSize: 11 }}>{llm.top_p}</Text>
                                  </Form.Item>
                                </Col>
                                <Col span={8}>
                                  <Form.Item label="Max Tokens">
                                    <InputNumber min={256} max={32768} value={llm.max_tokens} style={{ width: '100%' }}
                                      onChange={(v) => updateLLMConfig(idx, 'max_tokens', v)} />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Form.Item label="权重（负载均衡）">
                                <Slider min={0.1} max={5} step={0.1} value={llm.weight}
                                  onChange={(v) => updateLLMConfig(idx, 'weight', v)} />
                              </Form.Item>
                            </Form>
                          </div>
                        ),
                      }))}
                    />

                    <Divider style={{ margin: '16px 0 12px' }} />

                    <Form layout="vertical" size="small">
                      <Form.Item label="最大并发请求数">
                        <InputNumber
                          min={1} max={200}
                          value={configData?.max_concurrent_requests}
                          onChange={(v) => setConfigData((p: any) => ({ ...p, max_concurrent_requests: v }))}
                          style={{ width: 200 }}
                        />
                      </Form.Item>
                    </Form>
                  </Card>
                </div>
              ),
            },
            {
              key: 'embedding',
              label: <Space><DatabaseOutlined />嵌入模型配置</Space>,
              children: (
                <div style={{ overflow: 'auto', flex: 1 }}>
                  <Card
                    extra={
                      <Space>
                        <Button icon={<ReloadOutlined />} onClick={loadConfig} size="small">刷新</Button>
                        <Button icon={<SaveOutlined />} type="primary" onClick={handleSave} loading={saving} size="small">
                          保存配置
                        </Button>
                      </Space>
                    }
                    style={{ borderRadius: 12 }}
                  >
                    <Form layout="vertical" size="small">
                      <Form.Item label="模型类型">
                        <Select
                          value={configData?.embedding?.use_local ? 'local' : 'cloud'}
                          onChange={(v) => updateEmbeddingConfig('use_local', v === 'local')}
                          options={[
                            { label: <Space><DatabaseOutlined />本地模型</Space>, value: 'local' },
                            { label: <Space><CloudOutlined />云端模型</Space>, value: 'cloud' },
                          ]}
                        />
                      </Form.Item>

                      {configData?.embedding?.use_local ? (
                        <>
                          <Form.Item label="本地模型路径">
                            <Input
                              value={configData?.embedding?.local_model_path}
                              onChange={(e) => updateEmbeddingConfig('local_model_path', e.target.value)}
                              placeholder="如: models/bge-small-zh-v1.5"
                            />
                          </Form.Item>
                          <Row gutter={12}>
                            <Col span={12}>
                              <Form.Item label="向量维度">
                                <InputNumber
                                  value={configData?.embedding?.dimension}
                                  onChange={(v) => updateEmbeddingConfig('dimension', v)}
                                  style={{ width: '100%' }}
                                />
                              </Form.Item>
                            </Col>
                            <Col span={12}>
                              <Form.Item label="运行设备">
                                <Select
                                  value={configData?.embedding?.device}
                                  onChange={(v) => updateEmbeddingConfig('device', v)}
                                  options={[
                                    { label: 'CPU', value: 'cpu' },
                                    { label: 'CUDA (GPU)', value: 'cuda' },
                                    { label: '自动选择', value: 'auto' },
                                  ]}
                                />
                              </Form.Item>
                            </Col>
                          </Row>
                        </>
                      ) : (
                        <>
                          <Form.Item label="API Base URL">
                            <Input
                              value={configData?.embedding?.api_base_url || ''}
                              onChange={(e) => updateEmbeddingConfig('api_base_url', e.target.value)}
                              placeholder="如: https://api.siliconflow.cn/v1/"
                            />
                          </Form.Item>
                          <Form.Item label="API Key">
                            <Input.Password
                              value={configData?.embedding?.api_key || ''}
                              onChange={(e) => updateEmbeddingConfig('api_key', e.target.value)}
                              placeholder="请输入API Key"
                            />
                          </Form.Item>
                          <Form.Item label="模型名称">
                            <Input
                              value={configData?.embedding?.api_model || ''}
                              onChange={(e) => updateEmbeddingConfig('api_model', e.target.value)}
                              placeholder="如: BAAI/bge-large-zh-v1.5"
                            />
                          </Form.Item>
                          <Form.Item>
                            <Button
                              type="primary"
                              icon={<CloudOutlined />}
                              loading={testingEmbedding}
                              onClick={handleTestEmbedding}
                            >
                              测试连接
                            </Button>
                          </Form.Item>
                        </>
                      )}
                    </Form>
                  </Card>
                </div>
              ),
            },
            {
              key: 'hyperparams',
              label: <Space><ExperimentOutlined />超参数配置</Space>,
              children: (
                <div style={{ overflow: 'auto', flex: 1 }}>
                  <Card
                    extra={
                      <Space>
                        <Button icon={<ReloadOutlined />} onClick={loadConfig} size="small">刷新</Button>
                        <Button icon={<SaveOutlined />} type="primary" onClick={handleSave} loading={saving} size="small">
                          保存配置
                        </Button>
                      </Space>
                    }
                    style={{ borderRadius: 12 }}
                  >
                    <Tabs
                      defaultActiveKey="rag"
                      items={[
                        {
                          key: 'rag',
                          label: 'RAG检索配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="文本分块大小">
                                    <InputNumber
                                      min={100} max={2000} step={50}
                                      value={configData?.rag?.chunk_size || 500}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, chunk_size: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="分块重叠大小">
                                    <InputNumber
                                      min={0} max={500} step={10}
                                      value={configData?.rag?.chunk_overlap || 100}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, chunk_overlap: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="检索Top-K数量">
                                    <InputNumber
                                      min={1} max={50}
                                      value={configData?.rag?.top_k || 15}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, top_k: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="最小相似度阈值">
                                    <Slider
                                      min={0} max={1} step={0.05}
                                      value={configData?.rag?.min_score || 0.2}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, min_score: v } }))}
                                      marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="最大知识库上下文块数">
                                    <InputNumber
                                      min={1} max={20}
                                      value={configData?.rag?.max_kb_context_chunks || 8}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, max_kb_context_chunks: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="归因分析最大结果数">
                                    <InputNumber
                                      min={1} max={30}
                                      value={configData?.rag?.max_attribution_results || 15}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, max_attribution_results: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="额外搜索Top-K">
                                    <InputNumber
                                      min={1} max={20}
                                      value={configData?.rag?.additional_search_top_k || 5}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, additional_search_top_k: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="额外搜索相似度比例">
                                    <Slider
                                      min={0} max={1} step={0.05}
                                      value={configData?.rag?.additional_search_score_ratio || 0.75}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, rag: { ...p.rag, additional_search_score_ratio: v } }))}
                                      marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                            </Form>
                          ),
                        },
                        {
                          key: 'llm',
                          label: 'LLM调用配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="最大重试次数">
                                    <InputNumber
                                      min={1} max={10}
                                      value={configData?.llm_client?.max_retries || 3}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, llm_client: { ...p.llm_client, max_retries: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="重试延迟基数（秒）">
                                    <InputNumber
                                      min={0.5} max={10} step={0.5}
                                      value={configData?.llm_client?.retry_delay_base || 2.0}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, llm_client: { ...p.llm_client, retry_delay_base: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="请求超时时间（秒）">
                                    <InputNumber
                                      min={10} max={300}
                                      value={configData?.llm_client?.timeout || 60}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, llm_client: { ...p.llm_client, timeout: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="JSON模式温度">
                                    <Slider
                                      min={0} max={1} step={0.1}
                                      value={configData?.llm_client?.json_mode_temperature || 0.3}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, llm_client: { ...p.llm_client, json_mode_temperature: v } }))}
                                      marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                            </Form>
                          ),
                        },
                        {
                          key: 'agent',
                          label: 'Agent配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="最大历史轮次">
                                    <InputNumber
                                      min={1} max={50}
                                      value={configData?.agent?.max_history_turns || 10}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, agent: { ...p.agent, max_history_turns: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="最大子任务数">
                                    <InputNumber
                                      min={1} max={10}
                                      value={configData?.agent?.max_sub_tasks || 5}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, agent: { ...p.agent, max_sub_tasks: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="启用多意图规划">
                                    <Switch
                                      checked={configData?.agent?.enable_multi_intent_planning !== false}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, agent: { ...p.agent, enable_multi_intent_planning: v } }))}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="启用意图澄清">
                                    <Switch
                                      checked={configData?.agent?.enable_intent_clarification !== false}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, agent: { ...p.agent, enable_intent_clarification: v } }))}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Form.Item label="澄清置信度阈值">
                                <Slider
                                  min={0} max={1} step={0.05}
                                  value={configData?.agent?.clarification_confidence_threshold || 0.6}
                                  onChange={(v) => setConfigData((p: any) => ({ ...p, agent: { ...p.agent, clarification_confidence_threshold: v } }))}
                                  marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                                />
                              </Form.Item>
                            </Form>
                          ),
                        },
                        {
                          key: 'sql',
                          label: 'SQL生成器配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="最大SQL长度">
                                    <InputNumber
                                      min={500} max={5000} step={100}
                                      value={configData?.sql_generator?.max_sql_length || 2000}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, sql_generator: { ...p.sql_generator, max_sql_length: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="启用模糊匹配">
                                    <Switch
                                      checked={configData?.sql_generator?.enable_fuzzy_match !== false}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, sql_generator: { ...p.sql_generator, enable_fuzzy_match: v } }))}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Form.Item label="模糊匹配阈值">
                                <Slider
                                  min={0} max={1} step={0.05}
                                  value={configData?.sql_generator?.fuzzy_match_threshold || 0.7}
                                  onChange={(v) => setConfigData((p: any) => ({ ...p, sql_generator: { ...p.sql_generator, fuzzy_match_threshold: v } }))}
                                  marks={{ 0: '0', 0.5: '0.5', 1: '1' }}
                                />
                              </Form.Item>
                            </Form>
                          ),
                        },
                        {
                          key: 'chart',
                          label: '图表生成器配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="默认图表宽度（英寸）">
                                    <InputNumber
                                      min={5} max={20} step={0.5}
                                      value={configData?.chart_generator?.default_figsize_width || 10.0}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, chart_generator: { ...p.chart_generator, default_figsize_width: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="默认图表高度（英寸）">
                                    <InputNumber
                                      min={3} max={15} step={0.5}
                                      value={configData?.chart_generator?.default_figsize_height || 6.0}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, chart_generator: { ...p.chart_generator, default_figsize_height: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                              <Row gutter={16}>
                                <Col span={12}>
                                  <Form.Item label="图表分辨率（DPI）">
                                    <InputNumber
                                      min={50} max={300} step={10}
                                      value={configData?.chart_generator?.dpi || 100}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, chart_generator: { ...p.chart_generator, dpi: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                                <Col span={12}>
                                  <Form.Item label="最大数据点数">
                                    <InputNumber
                                      min={10} max={200}
                                      value={configData?.chart_generator?.max_data_points || 50}
                                      onChange={(v) => setConfigData((p: any) => ({ ...p, chart_generator: { ...p.chart_generator, max_data_points: v } }))}
                                      style={{ width: '100%' }}
                                    />
                                  </Form.Item>
                                </Col>
                              </Row>
                            </Form>
                          ),
                        },
                        {
                          key: 'embedding',
                          label: '嵌入模型配置',
                          children: (
                            <Form layout="vertical" size="small">
                              <Form.Item label="批处理大小">
                                <InputNumber
                                  min={1} max={100}
                                  value={configData?.embedding_model?.batch_size || 10}
                                  onChange={(v) => setConfigData((p: any) => ({ ...p, embedding_model: { ...p.embedding_model, batch_size: v } }))}
                                  style={{ width: 200 }}
                                />
                              </Form.Item>
                            </Form>
                          ),
                        },
                      ]}
                    />
                  </Card>
                </div>
              ),
            },
            {
              key: 'ui',
              label: <Space><EyeOutlined />界面设置</Space>,
              children: (
                <div style={{ overflow: 'auto', flex: 1 }}>
                  <Row gutter={20}>
                    <Col span={12}>
                      <Card title={<Space><EyeOutlined /><span>界面设置</span></Space>} style={{ borderRadius: 12, marginBottom: 20 }}>
                        <Form layout="vertical" size="small">
                          <Form.Item label="增强模式（知识库+归因分析）">
                            <Switch checked={enhancedMode} onChange={setEnhancedMode} />
                            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                              开启后支持知识库检索、多意图规划和归因分析
                            </Text>
                          </Form.Item>

                          <Form.Item label="默认展开处理步骤">
                            <Switch checked={showSteps} onChange={setShowSteps} />
                            <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                              展示AI处理的完整中间过程
                            </Text>
                          </Form.Item>

                          <Form.Item label="字体大小">
                            <Segmented
                              value={fontSize}
                              onChange={(v) => setFontSize(v as any)}
                              options={[
                                { label: '小', value: 'small' },
                                { label: '中', value: 'medium' },
                                { label: '大', value: 'large' },
                              ]}
                            />
                          </Form.Item>
                        </Form>
                      </Card>

                      <Card title={<Space><PictureOutlined /><span>图表风格</span></Space>} style={{ borderRadius: 12, marginBottom: 20 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                          {[
                            { key: 'default', label: '现代简洁', desc: '清晰简洁，适合日常使用', color: '#3b82f6', colors: ['#3b82f6', '#ef4444', '#22c55e'] },
                            { key: 'academic', label: '学术风格', desc: '适合论文和学术报告', color: '#1f77b4', colors: ['#1f77b4', '#ff7f0e', '#2ca02c'] },
                            { key: 'business', label: '商务风格', desc: '适合商业报告和演示', color: '#0369a1', colors: ['#0369a1', '#0e7490', '#047857'] },
                            { key: 'minimal', label: '极简风格', desc: '简约现代的设计风格', color: '#6366f1', colors: ['#6366f1', '#a855f7', '#ec4899'] },
                            { key: 'dark', label: '暗黑风格', desc: '深色背景，适合暗色主题', color: '#60a5fa', colors: ['#60a5fa', '#f87171', '#4ade80'] },
                            { key: 'colorful', label: '多彩风格', desc: '鲜明配色，视觉活泼', color: '#f43f5e', colors: ['#f43f5e', '#8b5cf6', '#06b6d4'] },
                            { key: 'financial', label: '金融专业', desc: '专业金融分析报告风格', color: '#1b4965', colors: ['#1b4965', '#c73e3a', '#2a7d4f'] },
                            { key: 'elegant', label: '雅致风格', desc: '柔和优雅的莫兰迪色调', color: '#b5838d', colors: ['#b5838d', '#6d6875', '#e5989b'] },
                          ].map((item) => (
                            <div
                              key={item.key}
                              onClick={() => setChartStyle(item.key as any)}
                              style={{
                                padding: '12px',
                                borderRadius: 10,
                                border: `2px solid ${chartStyle === item.key ? item.color : '#f0f0f0'}`,
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                background: chartStyle === item.key ? `${item.color}08` : '#fff',
                              }}
                            >
                              <div style={{ display: 'flex', gap: 3, marginBottom: 8 }}>
                                {item.colors.map((c, ci) => (
                                  <div key={ci} style={{
                                    flex: 1, height: 5, borderRadius: 3,
                                    background: c, opacity: chartStyle === item.key ? 1 : 0.35,
                                    transition: 'opacity 0.2s',
                                  }} />
                                ))}
                              </div>
                              <Text strong style={{ fontSize: 13, color: chartStyle === item.key ? item.color : '#333' }}>
                                {item.label}
                              </Text>
                              <br />
                              <Text type="secondary" style={{ fontSize: 11 }}>{item.desc}</Text>
                            </div>
                          ))}
                        </div>
                      </Card>

                      <Card title={<Space><ExperimentOutlined /><span>RAG超参数配置</span></Space>} style={{ borderRadius: 12 }}>
                        <Form layout="vertical" size="small">
                          <Form.Item label={
                            <Space>
                              <Text>文本分块大小</Text>
                              <Tooltip title="知识库文档分块时的每块字符数">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <InputNumber
                              min={100}
                              max={2000}
                              step={50}
                              value={configData?.rag?.chunk_size || 500}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, chunk_size: v }
                              }))}
                              style={{ width: '100%' }}
                            />
                            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                              当前: {configData?.rag?.chunk_size || 500} 字符
                            </Text>
                          </Form.Item>

                          <Form.Item label={
                            <Space>
                              <Text>分块重叠大小</Text>
                              <Tooltip title="相邻分块之间的重叠字符数，用于保持上下文连贯性">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <InputNumber
                              min={0}
                              max={500}
                              step={10}
                              value={configData?.rag?.chunk_overlap || 100}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, chunk_overlap: v }
                              }))}
                              style={{ width: '100%' }}
                            />
                            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                              当前: {configData?.rag?.chunk_overlap || 100} 字符
                            </Text>
                          </Form.Item>

                          <Form.Item label={
                            <Space>
                              <Text>检索Top-K数量</Text>
                              <Tooltip title="知识库检索时返回的最相似结果数量">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <InputNumber
                              min={1}
                              max={50}
                              value={configData?.rag?.top_k || 15}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, top_k: v }
                              }))}
                              style={{ width: '100%' }}
                            />
                            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
                              当前: {configData?.rag?.top_k || 15} 条
                            </Text>
                          </Form.Item>

                          <Form.Item label={
                            <Space>
                              <Text>最小相似度阈值</Text>
                              <Tooltip title="向量相似度低于此值的结果将被过滤，值越低检索结果越多">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <Slider
                              min={0}
                              max={1}
                              step={0.05}
                              value={configData?.rag?.min_score || 0.2}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, min_score: v }
                              }))}
                              marks={{
                                0: '0',
                                0.3: '0.3',
                                0.5: '0.5',
                                0.7: '0.7',
                                1: '1',
                              }}
                            />
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              当前: {configData?.rag?.min_score || 0.2}
                            </Text>
                          </Form.Item>

                          <Form.Item label={
                            <Space>
                              <Text>最大知识库上下文块数</Text>
                              <Tooltip title="用于生成回答的最大知识库块数量">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <InputNumber
                              min={1}
                              max={20}
                              value={configData?.rag?.max_kb_context_chunks || 8}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, max_kb_context_chunks: v }
                              }))}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>

                          <Form.Item label={
                            <Space>
                              <Text>归因分析最大结果数</Text>
                              <Tooltip title="归因分析中显示的最大证据数量">
                                <ExperimentOutlined style={{ color: '#999', fontSize: 12 }} />
                              </Tooltip>
                            </Space>
                          }>
                            <InputNumber
                              min={1}
                              max={30}
                              value={configData?.rag?.max_attribution_results || 15}
                              onChange={(v) => setConfigData((p: any) => ({
                                ...p,
                                rag: { ...p.rag, max_attribution_results: v }
                              }))}
                              style={{ width: '100%' }}
                            />
                          </Form.Item>
                        </Form>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card title={<Space><ExperimentOutlined /><span>关于系统</span></Space>} style={{ borderRadius: 12 }}>
                        <Paragraph style={{ fontSize: 13 }}>
                          <Text strong>上市公司财报智能问数助手</Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            版本: 1.0.0
                          </Text>
                          <br />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            2026年"泰迪杯"数据挖掘挑战赛B题解决方案
                          </Text>
                        </Paragraph>
                        <Paragraph style={{ fontSize: 12, color: '#999' }}>
                          支持自然语言查询、多轮对话、图表生成、知识库检索、多意图规划、归因分析等完整功能。
                          基于 DeepSeek/GLM 大模型 + RAG 知识库 + SQLite 结构化数据。
                        </Paragraph>
                        <Space direction="vertical" size={4}>
                          <Tag color="blue">React + TypeScript + Ant Design</Tag>
                          <Tag color="green">FastAPI + SQLite</Tag>
                          <Tag color="purple">DeepSeek-V3 / GLM-4</Tag>
                        </Space>
                      </Card>
                    </Col>
                  </Row>
                </div>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
};

export default SettingsPage;
