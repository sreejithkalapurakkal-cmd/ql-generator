import React, { useEffect, useState } from 'react';
import { Button, Modal, Input, message, Spin, Tooltip } from 'antd';
import { PlusOutlined, ThunderboltOutlined, TeamOutlined, ClockCircleOutlined, ScheduleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { PillTabs, EmptyState, Badge } from '../components/ui';
import { getTrackingLists, createTrackingList, deleteTrackingList } from '../api/trackingApi';
import { TrackingList } from '../types';
import MonitoringConfigDrawer from '../components/MonitoringConfigDrawer';

const TrackingListsPage: React.FC = () => {
  const navigate = useNavigate();
  const [lists, setLists] = useState<TrackingList[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [monitoringList, setMonitoringList] = useState<TrackingList | null>(null);

  const fetchLists = () => {
    setLoading(true);
    getTrackingLists()
      .then((res) => setLists(res.data.lists || []))
      .catch(() => setLists([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchLists(); }, []);

  const handleCreate = async () => {
    if (!newName.trim()) { message.warning('Name is required'); return; }
    setCreating(true);
    try {
      const res = await createTrackingList({
        name: newName.trim(),
        description: newDesc.trim() || undefined,
      });
      message.success('Tracking list created');
      setCreateOpen(false);
      setNewName('');
      setNewDesc('');
      navigate(`/tracking/${res.data.id}`);
    } catch {
      message.error('Failed to create list');
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteTrackingList(id);
      message.success('List deleted');
      fetchLists();
    } catch {
      message.error('Failed to delete list');
    }
  };

  const formatDate = (iso: string | null) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
    });
  };

  const timeAgo = (iso: string | null) => {
    if (!iso) return 'Never';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d ago`;
    return `${Math.floor(days / 30)}mo ago`;
  };

  const getHintsCount = (list: TrackingList) =>
    (list.signal_hints?.budget_signals?.length || 0) +
    (list.signal_hints?.urgency_signals?.length || 0) +
    (list.signal_hints?.custom_hints?.length || 0);

  const getHintChips = (list: TrackingList) => {
    const chips: { label: string; color: string }[] = [];
    list.signal_hints?.budget_signals?.forEach((s) =>
      chips.push({ label: `$ ${s}`, color: 'bg-green-50 text-green-700' }),
    );
    list.signal_hints?.urgency_signals?.forEach((s) =>
      chips.push({ label: `! ${s}`, color: 'bg-orange-50 text-orange-700' }),
    );
    list.signal_hints?.custom_hints?.forEach((s) =>
      chips.push({ label: s, color: 'bg-blue-50 text-blue-700' }),
    );
    return chips.slice(0, 3);
  };

  return (
    <div className="px-10 py-8 max-w-[1400px] mx-auto">
      {/* Secondary nav */}
      <PillTabs
        tabs={[
          { key: 'lists', label: 'My Lists' },
          { key: 'feed', label: 'Signal Feed' },
        ]}
        activeKey="lists"
        onChange={(v) => { if (v === 'feed') navigate('/signals'); }}
        className="mb-6"
      />

      {/* Page header */}
      <div className="flex items-center justify-between mb-7">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Tracking Lists</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Track and monitor your most qualified companies
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          size="large"
          onClick={() => setCreateOpen(true)}
          className="!rounded-lg"
        >
          New List
        </Button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex justify-center py-20"><Spin size="large" /></div>
      ) : lists.length === 0 ? (
        <EmptyState
          icon={<PlusOutlined />}
          title="No tracking lists yet"
          description="Create your first tracking list to start monitoring companies."
          action={
            <Button type="primary" onClick={() => setCreateOpen(true)}>
              Create your first list
            </Button>
          }
          className="py-20"
        />
      ) : (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-5">
          {lists.map((list) => (
            <div
              key={list.id}
              onClick={() => navigate(`/tracking/${list.id}`)}
              className={`bg-white border border-gray-200 rounded-lg hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer p-5 group ${
                list.monitoring_config?.enabled ? 'border-t-[3px] border-t-green-500' : 'border-t-[3px] border-t-gray-200'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    {list.monitoring_config?.enabled && (
                      <span className="w-2 h-2 rounded-full bg-green-500 shrink-0" />
                    )}
                    <h3 className="text-sm font-semibold text-gray-900 truncate">
                      {list.name}
                    </h3>
                  </div>
                  {list.description && (
                    <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 mt-1">
                      {list.description}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                  <Tooltip title="Monitoring schedule">
                    <button
                      onClick={(e) => { e.stopPropagation(); setMonitoringList(list); }}
                      className="text-gray-300 hover:text-brand transition-colors text-sm px-1"
                    >
                      <ScheduleOutlined />
                    </button>
                  </Tooltip>
                  <button
                    onClick={(e) => handleDelete(list.id, e)}
                    className="text-gray-300 hover:text-gray-500 transition-all text-base px-1"
                    title="Delete list"
                  >
                    &times;
                  </button>
                </div>
              </div>

              {/* Metrics row */}
              <div className="flex items-center gap-4 pt-3 mt-3 border-t border-gray-100 text-xs text-gray-400">
                <span className="flex items-center gap-1">
                  <TeamOutlined className="text-[11px]" />
                  <span className={`font-semibold ${list.company_count > 0 ? 'text-brand' : 'text-gray-300'}`}>
                    {list.company_count}
                  </span>
                  companies
                </span>
                {getHintsCount(list) > 0 && (
                  <span className="flex items-center gap-1">
                    <ThunderboltOutlined className="text-[11px]" />
                    <span className="font-semibold text-gray-600">{getHintsCount(list)}</span> hints
                  </span>
                )}
                <span className="flex items-center gap-1 ml-auto">
                  <ClockCircleOutlined className="text-[11px]" />
                  {timeAgo(list.last_monitored_at)}
                </span>
              </div>

              {/* Hint preview chips */}
              {getHintChips(list).length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {getHintChips(list).map((chip, i) => (
                    <Badge key={i} className={`${chip.color} text-[10px]`}>
                      {chip.label}
                    </Badge>
                  ))}
                  {getHintsCount(list) > 3 && (
                    <span className="text-[10px] text-gray-400 self-center">+{getHintsCount(list) - 3} more</span>
                  )}
                </div>
              )}

              {/* Created date */}
              <p className="text-[10px] text-gray-300 mt-2 text-right">
                Created {formatDate(list.created_at)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal
        title="Create Tracking List"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setNewName(''); setNewDesc(''); }}
        onOk={handleCreate}
        confirmLoading={creating}
        okText="Create"
      >
        <div className="mt-4">
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
            List Name
          </label>
          <Input
            placeholder="e.g., Conference Q2 2026"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onPressEnter={handleCreate}
            autoFocus
          />
          <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1.5 mt-4">
            Description (optional)
          </label>
          <Input.TextArea
            placeholder="What companies are you tracking?"
            value={newDesc}
            onChange={(e) => setNewDesc(e.target.value)}
            rows={3}
          />
        </div>
      </Modal>

      {/* Monitoring Config Drawer */}
      {monitoringList && (
        <MonitoringConfigDrawer
          open={!!monitoringList}
          onClose={() => setMonitoringList(null)}
          listId={monitoringList.id}
          config={monitoringList.monitoring_config || {}}
          signalHints={monitoringList.signal_hints}
          lastMonitoredAt={monitoringList.last_monitored_at}
          onSaved={() => {
            setMonitoringList(null);
            fetchLists();
          }}
        />
      )}
    </div>
  );
};

export default TrackingListsPage;
