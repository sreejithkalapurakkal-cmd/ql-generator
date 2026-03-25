import React, { useEffect, useState } from 'react';
import {
  Table, Select, Tag, Button, Drawer, Input, Timeline, Typography, Space, Avatar, message,
} from 'antd';
import { UserOutlined, SendOutlined, EyeOutlined } from '@ant-design/icons';
import { listFeedback, getFeedback, updateFeedbackStatus, replyToFeedback } from '../api/feedbackApi';
import type { FeedbackListItem, FeedbackItem, FeedbackType, FeedbackStatus } from '../types';

const { Title, Text } = Typography;
const { TextArea } = Input;

const typeColorMap: Record<FeedbackType, string> = {
  feedback: 'blue',
  complaint: 'red',
  bug_report: 'orange',
  feature_request: 'green',
};

const typeLabel: Record<FeedbackType, string> = {
  feedback: 'Feedback',
  complaint: 'Complaint',
  bug_report: 'Bug Report',
  feature_request: 'Feature Request',
};

const statusColorMap: Record<FeedbackStatus, string> = {
  open: 'default',
  in_progress: 'processing',
  resolved: 'success',
  closed: 'default',
};

const statusLabel: Record<FeedbackStatus, string> = {
  open: 'Open',
  in_progress: 'In Progress',
  resolved: 'Resolved',
  closed: 'Closed',
};

const AdminFeedbackPage: React.FC = () => {
  const [items, setItems] = useState<FeedbackListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<FeedbackType | undefined>();
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | undefined>();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<FeedbackItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replying, setReplying] = useState(false);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const resp = await listFeedback({
        type_filter: typeFilter,
        status_filter: statusFilter,
      });
      setItems(resp.data);
    } catch {
      message.error('Failed to load feedback');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchItems();
  }, [typeFilter, statusFilter]);

  const openDetail = async (id: string) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    try {
      const resp = await getFeedback(id);
      setDetail(resp.data);
    } catch {
      message.error('Failed to load feedback detail');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleStatusChange = async (id: string, status: FeedbackStatus) => {
    try {
      await updateFeedbackStatus(id, status);
      message.success('Status updated');
      fetchItems();
      if (detail?.id === id) {
        setDetail((prev) => prev ? { ...prev, status } : prev);
      }
    } catch {
      message.error('Failed to update status');
    }
  };

  const handleReply = async () => {
    if (!detail || !replyText.trim()) return;
    setReplying(true);
    try {
      const resp = await replyToFeedback(detail.id, replyText.trim());
      setDetail((prev) =>
        prev ? { ...prev, replies: [...prev.replies, resp.data] } : prev
      );
      setReplyText('');
      message.success('Reply sent');
      fetchItems();
    } catch {
      message.error('Failed to send reply');
    } finally {
      setReplying(false);
    }
  };

  const columns = [
    {
      title: 'User',
      key: 'user',
      width: 200,
      render: (_: unknown, record: FeedbackListItem) => (
        <Space>
          <Avatar size={28} icon={<UserOutlined />} style={{ background: '#5C2D8F' }} />
          <div>
            <div style={{ fontWeight: 500, fontSize: 13 }}>{record.user_name || '—'}</div>
            <div style={{ fontSize: 11, color: '#888' }}>{record.user_email}</div>
          </div>
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 130,
      render: (t: FeedbackType) => <Tag color={typeColorMap[t]}>{typeLabel[t]}</Tag>,
    },
    {
      title: 'Subject',
      dataIndex: 'subject',
      key: 'subject',
      ellipsis: true,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 150,
      render: (status: FeedbackStatus, record: FeedbackListItem) => (
        <Select
          value={status}
          size="small"
          style={{ width: 130 }}
          onChange={(val) => handleStatusChange(record.id, val)}
          options={[
            { label: 'Open', value: 'open' },
            { label: 'In Progress', value: 'in_progress' },
            { label: 'Resolved', value: 'resolved' },
            { label: 'Closed', value: 'closed' },
          ]}
        />
      ),
    },
    {
      title: 'Replies',
      dataIndex: 'reply_count',
      key: 'reply_count',
      width: 80,
      render: (count: number) => count > 0 ? <Tag color="purple">{count}</Tag> : '—',
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 140,
      render: (val: string | null) =>
        val
          ? new Date(val).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })
          : '—',
    },
    {
      title: '',
      key: 'actions',
      width: 60,
      render: (_: unknown, record: FeedbackListItem) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          size="small"
          onClick={() => openDetail(record.id)}
        />
      ),
    },
  ];

  return (
    <div style={{ padding: '32px 48px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>Feedback Management</Title>
        <Space>
          <Select
            placeholder="Filter by type"
            allowClear
            style={{ width: 160 }}
            value={typeFilter}
            onChange={setTypeFilter}
            options={[
              { label: 'Feedback', value: 'feedback' },
              { label: 'Complaint', value: 'complaint' },
              { label: 'Bug Report', value: 'bug_report' },
              { label: 'Feature Request', value: 'feature_request' },
            ]}
          />
          <Select
            placeholder="Filter by status"
            allowClear
            style={{ width: 160 }}
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { label: 'Open', value: 'open' },
              { label: 'In Progress', value: 'in_progress' },
              { label: 'Resolved', value: 'resolved' },
              { label: 'Closed', value: 'closed' },
            ]}
          />
        </Space>
      </div>

      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={false}
        style={{ background: '#fff', borderRadius: 12 }}
      />

      <Drawer
        title="Feedback Detail"
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setDetail(null); setReplyText(''); }}
        width={560}
        loading={detailLoading}
      >
        {detail && (
          <div>
            <Space style={{ marginBottom: 12 }}>
              <Tag color={typeColorMap[detail.type]}>{typeLabel[detail.type]}</Tag>
              <Tag color={statusColorMap[detail.status]}>{statusLabel[detail.status]}</Tag>
            </Space>

            <Title level={5} style={{ marginTop: 8 }}>{detail.subject}</Title>

            <div style={{ marginBottom: 8 }}>
              <Text type="secondary" style={{ fontSize: 13 }}>
                By {detail.user_name || detail.user_email} &middot;{' '}
                {detail.created_at
                  ? new Date(detail.created_at).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : ''}
              </Text>
            </div>

            <div
              style={{
                background: '#fafafa',
                padding: 16,
                borderRadius: 8,
                marginBottom: 24,
                whiteSpace: 'pre-wrap',
              }}
            >
              {detail.description}
            </div>

            <Title level={5}>Replies</Title>

            {detail.replies.length > 0 ? (
              <Timeline style={{ marginTop: 12 }}>
                {detail.replies.map((reply) => (
                  <Timeline.Item key={reply.id} color="purple">
                    <div>
                      <Text strong style={{ fontSize: 13 }}>
                        {reply.user_name || reply.user_email || 'Admin'}
                      </Text>
                      <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                        {reply.created_at
                          ? new Date(reply.created_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })
                          : ''}
                      </Text>
                    </div>
                    <div style={{ marginTop: 4, whiteSpace: 'pre-wrap' }}>{reply.message}</div>
                  </Timeline.Item>
                ))}
              </Timeline>
            ) : (
              <Text type="secondary" italic style={{ display: 'block', marginBottom: 16 }}>
                No replies yet
              </Text>
            )}

            <div style={{ marginTop: 16 }}>
              <TextArea
                rows={3}
                placeholder="Type a reply..."
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                style={{ marginTop: 8 }}
                onClick={handleReply}
                loading={replying}
                disabled={!replyText.trim()}
              >
                Send Reply
              </Button>
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default AdminFeedbackPage;
