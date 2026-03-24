import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Alert, Card, Modal, Table, Tag, Input, Select, Typography, Space, Row, Col } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getAllCompanies, getAllCompanyFilters, AllCompaniesParams } from '../api/leadsApi';
import { getPipelineStatsByICP, ICPStat } from '../api/pipelineApi';
import { Company } from '../types';
import { usePageContext } from '../context/PageContextProvider';

const { Text } = Typography;

// ---------------------------------------------------------------------------
// Score display helpers
// ---------------------------------------------------------------------------

const getScoreColor = (score: number | null | undefined): string => {
  if (score == null) return '#d9d9d9';
  if (score >= 70) return '#52c41a';
  if (score >= 40) return '#faad14';
  return '#ff4d4f';
};

const formatCurrency = (val: number | null | undefined) => {
  if (!val) return '-';
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(1)}B`;
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(0)}M`;
  return `$${val.toLocaleString()}`;
};

const hotnessTierConfig: Record<string, { color: string; label: string }> = {
  hot: { color: '#f5222d', label: 'Hot' },
  warm: { color: '#fa8c16', label: 'Warm' },
  cool: { color: '#1890ff', label: 'Cool' },
  cold: { color: '#8c8c8c', label: 'Cold' },
};

// ---------------------------------------------------------------------------
// AllLeadsPage Component
// ---------------------------------------------------------------------------

