import React, { useEffect, useState } from 'react';
import { Drawer, Table, Tag, Timeline, Typography, Spin, message } from 'antd';
import { listFeedback, getFeedback } from '../api/feedbackApi';
import type { FeedbackListItem, FeedbackItem, FeedbackType, FeedbackStatus } from '../types';

const { Text } = Typography;

interface Props {
  open: boolean;
  onClose: () => void;
}

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

const MySubmissionsModal: React.FC<Props> = ({ open, onClose }) => {
  const [items, setItems] = useState<FeedbackListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedDetail, setExpandedDetail] = useState<Record<string, FeedbackItem>>({});
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (open) {
      fetchItems();
    }
  }, [open]);

  const fetchItems = async () => {
    setLoading(true);
    try {
      const resp = await listFeedback();
      setItems(resp.data);
    } catch {
      message.error('Failed to load submissions');
    } finally {
      setLoading(false);
    }
  };

  const loadDetail = async (id: string) => {
    if (expandedDetail[id]) return;
    setLoadingDetails((prev) => ({ ...prev, [id]: true }));
    try {
      const resp = await getFeedback(id);
      setExpandedDetail((prev) => ({ ...prev, [id]: resp.data }));
    } catch {
      message.error('Failed to load details');
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [id]: false }));
    }
  };

  const columns = [
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
      width: 120,
      render: (s: FeedbackStatus) => <Tag color={statusColorMap[s]}>{statusLabel[s]}</Tag>,
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
  ];

  const expandedRowRender = (record: FeedbackListItem) => {
    const detail = expandedDetail[record.id];
    const isLoading = loadingDetails[record.id];

    if (isLoading) {
      return <Spin size="small" style={{ padding: 16 }} />;
    }

    if (!detail) {
      return <Text type="secondary">Loading...</Text>;
    }

    return (
      <div style={{ padding: '8px 0' }}>
        <Text strong>Description</Text>
        <div style={{ margin: '8px 0 16px', whiteSpace: 'pre-wrap', color: '#555' }}>
          {detail.description}
        </div>

        {detail.replies.length > 0 && (
          <>
            <Text strong>Admin Replies</Text>
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
          </>
        )}

        {detail.replies.length === 0 && (
          <Text type="secondary" italic>
            No replies yet
          </Text>
        )}
      </div>
    );
  };

  return (
    <Drawer
      title="My Submissions"
      open={open}
      onClose={onClose}
      width={700}
      destroyOnClose
    >
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={false}
        size="small"
        expandable={{
          expandedRowRender,
          onExpand: (expanded, record) => {
            if (expanded) loadDetail(record.id);
          },
        }}
      />
    </Drawer>
  );
};

export default MySubmissionsModal;
