import React, { useEffect, useState, useMemo } from 'react';
import { Card, Row, Col, Table, Tag, Switch, Button, Input, Tooltip, Popconfirm, message, Badge } from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  WarningFilled,
  QuestionCircleFilled,
  DeleteOutlined,
  ApiOutlined,
} from '@ant-design/icons';
import { listTools, getToolsSummary, updateTool, checkToolHealth, checkAllToolsHealth, deleteTool } from '../api/toolsApi';
import { ToolRegistryItem, ToolMetricsSummary } from '../types';

const ToolsPage: React.FC = () => {
  const [tools, setTools] = useState<ToolRegistryItem[]>([]);
  const [summary, setSummary] = useState<ToolMetricsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [checkingToolId, setCheckingToolId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const refreshData = async () => {
    setLoading(true);
    try {
      const [toolsRes, summaryRes] = await Promise.all([listTools(), getToolsSummary()]);
      setTools(toolsRes.data);
      setSummary(summaryRes.data);
    } catch {
      message.error('Failed to load tools data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshData();
  }, []);

  const handleToggleEnabled = async (tool: ToolRegistryItem, enabled: boolean) => {
    try {
      await updateTool(tool.id, { is_enabled: enabled });
      message.success(`${tool.display_name} ${enabled ? 'enabled' : 'disabled'}`);
      refreshData();
    } catch {
      message.error('Failed to update tool');
    }
  };

  const handleCheckHealth = async (toolId: string) => {
    setCheckingToolId(toolId);
    try {
      const res = await checkToolHealth(toolId);
      message.success(`${res.data.tool_name}: ${res.data.status}`);
      refreshData();
    } catch {
      message.error('Health check failed');
    } finally {
      setCheckingToolId(null);
    }
  };

  const handleCheckAllHealth = async () => {
    setHealthCheckLoading(true);
    try {
      const res = await checkAllToolsHealth();
      const healthy = res.data.filter(r => r.status === 'healthy').length;
      message.success(`Health check complete: ${healthy}/${res.data.length} healthy`);
      refreshData();
    } catch {
      message.error('Health check failed');
    } finally {
      setHealthCheckLoading(false);
    }
  };

  const handleDelete = async (toolId: string) => {
    try {
      await deleteTool(toolId);
      message.success('Tool removed from registry');
      refreshData();
    } catch {
      message.error('Failed to delete tool');
    }
  };

  const filteredTools = useMemo(() => {
    let result = tools;
    if (categoryFilter !== 'all') {
      result = result.filter(t => t.category === categoryFilter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        t => t.display_name.toLowerCase().includes(q) || t.tool_name.toLowerCase().includes(q)
      );
    }
    return result;
  }, [tools, categoryFilter, searchQuery]);

  const healthIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleFilled style={{ color: '#52c41a', fontSize: 16 }} />;
      case 'unhealthy':
        return <CloseCircleFilled style={{ color: '#ff4d4f', fontSize: 16 }} />;
      case 'no_api_key':
        return <WarningFilled style={{ color: '#faad14', fontSize: 16 }} />;
      default:
        return <QuestionCircleFilled style={{ color: '#d9d9d9', fontSize: 16 }} />;
    }
  };

  const categoryColor: Record<string, string> = {
    pipeline: 'blue',
    research: 'purple',
    copilot_db: 'cyan',
  };

  const categoryLabel: Record<string, string> = {
    pipeline: 'Pipeline',
    research: 'Research',
    copilot_db: 'Co-pilot DB',
  };

  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  };

  const columns = [
    {
      title: 'Tool',
      key: 'tool',
      width: 260,
      render: (_: unknown, record: ToolRegistryItem) => (
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{record.display_name}</div>
          <div style={{ color: '#8c8c8c', fontSize: 12, fontFamily: 'monospace' }}>{record.tool_name}</div>
        </div>
      ),
    },
    {
      title: 'Category',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (cat: string) => (
        <Tag color={categoryColor[cat] || 'default'}>{categoryLabel[cat] || cat}</Tag>
      ),
    },
    {
      title: 'Health',
      key: 'health',
      width: 120,
      render: (_: unknown, record: ToolRegistryItem) => (
        <Tooltip title={record.last_health_message || record.health_status}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {healthIcon(record.health_status)}
            <span style={{ fontSize: 13 }}>{record.health_status.replace('_', ' ')}</span>
          </span>
        </Tooltip>
      ),
    },
    {
      title: 'API Key',
      key: 'api_key',
      width: 80,
      align: 'center' as const,
      render: (_: unknown, record: ToolRegistryItem) =>
        record.requires_api_key ? (
          record.health_status !== 'no_api_key' ? (
            <CheckCircleFilled style={{ color: '#52c41a' }} />
          ) : (
            <CloseCircleFilled style={{ color: '#ff4d4f' }} />
          )
        ) : (
          <span style={{ color: '#d9d9d9' }}>-</span>
        ),
    },
    {
      title: 'Success Rate',
      key: 'success_rate',
      width: 110,
      align: 'center' as const,
      render: (_: unknown, record: ToolRegistryItem) => {
        if (record.total_calls === 0) return <span style={{ color: '#d9d9d9' }}>-</span>;
        const rate = record.success_rate ?? 0;
        const color = rate >= 80 ? '#52c41a' : rate >= 50 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 600 }}>{rate.toFixed(1)}%</span>;
      },
    },
    {
      title: 'Calls',
      dataIndex: 'total_calls',
      key: 'total_calls',
      width: 80,
      align: 'center' as const,
      render: (val: number) => val || <span style={{ color: '#d9d9d9' }}>0</span>,
    },
    {
      title: 'Rate Limit',
      dataIndex: 'rate_limit_info',
      key: 'rate_limit_info',
      width: 160,
      render: (val: string | null) =>
        val ? (
          <Tooltip title={val}>
            <span style={{ fontSize: 12, color: '#595959' }}>{val}</span>
          </Tooltip>
        ) : (
          <span style={{ color: '#d9d9d9' }}>-</span>
        ),
    },
    {
      title: 'Last Used',
      key: 'last_used',
      width: 100,
      render: (_: unknown, record: ToolRegistryItem) => (
        <span style={{ color: '#8c8c8c', fontSize: 13 }}>{formatRelativeTime(record.last_used_at)}</span>
      ),
    },
    {
      title: 'Last Error',
      key: 'last_error',
      width: 180,
      ellipsis: true,
      render: (_: unknown, record: ToolRegistryItem) =>
        record.last_error ? (
          <Tooltip title={record.last_error}>
            <span style={{ color: '#ff4d4f', fontSize: 12 }}>{record.last_error}</span>
          </Tooltip>
        ) : (
          <span style={{ color: '#d9d9d9' }}>-</span>
        ),
    },
    {
      title: 'Enabled',
      key: 'enabled',
      width: 80,
      align: 'center' as const,
      render: (_: unknown, record: ToolRegistryItem) => (
        <Switch
          checked={record.is_enabled}
          onChange={(checked) => handleToggleEnabled(record, checked)}
          disabled={record.category === 'copilot_db'}
          size="small"
        />
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_: unknown, record: ToolRegistryItem) => (
        <span style={{ display: 'flex', gap: 4 }}>
          <Tooltip title="Check Health">
            <Button
              type="text"
              size="small"
              icon={<ReloadOutlined spin={checkingToolId === record.id} />}
              onClick={() => handleCheckHealth(record.id)}
              loading={checkingToolId === record.id}
            />
          </Tooltip>
          <Popconfirm
            title="Remove this tool from the registry?"
            onConfirm={() => handleDelete(record.id)}
            okText="Delete"
            cancelText="Cancel"
          >
            <Tooltip title="Delete">
              <Button type="text" size="small" icon={<DeleteOutlined />} danger />
            </Tooltip>
          </Popconfirm>
        </span>
      ),
    },
  ];

  const tileStyle: React.CSSProperties = {
    textAlign: 'center',
    padding: '20px 16px',
    borderRadius: 12,
    background: '#fff',
    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
  };

  const filterButtons = [
    { key: 'all', label: 'All' },
    { key: 'pipeline', label: 'Pipeline' },
    { key: 'research', label: 'Research' },
    { key: 'copilot_db', label: 'Co-pilot DB' },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 28, fontWeight: 700 }}>
            <ApiOutlined style={{ marginRight: 10 }} />
            Tools Monitor
          </h1>
          <p style={{ margin: '4px 0 0', color: '#8c8c8c' }}>
            Monitor health, usage metrics, and manage external API tools
          </p>
        </div>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          loading={healthCheckLoading}
          onClick={handleCheckAllHealth}
          size="large"
        >
          Check All Health
        </Button>
      </div>

      {/* Metric Tiles */}
      {summary && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#5C2D8F' }}>{summary.total_tools}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>Total Tools</div>
            </Card>
          </Col>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#52c41a' }}>{summary.healthy_count}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>Healthy</div>
            </Card>
          </Col>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#ff4d4f' }}>{summary.unhealthy_count}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>Unhealthy</div>
            </Card>
          </Col>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#faad14' }}>{summary.no_api_key_count}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>No API Key</div>
            </Card>
          </Col>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#8c8c8c' }}>{summary.disabled_count}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>Disabled</div>
            </Card>
          </Col>
          <Col span={4}>
            <Card style={tileStyle} variant="borderless">
              <div style={{ fontSize: 32, fontWeight: 700, color: '#bfbfbf' }}>{summary.unknown_count}</div>
              <div style={{ color: '#8c8c8c', fontSize: 13, marginTop: 4 }}>Unknown</div>
            </Card>
          </Col>
        </Row>
      )}

      {/* Filter Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8 }}>
          {filterButtons.map(fb => (
            <Button
              key={fb.key}
              type={categoryFilter === fb.key ? 'primary' : 'default'}
              size="small"
              onClick={() => setCategoryFilter(fb.key)}
            >
              {fb.label}
              {fb.key !== 'all' && (
                <Badge
                  count={tools.filter(t => t.category === fb.key).length}
                  style={{ marginLeft: 6, backgroundColor: categoryFilter === fb.key ? '#fff' : '#5C2D8F', color: categoryFilter === fb.key ? '#5C2D8F' : '#fff', fontSize: 11 }}
                  size="small"
                />
              )}
            </Button>
          ))}
        </div>
        <Input
          placeholder="Search tools..."
          prefix={<SearchOutlined />}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          style={{ width: 240 }}
          allowClear
        />
      </div>

      {/* Tools Table */}
      <Card variant="borderless" style={{ borderRadius: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
        <Table
          dataSource={filteredTools}
          columns={columns}
          rowKey="id"
          loading={loading}
          pagination={false}
          size="middle"
          scroll={{ x: 1200 }}
          rowClassName={(record) => !record.is_enabled ? 'tool-row-disabled' : ''}
        />
      </Card>

      <style>{`
        .tool-row-disabled {
          opacity: 0.5;
        }
        .tool-row-disabled td {
          background: #fafafa !important;
        }
      `}</style>
    </div>
  );
};

export default ToolsPage;
