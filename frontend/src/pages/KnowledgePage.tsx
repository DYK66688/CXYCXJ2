import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Space, Typography, Tag, message,
  Upload, Input, Statistic, Row, Col, Modal, Empty, Spin, Popconfirm,
  Progress, Alert,
} from 'antd';
import {
  BookOutlined, UploadOutlined, DeleteOutlined,
  SearchOutlined, FileTextOutlined, ReloadOutlined,
  CloudUploadOutlined, PieChartOutlined,
} from '@ant-design/icons';
import {
  getKnowledgeStats, listKnowledgeDocs, searchKnowledge,
  deleteKnowledgeDoc, uploadKnowledgeFile, addKnowledgeDoc,
} from '../services/api';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const KnowledgePage: React.FC = () => {
  const [stats, setStats] = useState<any>({});
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [addModalVisible, setAddModalVisible] = useState(false);
  const [addContent, setAddContent] = useState('');
  const [addTitle, setAddTitle] = useState('');
  const [uploadProgress, setUploadProgress] = useState<{ stage: string; message: string; progress: number } | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statsData, docsData] = await Promise.all([
        getKnowledgeStats(),
        listKnowledgeDocs(),
      ]);
      setStats(statsData);
      setDocuments(docsData);
    } catch (error) {
      // 知识库可能为空，不报错
    }
    setLoading(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const results = await searchKnowledge(searchQuery.trim());
      setSearchResults(results);
      if (results.length === 0) {
        message.info('未找到相关结果');
      }
    } catch (error) {
      message.error('搜索失败');
    }
    setSearchLoading(false);
  };

  const handleDelete = async (sourcePath: string) => {
    try {
      await deleteKnowledgeDoc(sourcePath);
      message.success('删除成功');
      loadData();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadProgress({ stage: 'starting', message: '开始上传...', progress: 0 });
    try {
      const result = await uploadKnowledgeFile(file, (progress) => {
        setUploadProgress(progress);
      });
      message.success(`上传成功，已添加 ${result.chunks_added} 个知识块`);
      setUploadProgress(null);
      loadData();
    } catch (error: any) {
      message.error(`上传失败: ${error.message || '未知错误'}`);
      setUploadProgress(null);
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleAddManual = async () => {
    if (!addContent.trim()) return;
    try {
      const result = await addKnowledgeDoc({
        content: addContent,
        source_title: addTitle || '手动添加',
        source_type: 'manual',
      });
      message.success(`添加成功，${result.chunks_added} 个知识块`);
      setAddModalVisible(false);
      setAddContent('');
      setAddTitle('');
      loadData();
    } catch (error) {
      message.error('添加失败');
    }
  };

  const docColumns = [
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source_type',
      render: (v: string) => (
        <Tag color={
          v?.includes('individual') ? 'blue' :
          v?.includes('industry') ? 'green' :
          v?.includes('financial') ? 'orange' : 'default'
        }>
          {v?.replace('research_', '') || '未知'}
        </Tag>
      ),
    },
    {
      title: '标题',
      dataIndex: 'source_title',
      key: 'source_title',
      ellipsis: true,
    },
    {
      title: '知识块数',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 100,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: any) => (
        <Popconfirm
          title="确定删除此文档？"
          onConfirm={() => handleDelete(record.source_path)}
        >
          <Button type="link" danger size="small" icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 24, height: 'calc(100vh - 56px)', overflow: 'auto' }}>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={8}>
          <Card size="small" style={{ borderRadius: 8 }}>
            <Statistic
              title="文档总数"
              value={stats.total_documents || 0}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={8}>
          <Card size="small" style={{ borderRadius: 8 }}>
            <Statistic
              title="知识块总数"
              value={stats.total_chunks || 0}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col xs={8}>
          <Card size="small" style={{ borderRadius: 8 }}>
            <Statistic
              title="研报总数"
              value={stats.total_research_reports || 0}
              prefix={<PieChartOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 上传进度显示 */}
      {uploadProgress && (
        <Alert
          message={
            <Space>
              <Spin size="small" />
              <span>{uploadProgress.message}</span>
              <Progress 
                percent={uploadProgress.progress} 
                size="small" 
                style={{ width: 200, marginLeft: 16 }}
                status={uploadProgress.progress === 100 ? 'success' : 'active'}
              />
            </Space>
          }
          type="info"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setUploadProgress(null)}
        />
      )}

      <Row gutter={16}>
        {/* 文档列表 */}
        <Col xs={24} lg={14}>
          <Card
            title={<><BookOutlined /> 知识库文档</>}
            size="small"
            style={{ borderRadius: 8, marginBottom: 16 }}
            extra={
              <Space>
                <Upload
                  beforeUpload={handleUpload as any}
                  showUploadList={false}
                  accept=".pdf,.txt,.md"
                  disabled={uploading}
                >
                  <Button size="small" icon={<CloudUploadOutlined />}>
                    上传文件
                  </Button>
                </Upload>
                <Button size="small" onClick={() => setAddModalVisible(true)}>
                  手动添加
                </Button>
                <Button size="small" icon={<ReloadOutlined />} onClick={loadData} />
              </Space>
            }
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : documents.length > 0 ? (
              <Table
                dataSource={documents}
                columns={docColumns}
                rowKey="source_path"
                size="small"
                pagination={{ pageSize: 10 }}
              />
            ) : (
              <Empty description="知识库为空，请先运行任务一初始化或手动添加文档" />
            )}
          </Card>
        </Col>

        {/* 搜索面板 */}
        <Col xs={24} lg={10}>
          <Card
            title={<><SearchOutlined /> 语义搜索</>}
            size="small"
            style={{ borderRadius: 8 }}
          >
            <Space.Compact style={{ width: '100%', marginBottom: 12 }}>
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="输入搜索内容..."
                onPressEnter={handleSearch}
              />
              <Button
                type="primary"
                icon={<SearchOutlined />}
                onClick={handleSearch}
                loading={searchLoading}
              >
                搜索
              </Button>
            </Space.Compact>

            {searchResults.length > 0 ? (
              searchResults.map((result, idx) => (
                <Card
                  key={idx}
                  size="small"
                  style={{ marginBottom: 8, borderRadius: 8 }}
                >
                  <Space style={{ marginBottom: 4 }}>
                    <Tag color="blue">{(result.score * 100).toFixed(1)}%</Tag>
                    <Text style={{ fontSize: 12 }} type="secondary">
                      {result.source_title}
                    </Text>
                  </Space>
                  <Paragraph
                    ellipsis={{ rows: 4, expandable: true }}
                    style={{ fontSize: 13, margin: 0 }}
                  >
                    {result.content}
                  </Paragraph>
                </Card>
              ))
            ) : (
              <Empty description="输入关键词进行语义搜索" />
            )}
          </Card>
        </Col>
      </Row>

      {/* 手动添加弹窗 */}
      <Modal
        title="手动添加知识"
        open={addModalVisible}
        onOk={handleAddManual}
        onCancel={() => setAddModalVisible(false)}
        width={600}
      >
        <Input
          placeholder="标题"
          value={addTitle}
          onChange={(e) => setAddTitle(e.target.value)}
          style={{ marginBottom: 8 }}
        />
        <TextArea
          placeholder="粘贴知识内容..."
          value={addContent}
          onChange={(e) => setAddContent(e.target.value)}
          autoSize={{ minRows: 6, maxRows: 15 }}
        />
      </Modal>
    </div>
  );
};

export default KnowledgePage;
