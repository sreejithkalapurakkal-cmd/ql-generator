import React, { useEffect, useState, useMemo } from 'react';
import { Card, Row, Col, Table, Tag, Switch, Button, Input, Tooltip, Popconfirm, message, Badge, Select, Alert, Typography } from 'antd';
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
import { getToolAttribution, getToolEffectivenessAggregate } from '../api/leadsApi';
import { listPipelineRuns } from '../api/pipelineApi';
import { ToolRegistryItem, ToolMetricsSummary, ToolAttribution, PipelineRun, ToolEffectivenessAggregate } from '../types';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend, ResponsiveContainer, Tooltip as RechartsTooltip,
} from 'recharts';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Score/efficiency helpers
// ---------------------------------------------------------------------------

const getScoreColor = (score: number | null | undefined): string => {
  if (score == null) return '#d9d9d9';
  if (score >= 70) return '#52c41a';
  if (score >= 40) return '#faad14';
  return '#ff4d4f';
};

const getEfficiencyColor = (eff: number | null): string => {
  if (eff == null) return '#d9d9d9';
  if (eff >= 70) return '#52c41a';
  if (eff >= 40) return '#faad14';
  return '#ff4d4f';
};

// ---------------------------------------------------------------------------
// Per-Run Tool Attribution Sub-component
// ---------------------------------------------------------------------------

