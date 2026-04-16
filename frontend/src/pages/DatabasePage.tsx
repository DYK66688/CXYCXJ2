import React, { useState, useEffect } from 'react';
import {
  Card, Table, Statistic, Row, Col, Input, Button, Space,
  Typography, Tag, message, Tabs, Empty, Spin,
} from 'antd';
import {
  DatabaseOutlined, TableOutlined, SearchOutlined,
  PlayCircleOutlined, ReloadOutlined,
} from '@ant-design/icons';
import { getDatabaseTables, getDatabaseStats, executeQuery } from '../services/api';

const { Text, Paragraph } = Typography;
const { TextArea } = Input;

const DatabasePage: React.FC = () => {
  const [tables, setTables] = useState<any[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [sqlInput, setSqlInput] = useState('');
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [selectedTable, setSelectedTable] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [tablesData, statsData] = await Promise.all([
        getDatabaseTables(),
        getDatabaseStats(),
      ]);
      setTables(tablesData);
      setStats(statsData);
    } catch (error) {
      message.error('加载数据库信息失败，请检查后端服务');
    }
    setLoading(false);
  };

  const handleQuery = async () => {
    if (!sqlInput.trim()) return;
    setQueryLoading(true);
    setQueryResult(null);
    try {
      const result = await executeQuery(sqlInput.trim());
      setQueryResult(result);
      if (!result.success) {
        message.error(result.error);
      }
    } catch (error: any) {
      message.error('查询失败: ' + (error.message || '未知错误'));
    }
    setQueryLoading(false);
  };

  const handleTablePreview = async (tableName: string) => {
    setSelectedTable(tableName);
    setSqlInput(`SELECT * FROM ${tableName} LIMIT 20;`);
    setQueryLoading(true);
    try {
      const result = await executeQuery(`SELECT * FROM ${tableName} LIMIT 20`);
      setQueryResult(result);
    } catch (error) {
      message.error('预览失败');
    }
    setQueryLoading(false);
  };

  return (
    <div style={{ padding: 24, height: 'calc(100vh - 56px)', overflow: 'auto' }}>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {Object.entries(stats).map(([table, count]) => (
          <Col key={table} xs={12} sm={8} md={6} lg={4}>
            <Card size="small" style={{ borderRadius: 8 }}>
              <Statistic
                title={<Text style={{ fontSize: 11 }}>{table}</Text>}
                value={count}
                prefix={<TableOutlined />}
                valueStyle={{ fontSize: 20 }}
              />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        {/* 表结构面板 */}
        <Col xs={24} lg={8}>
          <Card
            title={<><DatabaseOutlined /> 数据库表</>}
            size="small"
            style={{ borderRadius: 8, marginBottom: 16 }}
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadData}>刷新</Button>}
          >
            {loading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : (
              tables.map((t) => (
                <Card
                  key={t.name}
                  size="small"
                  style={{
                    marginBottom: 8, borderRadius: 8, cursor: 'pointer',
                    border: selectedTable === t.name ? '1px solid #1677ff' : undefined,
                  }}
                  onClick={() => handleTablePreview(t.name)}
                >
                  <Space>
                    <TableOutlined />
                    <Text strong>{t.name}</Text>
                    <Tag>{t.row_count} 行</Tag>
                  </Space>
                  <div style={{ marginTop: 4 }}>
                    {t.columns?.slice(0, 5).map((col: any) => (
                      <Tag key={col.name} style={{ fontSize: 11, marginBottom: 2 }}>
                        {col.name}
                      </Tag>
                    ))}
                    {t.columns?.length > 5 && (
                      <Tag style={{ fontSize: 11 }}>+{t.columns.length - 5}</Tag>
                    )}
                  </div>
                </Card>
              ))
            )}
          </Card>
        </Col>

        {/* SQL查询面板 */}
        <Col xs={24} lg={16}>
          <Card
            title={<><SearchOutlined /> SQL查询</>}
            size="small"
            style={{ borderRadius: 8, marginBottom: 16 }}
          >
            <TextArea
              value={sqlInput}
              onChange={(e) => setSqlInput(e.target.value)}
              placeholder="输入SQL查询语句，例如：SELECT * FROM income_sheet LIMIT 10;"
              autoSize={{ minRows: 3, maxRows: 8 }}
              style={{ fontFamily: 'monospace', marginBottom: 8 }}
            />
            <Space>
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={handleQuery}
                loading={queryLoading}
              >
                执行查询
              </Button>
              <Text type="secondary" style={{ fontSize: 12 }}>
                注意：仅支持SELECT查询语句
              </Text>
            </Space>
          </Card>

          {/* 查询结果 */}
          <Card
            title="查询结果"
            size="small"
            style={{ borderRadius: 8 }}
          >
            {queryLoading ? (
              <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
            ) : queryResult ? (
              queryResult.success ? (
                <>
                  <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                    共 {queryResult.row_count} 条结果
                  </Text>
                  <Table
                    dataSource={queryResult.data?.map((row: any, idx: number) => ({ ...row, _key: idx }))}
                    columns={queryResult.data?.[0] ? Object.keys(queryResult.data[0]).map((key) => ({
                      title: key,
                      dataIndex: key,
                      key,
                      ellipsis: true,
                      width: 150,
                    })) : []}
                    rowKey="_key"
                    size="small"
                    scroll={{ x: 'max-content' }}
                    pagination={{ pageSize: 10, showSizeChanger: true }}
                  />
                </>
              ) : (
                <Text type="danger">{queryResult.error}</Text>
              )
            ) : (
              <Empty description="暂无查询结果" />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DatabasePage;
