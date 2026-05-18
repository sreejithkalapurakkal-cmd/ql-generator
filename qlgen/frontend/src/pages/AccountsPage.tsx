import React, { useEffect, useState, useCallback } from 'react';
import { Input, Select, Spin, Tooltip } from 'antd';
import { SearchOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Badge, EmptyState } from '../components/ui';
import client from '../api/client';

interface Account {
  id: string;
  name: string | null;
  domain: string | null;
  industry: string | null;
  country: string | null;
  employee_count: number | null;
  status: string;
  signal_count: number;
  has_brief: boolean;
  open_draft_count: number;
  tags: string[];
}

const STATUS_COLORS: Record<string, string> = {
  monitored: '#52c41a',
  paused: '#faad14',
  archived: '#8c8c8c',
};

const AccountsPage: React.FC = () => {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [industry, setIndustry] = useState<string | undefined>();
  const [sortBy, setSortBy] = useState('signal_count');

  const fetchAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { sort_by: sortBy, limit: '100' };
      if (search) params.search = search;
      if (industry) params.industry = industry;
      const res = await client.get<{ accounts: Account[]; total: number }>('/accounts/', { params });
      setAccounts(res.data.accounts || []);
      setTotal(res.data.total || 0);
    } catch {
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, [search, industry, sortBy]);

  useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

  const initials = (name: string | null) => {
    if (!name) return '?';
    return name.split(/[\s.]+/).slice(0, 2).map(w => w[0]?.toUpperCase() || '').join('');
  };

  return (
    <div className="px-10 py-8 max-w-[1400px] mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {total} companies across your tracking lists
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 mb-4">
        <div className="flex items-center gap-3 flex-wrap">
          <Input
            prefix={<SearchOutlined className="text-gray-400" />}
            placeholder="Search by name or domain..."
            allowClear
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 280 }}
            size="small"
          />
          <Select
            placeholder="All industries"
            value={industry}
            onChange={setIndustry}
            allowClear
            size="small"
            style={{ width: 180 }}
            options={[
              { value: 'Healthcare', label: 'Healthcare' },
              { value: 'Technology', label: 'Technology' },
              { value: 'Financial Services', label: 'Financial Services' },
              { value: 'Manufacturing', label: 'Manufacturing' },
              { value: 'Retail', label: 'Retail' },
            ]}
          />
          <Select
            value={sortBy}
            onChange={setSortBy}
            size="small"
            style={{ width: 150 }}
            options={[
              { value: 'signal_count', label: 'Sort: Signals' },
              { value: 'name', label: 'Sort: Name' },
              { value: 'industry', label: 'Sort: Industry' },
            ]}
          />
          <span className="ml-auto text-xs text-gray-400">{total} accounts</span>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20"><Spin size="large" /></div>
      ) : accounts.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg">
          <EmptyState
            icon={<SearchOutlined />}
            title="No accounts found"
            description="Add companies to tracking lists to see them here."
            className="py-16"
          />
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          {/* Header row */}
          <div className="grid grid-cols-[2fr_1fr_1fr_80px_80px_80px_100px] gap-3 px-5 py-2.5 border-b border-gray-100 bg-gray-50">
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide">Account</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide">Industry</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide">Region</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide text-center">Signals</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide text-center">Brief</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide text-center">Drafts</span>
            <span className="text-[10px] font-bold uppercase text-gray-400 tracking-wide">Status</span>
          </div>

          {/* Rows */}
          {accounts.map((account) => (
            <div
              key={account.id}
              onClick={() => navigate(`/accounts/${account.id}`)}
              className="grid grid-cols-[2fr_1fr_1fr_80px_80px_80px_100px] gap-3 px-5 py-3 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-colors items-center"
            >
              {/* Account */}
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-brand-pale text-brand flex items-center justify-center text-xs font-bold shrink-0">
                  {initials(account.name)}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{account.name || account.domain}</p>
                  {account.domain && (
                    <p className="text-xs text-gray-400 truncate">{account.domain}</p>
                  )}
                </div>
              </div>

              {/* Industry */}
              <span className="text-xs text-gray-600 truncate">{account.industry || '—'}</span>

              {/* Region */}
              <span className="text-xs text-gray-600 truncate">{account.country || '—'}</span>

              {/* Signals */}
              <div className="text-center">
                {account.signal_count > 0 ? (
                  <span className="inline-flex items-center gap-1 text-xs font-semibold text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">
                    <ThunderboltOutlined className="text-[10px]" />
                    {account.signal_count}
                  </span>
                ) : (
                  <span className="text-xs text-gray-300">0</span>
                )}
              </div>

              {/* Brief */}
              <div className="text-center">
                {account.has_brief ? (
                  <span className="text-xs font-semibold text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Ready</span>
                ) : (
                  <span className="text-xs text-gray-300">None</span>
                )}
              </div>

              {/* Drafts */}
              <div className="text-center">
                {account.open_draft_count > 0 ? (
                  <span className="text-xs font-semibold text-brand">{account.open_draft_count}</span>
                ) : (
                  <span className="text-xs text-gray-300">0</span>
                )}
              </div>

              {/* Status */}
              <div className="flex items-center gap-1.5">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: STATUS_COLORS[account.status] || '#8c8c8c' }}
                />
                <span className="text-xs text-gray-600 capitalize">{account.status}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AccountsPage;
