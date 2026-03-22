import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { Card, Table, Tag, Input, Select, Typography, Space } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getAllCompanies, AllCompaniesParams } from '../api/leadsApi';
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
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sortBy, setSortBy] = useState('final_score');
  const [sortOrder] = useState('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

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

      const res = await getAllCompanies(params);
      setCompanies(res.data.companies);
      setTotal(res.data.total);
    } catch {
      setCompanies([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Reset to page 1 when search/sort changes
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, sortBy]);

  // Unique ICP names for filtering display
  const icpNames = useMemo(() => {
    const names = new Set(companies.map(c => c.run_icp_name).filter(Boolean));
    return Array.from(names) as string[];
  }, [companies]);

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
        <p style={{ color: '#8c8c8c', margin: '4px 0 0' }}>
          Browse all qualified companies across all your pipeline runs
        </p>
      </div>

      {/* Summary */}
      <div className="summary-bar" style={{ marginBottom: 24 }}>
        <div className="summary-item">
          <div className="val">{total}</div>
          <div className="lbl">Total Companies</div>
        </div>
      </div>

      {/* Controls + Table */}
      <Card
        title="Companies"
        extra={
          <Space>
            <Input
              placeholder="Search company or website..."
              prefix={<SearchOutlined />}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ width: 260 }}
              allowClear
            />
            <Select value={sortBy} onChange={setSortBy} style={{ width: 180 }}>
              <Select.Option value="final_score">Sort by Final Score</Select.Option>
              <Select.Option value="budget_signal_score">Sort by Budget Score</Select.Option>
              <Select.Option value="urgency_signal_score">Sort by Urgency Score</Select.Option>
              <Select.Option value="deal_hotness_score">Sort by Deal Hotness</Select.Option>
              <Select.Option value="company_name">Sort by Company</Select.Option>
              <Select.Option value="created_at">Sort by Date</Select.Option>
            </Select>
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
                  state: { company: record, icp_name: record.run_icp_name ?? null },
                });
              }
            },
            style: { cursor: 'pointer' },
          })}
          size="small"
        />
      </Card>
    </div>
  );
};

export default AllLeadsPage;