const AllLeadsPage: React.FC = () => {
  const navigate = useNavigate();
  const { setCompanyId } = usePageContext();

  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [totalContacts, setTotalContacts] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState('final_score');
  const [sortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // Filters
  const [industryFilter, setIndustryFilter] = useState<string | undefined>(undefined);
  const [countryFilter, setCountryFilter] = useState<string | undefined>(undefined);
  const [availableIndustries, setAvailableIndustries] = useState<string[]>([]);
  const [availableCountries, setAvailableCountries] = useState<string[]>([]);

  // Load filter options once on mount
  useEffect(() => {
    getAllCompanyFilters()
      .then(res => {
        setAvailableIndustries(res.data.industries || []);
        setAvailableCountries(res.data.countries || []);
      })
      .catch(() => {});
  }, []);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 400);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: AllCompaniesParams = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (industryFilter) params.industry_filter = industryFilter;
      if (countryFilter) params.country_filter = countryFilter;

      const res = await getAllCompanies(params);
      setCompanies(res.data.companies);
      setTotal(res.data.total);
      setTotalContacts(res.data.total_contacts ?? 0);
      setError(null);
    } catch (err: any) {
      setCompanies([]);
      setTotal(0);
      setTotalContacts(0);
      const detail = err?.response?.data?.detail || err?.message || 'Failed to load companies';
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch, industryFilter, countryFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, sortBy, industryFilter, countryFilter]);

  // Unique ICP names for column filtering
  const icpNames = useMemo(() => {
    const names = new Set(companies.map(c => c.run_icp_name).filter(Boolean));
    return Array.from(names) as string[];
  }, [companies]);

  const activeFilterCount = [industryFilter, countryFilter].filter(Boolean).length;

  // Stats modal (breakdown by ICP)
  type TileKey = 'companies' | 'contacts';
  const [statsModalOpen, setStatsModalOpen] = useState(false);
  const [statsModalTile, setStatsModalTile] = useState<TileKey>('companies');
  const [icpStats, setIcpStats] = useState<ICPStat[]>([]);
  const [statsLoading, setStatsLoading] = useState(false);

  const openStatsModal = async (tile: TileKey) => {
    setStatsModalTile(tile);
    setStatsModalOpen(true);
    setStatsLoading(true);
    try {
      const res = await getPipelineStatsByICP();
      setIcpStats(Array.isArray(res.data) ? res.data : []);
    } catch {
      setIcpStats([]);
    } finally {
      setStatsLoading(false);
    }
  };

  const MODAL_TITLES: Record<TileKey, string> = {
    companies: 'Total Companies — by Search Criteria',
    contacts: 'Total Contacts — by Search Criteria',
  };

  const modalColumns = (tile: TileKey) => {
    const highlightStyle = { fontWeight: 700, fontSize: 15, color: 'var(--purple)' };
    if (tile === 'companies') {
      return [
        { title: 'Search Criteria', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
        { title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 120, render: (v: number) => <span style={highlightStyle}>{v}</span> },
        { title: 'Contacts', dataIndex: 'total_contacts', key: 'total_contacts', width: 110 },
        { title: 'Runs', dataIndex: 'run_count', key: 'run_count', width: 70 },
      ];
    }
    return [
      { title: 'Search Criteria', dataIndex: 'icp_name', key: 'icp_name', render: (v: string) => <span style={{ fontWeight: 600 }}>{v}</span> },
      { title: 'Contacts', dataIndex: 'total_contacts', key: 'total_contacts', width: 110, render: (v: number) => <span style={highlightStyle}>{v}</span> },
      { title: 'Companies', dataIndex: 'total_companies', key: 'total_companies', width: 120 },
      { title: 'Runs', dataIndex: 'run_count', key: 'run_count', width: 70 },
    ];
  };

  const statusColor: Record<string, string> = {
    pending: 'default', running: 'processing', completed: 'success', failed: 'error',
    awaiting_review: 'warning', cancelled: 'default',
  };

  const expandedRowRender = (stat: ICPStat) => {
    const runCols = [
      {
        title: 'Run', dataIndex: 'id', key: 'id', width: 130,
        render: (id: string, r: ICPStat['runs'][0]) => (
          <a onClick={() => { setStatsModalOpen(false); navigate(`/leads/${id}`); }}
            style={{ color: 'var(--purple)', cursor: 'pointer' }}>
            {r.status === 'completed' ? `${id.substring(0, 8)}…` : id.substring(0, 8)}
          </a>
        ),
      },
      { title: 'Status', dataIndex: 'status', key: 'status', width: 110, render: (s: string) => <Tag color={statusColor[s] || 'default'}>{s.toUpperCase()}</Tag> },
      { title: 'Companies', dataIndex: 'companies_found', key: 'companies_found', width: 100 },
      { title: 'Contacts', dataIndex: 'contacts_found', key: 'contacts_found', width: 100 },
      { title: 'Started', dataIndex: 'started_at', key: 'started_at', render: (d: string | null) => d ? new Date(d).toLocaleString() : '—' },
    ];
    return <Table columns={runCols} dataSource={Array.isArray(stat.runs) ? stat.runs : []} rowKey="id" pagination={false} size="small" />;
  };

  const columns = [
    {
      title: '#',
      key: 'serial',
      width: 55,
      render: (_: unknown, __: Company, index: number) => (
        <Text type="secondary" style={{ fontSize: 12 }}>{(page - 1) * pageSize + index + 1}</Text>
      ),
    },
    {
      title: 'Company',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string) => (
        <Text style={{ fontWeight: 600, fontSize: 13 }}>{name}</Text>
      ),
    },
    {
      title: 'Industry',
      dataIndex: 'industry',
      key: 'industry',
      width: 130,
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Country',
      dataIndex: 'country',
      key: 'country',
      width: 90,
      render: (v: string | null) => v || '-',
    },
    {
      title: 'Revenue',
      dataIndex: 'revenue_estimate',
      key: 'revenue',
      width: 100,
      render: (v: number | null) => formatCurrency(v),
    },
    {
      title: 'Final Score',
      dataIndex: 'final_score',
      key: 'final_score',
      width: 110,
      render: (score: number | null | undefined) => {
        if (score == null) return <Text type="secondary">-</Text>;
        return (
          <span style={{ color: getScoreColor(score), fontWeight: 700, fontSize: 15 }}>
            {Math.round(score)}
          </span>
        );
      },
    },
    {
      title: 'Budget',
      dataIndex: 'budget_signal_score',
      key: 'budget',
      width: 80,
      render: (score: number | null | undefined) => {
        if (score == null) return <Text type="secondary">-</Text>;
        return <span style={{ color: getScoreColor(score), fontWeight: 600, fontSize: 13 }}>{Math.round(score)}</span>;
      },
    },
    {
      title: 'Urgency',
      dataIndex: 'urgency_signal_score',
      key: 'urgency',
      width: 80,
      render: (score: number | null | undefined) => {
        if (score == null) return <Text type="secondary">-</Text>;
        return <span style={{ color: getScoreColor(score), fontWeight: 600, fontSize: 13 }}>{Math.round(score)}</span>;
      },
    },
    {
      title: 'Hotness',
      dataIndex: 'deal_hotness_tier',
      key: 'hotness',
      width: 90,
      render: (tier: string | null | undefined) => {
        if (!tier) return <Text type="secondary">-</Text>;
        const cfg = hotnessTierConfig[tier] || { color: '#8c8c8c', label: tier };
        return <Tag color={cfg.color} style={{ margin: 0 }}>{cfg.label}</Tag>;
      },
    },
    {
      title: 'Contacts',
      key: 'contacts',
      width: 85,
      render: (_: unknown, record: Company) => {
        const count = record.contacts?.length ?? 0;
        return count > 0
          ? <Tag color="blue" style={{ fontSize: 12 }}>{count}</Tag>
          : <Text type="secondary">--</Text>;
      },
    },
    {
      title: 'Search Criteria',
      dataIndex: 'run_icp_name',
      key: 'icp',
      width: 160,
      filters: icpNames.map(n => ({ text: n, value: n })),
      onFilter: (value: unknown, record: Company) => record.run_icp_name === value,
      render: (v: string | null) => v ? <Tag color="purple" style={{ fontSize: 12 }}>{v}</Tag> : <Text type="secondary">-</Text>,
    },
  ];

  return (
    <div style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div className="section-label">Lead Management</div>
        <h1 className="page-title">All Leads</h1>
      </div>

      {/* Summary */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={12} md={8}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('companies')}>
            <div className="metric-icon">🏢</div>
            <div className="label">Total Companies</div>
            <div className="value">{total}</div>
          </div>
        </Col>
        <Col xs={12} sm={12} md={8}>
          <div className="metric-tile metric-tile-clickable" onClick={() => openStatsModal('contacts')}>
            <div className="metric-icon">👥</div>
            <div className="label">Total Contacts</div>
            <div className="value">{totalContacts}</div>
          </div>
        </Col>
      </Row>

      {/* Error banner */}
      {error && (
        <Alert
          type="error"
          message="Failed to load leads"
          description={error}
          showIcon
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setError(null)}
        />
      )}

      {/* Controls + Table */}
      <Card
        title="Companies"
        extra={
          <Space wrap>
            <Input
              placeholder="Search company or website..."
              prefix={<SearchOutlined />}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: 220 }}
              allowClear
            />
            <Select
              placeholder="Industry"
              value={industryFilter}
              onChange={setIndustryFilter}
              allowClear
              showSearch
              style={{ width: 160 }}
              options={availableIndustries.map(i => ({ label: i, value: i }))}
            />
            <Select
              placeholder="Country"
              value={countryFilter}
              onChange={setCountryFilter}
              allowClear
              showSearch
              style={{ width: 140 }}
              options={availableCountries.map(c => ({ label: c, value: c }))}
            />
            <Select value={sortBy} onChange={setSortBy} style={{ width: 180 }}>
              <Select.Option value="final_score">Sort by Final Score</Select.Option>
              <Select.Option value="budget_signal_score">Sort by Budget Score</Select.Option>
              <Select.Option value="urgency_signal_score">Sort by Urgency Score</Select.Option>
              <Select.Option value="deal_hotness_score">Sort by Deal Hotness</Select.Option>
              <Select.Option value="company_name">Sort by Company</Select.Option>
              <Select.Option value="created_at">Sort by Date</Select.Option>
            </Select>
            {activeFilterCount > 0 && (
              <a
                onClick={() => { setIndustryFilter(undefined); setCountryFilter(undefined); }}
                style={{ fontSize: 13, color: '#5C2D8F', whiteSpace: 'nowrap' }}
              >
                Clear filters ({activeFilterCount})
              </a>
            )}
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={companies}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
            showSizeChanger: true,
            showTotal: (t) => `${t} companies`,
          }}
          scroll={{ x: 1200 }}
          onRow={(record) => ({
            onClick: () => {
              if (record.pipeline_run_id) {
                setCompanyId(record.id);
                navigate(`/leads/${record.pipeline_run_id}/company/${record.id}`, {
                  state: { company: record, icp_name: record.run_icp_name ?? null, from: '/all-leads' },
                });
              }
            },
            style: { cursor: 'pointer' },
          })}
          size="small"
        />
      </Card>
      {/* Stats Breakdown Modal */}
      <Modal
        title={MODAL_TITLES[statsModalTile]}
        open={statsModalOpen}
        onCancel={() => setStatsModalOpen(false)}
        footer={null}
        width={760}
      >
        <Table
          columns={modalColumns(statsModalTile) as any}
          dataSource={icpStats}
          rowKey="icp_id"
          loading={statsLoading}
          expandable={{ expandedRowRender }}
          pagination={false}
          size="middle"
          locale={{ emptyText: 'No data found' }}
        />
      </Modal>
    </div>
  );
};

export default AllLeadsPage;