const PerRunAttribution: React.FC<{ runId: string }> = ({ runId }) => {
  const [data, setData] = useState<ToolAttribution[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getToolAttribution(runId)
      .then(res => setData(res.data.tools || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [runId]);

  const discoveryTools = useMemo(
    () => data.filter(t => t.companies_discovered > 0).sort((a, b) => b.companies_discovered - a.companies_discovered),
    [data],
  );

  const enrichmentTools = useMemo(
    () => data.filter(t => t.companies_discovered === 0 && t.total_calls > 0),
    [data],
  );

  const columns = [
    {
      title: 'Tool',
      dataIndex: 'tool_name',
      key: 'tool_name',
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: 'Discovered',
      dataIndex: 'companies_discovered',
      key: 'discovered',
      sorter: (a: ToolAttribution, b: ToolAttribution) => a.companies_discovered - b.companies_discovered,
    },
    {
      title: 'Qualified',
      dataIndex: 'companies_qualified',
      key: 'qualified',
      render: (v: number) => <span style={{ color: '#52c41a', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: 'Disqualified',
      dataIndex: 'companies_disqualified',
      key: 'disqualified',
      render: (v: number) => <span style={{ color: '#ff4d4f' }}>{v}</span>,
    },
    {
      title: 'High Fit',
      dataIndex: 'high_fit_count',
      key: 'high_fit',
      render: (v: number) => <Tag color="green">{v}</Tag>,
    },
    {
      title: 'Medium Fit',
      dataIndex: 'medium_fit_count',
      key: 'medium_fit',
      render: (v: number) => <Tag color="gold">{v}</Tag>,
    },
    {
      title: 'Low Fit',
      dataIndex: 'low_fit_count',
      key: 'low_fit',
      render: (v: number) => <Tag color="red">{v}</Tag>,
    },
    {
      title: 'Efficiency',
      dataIndex: 'efficiency',
      key: 'efficiency',
      sorter: (a: ToolAttribution, b: ToolAttribution) => (a.efficiency ?? 0) - (b.efficiency ?? 0),
      render: (v: number | null) => v != null ? (
        <Tag color={getEfficiencyColor(v) === '#52c41a' ? 'green' : getEfficiencyColor(v) === '#faad14' ? 'gold' : 'red'}>
          {v}%
        </Tag>
      ) : <Text type="secondary">-</Text>,
    },
    {
      title: 'Avg Score',
      dataIndex: 'avg_icp_match_score',
      key: 'avg_score',
      sorter: (a: ToolAttribution, b: ToolAttribution) => (a.avg_icp_match_score ?? 0) - (b.avg_icp_match_score ?? 0),
      render: (v: number | null) => v != null ? (
        <span style={{ color: getScoreColor(v), fontWeight: 600 }}>{v}</span>
      ) : <Text type="secondary">-</Text>,
    },
    {
      title: 'Calls',
      dataIndex: 'total_calls',
      key: 'calls',
    },
    {
      title: 'Success Rate',
      dataIndex: 'success_rate',
      key: 'success_rate',
      render: (v: number | null) => v != null ? `${v}%` : <Text type="secondary">-</Text>,
    },
    {
      title: 'Top Companies',
      dataIndex: 'sample_companies',
      key: 'samples',
      width: 200,
      render: (v: string[]) => v && v.length > 0 ? (
        <Tooltip title={v.join(', ')}>
          <Text ellipsis style={{ maxWidth: 180 }}>{v.join(', ')}</Text>
        </Tooltip>
      ) : <Text type="secondary">-</Text>,
    },
  ];

  const enrichmentColumns = [
    { title: 'Tool', dataIndex: 'tool_name', key: 'tool_name', render: (v: string) => <Text strong>{v}</Text> },
    { title: 'Total Calls', dataIndex: 'total_calls', key: 'calls' },
    {
      title: 'Successful',
      dataIndex: 'successful_calls',
      key: 'success',
      render: (v: number) => <span style={{ color: '#52c41a' }}>{v}</span>,
    },
    {
      title: 'Failed',
      dataIndex: 'failed_calls',
      key: 'failed',
      render: (v: number) => <span style={{ color: v > 0 ? '#ff4d4f' : undefined }}>{v}</span>,
    },
    {
      title: 'Success Rate',
      dataIndex: 'success_rate',
      key: 'success_rate',
      render: (v: number | null) => v != null ? `${v}%` : '-',
    },
  ];

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>Loading tool attribution data...</div>;
  }

  if (discoveryTools.length === 0 && enrichmentTools.length === 0) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>No tool attribution data available for this run.</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {discoveryTools.length > 0 && (
        <Card title="Company Discovery by Tool" size="small">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={discoveryTools} margin={{ bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="tool_name" angle={-35} textAnchor="end" height={80} interval={0} tick={{ fontSize: 11 }} />
              <YAxis />
              <RechartsTooltip />
              <Legend />
              <Bar dataKey="high_fit_count" stackId="a" fill="#52c41a" name="High Fit (70+)" />
              <Bar dataKey="medium_fit_count" stackId="a" fill="#faad14" name="Medium Fit (40-69)" />
              <Bar dataKey="low_fit_count" stackId="a" fill="#ff4d4f" name="Low Fit (<40)" />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {discoveryTools.length > 0 && (
        <Card title="Discovery Tool Breakdown" size="small">
          <Table
            columns={columns}
            dataSource={discoveryTools}
            rowKey="tool_name"
            pagination={false}
            size="small"
            scroll={{ x: 1200 }}
          />
        </Card>
      )}

      {enrichmentTools.length > 0 && (
        <Card title="Enrichment & Support Tools (no direct company attribution)" size="small">
          <Table
            columns={enrichmentColumns}
            dataSource={enrichmentTools}
            rowKey="tool_name"
            pagination={false}
            size="small"
          />
        </Card>
      )}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Main ToolsPage Component
// ---------------------------------------------------------------------------

const ToolsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'registry' | 'effectiveness'>('registry');

  // --- Registry tab state ---
  const [tools, setTools] = useState<ToolRegistryItem[]>([]);
  const [summary, setSummary] = useState<ToolMetricsSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [healthCheckLoading, setHealthCheckLoading] = useState(false);
  const [checkingToolId, setCheckingToolId] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // --- Effectiveness tab state ---
  const [pipelineRuns, setPipelineRuns] = useState<PipelineRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [aggregateData, setAggregateData] = useState<ToolEffectivenessAggregate[]>([]);
  const [aggregateLoading, setAggregateLoading] = useState(false);

  // --- Registry data ---
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

  // --- Load pipeline runs + aggregates when switching to effectiveness tab ---
  useEffect(() => {
    if (activeTab === 'effectiveness') {
      listPipelineRuns()
        .then(res => {
          const completed = (Array.isArray(res.data) ? res.data : []).filter(
            (r: PipelineRun) => r.status === 'completed',
          );
          setPipelineRuns(completed);
          if (completed.length > 0 && !selectedRunId) {
            setSelectedRunId(completed[0].id);
          }
        })
        .catch(() => setPipelineRuns([]));

      setAggregateLoading(true);
      getToolEffectivenessAggregate()
        .then(res => setAggregateData(res.data.tools || []))
        .catch(() => setAggregateData([]))
        .finally(() => setAggregateLoading(false));
    }
  }, [activeTab]);

  // --- Registry handlers ---
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

  // --- Insights derived from aggregate data ---
  const insights = useMemo(() => {
    const results: { type: 'success' | 'warning' | 'error'; message: string }[] = [];
    for (const tool of aggregateData) {
      if (tool.pass_rate >= 70 && tool.total_runs_used >= 3) {
        results.push({
          type: 'success',
          message: `${tool.tool_name} has ${tool.pass_rate}% pass rate${tool.industry ? ` for ${tool.industry}` : ''} across ${tool.total_runs_used} runs — high performer`,
        });
      }
      if (tool.pass_rate < 20 && tool.total_companies_sourced >= 5) {
        results.push({
          type: 'error',
          message: `${tool.tool_name} has only ${tool.pass_rate}% pass rate${tool.industry ? ` for ${tool.industry}` : ''} with ${tool.total_companies_sourced} companies sourced — consider disabling`,
        });
      }
      if (tool.pass_rate >= 40 && tool.pass_rate < 70 && tool.total_runs_used >= 2) {
        results.push({
          type: 'warning',
          message: `${tool.tool_name} has moderate ${tool.pass_rate}% pass rate${tool.industry ? ` for ${tool.industry}` : ''} — monitor performance`,
        });
      }
    }
    return results;
  }, [aggregateData]);

  // --- Registry filtered data ---
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

  const registryColumns = [
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
      title: 'Priority',
      key: 'priority',
      width: 80,
      align: 'center' as const,
      render: (_: unknown, record: ToolRegistryItem) => {
        const p = record.priority ?? 50;
        const color = p >= 70 ? '#52c41a' : p >= 40 ? '#faad14' : '#ff4d4f';
        return (
          <Tooltip title={record.auto_disabled ? 'Auto-disabled due to low effectiveness' : `Priority: ${p}/100`}>
            <span style={{ fontWeight: 600, color }}>
              {p}
              {record.auto_disabled && <WarningFilled style={{ color: '#ff4d4f', marginLeft: 4, fontSize: 12 }} />}
            </span>
          </Tooltip>
        );
      },
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

  // --- Cross-run aggregate table columns ---
  const aggregateColumns = [
    { title: 'Tool', dataIndex: 'tool_name', key: 'tool_name', render: (v: string) => <Text strong>{v}</Text> },
    { title: 'Industry', dataIndex: 'industry', key: 'industry', render: (v: string) => v || <Text type="secondary">-</Text> },
    { title: 'Country', dataIndex: 'country', key: 'country', render: (v: string) => v || <Text type="secondary">-</Text> },
    { title: 'Sourced', dataIndex: 'total_companies_sourced', key: 'sourced' },
    { title: 'Passed', dataIndex: 'companies_passed_stage2', key: 'passed', render: (v: number) => <span style={{ color: '#52c41a', fontWeight: 600 }}>{v}</span> },
    {
      title: 'Pass Rate',
      dataIndex: 'pass_rate',
      key: 'pass_rate',
      sorter: (a: ToolEffectivenessAggregate, b: ToolEffectivenessAggregate) => a.pass_rate - b.pass_rate,
      render: (v: number) => {
        const color = v >= 70 ? '#52c41a' : v >= 40 ? '#faad14' : '#ff4d4f';
        return <span style={{ color, fontWeight: 600 }}>{v}%</span>;
      },
    },
    {
      title: 'Avg Score',
      dataIndex: 'avg_score',
      key: 'avg_score',
      render: (v: number) => <span style={{ color: getScoreColor(v), fontWeight: 600 }}>{v}</span>,
    },
    {
      title: 'Effectiveness',
      dataIndex: 'effectiveness_score',
      key: 'effectiveness',
      sorter: (a: ToolEffectivenessAggregate, b: ToolEffectivenessAggregate) => a.effectiveness_score - b.effectiveness_score,
      render: (v: number) => <Tag color={v >= 50 ? 'green' : v >= 20 ? 'gold' : 'red'}>{v.toFixed(1)}</Tag>,
    },
    { title: 'Runs', dataIndex: 'total_runs_used', key: 'runs' },
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
            Monitor health, usage metrics, effectiveness, and manage external API tools
          </p>
        </div>
        {activeTab === 'registry' && (
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={healthCheckLoading}
            onClick={handleCheckAllHealth}
            size="large"
          >
            Check All Health
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 20 }}>
        <div
          className={`tab ${activeTab === 'registry' ? 'active' : ''}`}
          onClick={() => setActiveTab('registry')}
        >
          Tool Registry
        </div>
        <div
          className={`tab ${activeTab === 'effectiveness' ? 'active' : ''}`}
          onClick={() => setActiveTab('effectiveness')}
        >
          Tool Effectiveness
        </div>
      </div>

      {/* Tab: Registry */}
      {activeTab === 'registry' && (
        <>
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
              columns={registryColumns}
              rowKey="id"
              loading={loading}
              pagination={false}
              size="middle"
              scroll={{ x: 1200 }}
              rowClassName={(record) => !record.is_enabled ? 'tool-row-disabled' : ''}
            />
          </Card>
        </>
      )}

      {/* Tab: Effectiveness */}
      {activeTab === 'effectiveness' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Insights Panel */}
          {insights.length > 0 && (
            <Card title="Insights & Recommendations" size="small">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {insights.map((insight, i) => (
                  <Alert
                    key={i}
                    type={insight.type}
                    message={insight.message}
                    showIcon
                    style={{ borderRadius: 8 }}
                  />
                ))}
              </div>
            </Card>
          )}

          {/* Cross-Run Aggregates */}
          <Card title="Cross-Run Tool Effectiveness" size="small">
            {aggregateLoading ? (
              <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>Loading aggregate data...</div>
            ) : aggregateData.length > 0 ? (
              <Table
                columns={aggregateColumns}
                dataSource={aggregateData}
                rowKey={(r) => `${r.tool_name}-${r.industry}-${r.country}`}
                pagination={false}
                size="small"
                scroll={{ x: 900 }}
              />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
                No cross-run effectiveness data available yet. Complete pipeline runs to build intelligence.
              </div>
            )}
          </Card>

          {/* Per-Run Attribution */}
          <Card
            title="Per-Run Tool Attribution"
            size="small"
            extra={
              <Select
                placeholder="Select a pipeline run"
                value={selectedRunId}
                onChange={(v) => setSelectedRunId(v)}
                style={{ width: 360 }}
                allowClear
              >
                {pipelineRuns.map(run => (
                  <Select.Option key={run.id} value={run.id}>
                    {run.icp_name || 'Unnamed'} — {new Date(run.started_at || run.created_at).toLocaleDateString()} ({run.companies_found} companies)
                  </Select.Option>
                ))}
              </Select>
            }
          >
            {selectedRunId ? (
              <PerRunAttribution runId={selectedRunId} />
            ) : (
              <div style={{ textAlign: 'center', padding: 40, color: '#8c8c8c' }}>
                Select a pipeline run to view tool attribution details.
              </div>
            )}
          </Card>
        </div>
      )}

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
