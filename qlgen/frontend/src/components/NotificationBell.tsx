import React, { useEffect, useState, useCallback } from 'react';
import { Badge, Drawer, Button, Spin, message } from 'antd';
import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from './ui';
import {
  getUnreadCount, getNotifications, markRead, markAllRead,
} from '../api/notificationApi';
import { Notification } from '../types';

const NotificationBell: React.FC = () => {
  const navigate = useNavigate();
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchUnread = useCallback(() => {
    getUnreadCount()
      .then((res) => setUnread(res.data.unread_count))
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchUnread();
    const interval = setInterval(fetchUnread, 30000);
    return () => clearInterval(interval);
  }, [fetchUnread]);

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await getNotifications({ limit: 30 });
      setNotifications(res.data.notifications || []);
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  };

  const handleOpen = () => {
    setOpen(true);
    fetchNotifications();
  };

  const handleClick = async (notif: Notification) => {
    if (!notif.is_read) {
      await markRead([notif.id]);
      setNotifications((prev) =>
        prev.map((n) => n.id === notif.id ? { ...n, is_read: true } : n)
      );
      setUnread((prev) => Math.max(0, prev - 1));
    }
    if (notif.link) {
      setOpen(false);
      navigate(notif.link);
    }
  };

  const handleMarkAllRead = async () => {
    await markAllRead();
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnread(0);
    message.success('All notifications marked as read');
  };

  const timeAgo = (iso: string | null) => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  return (
    <>
      {/* Bell trigger */}
      <div
        onClick={handleOpen}
        className="cursor-pointer flex items-center px-2 py-1 rounded-md hover:bg-black/[0.04] transition-colors"
      >
        <Badge count={unread} size="small" offset={[-2, 2]}>
          <BellOutlined className="text-lg text-gray-500" />
        </Badge>
      </div>

      {/* Notification drawer */}
      <Drawer
        title={
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-gray-900">Notifications</span>
              {unread > 0 && (
                <span className="text-xs font-semibold bg-brand text-white px-1.5 py-0.5 rounded-full leading-none">
                  {unread}
                </span>
              )}
            </div>
            {unread > 0 && (
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                onClick={handleMarkAllRead}
                className="!text-xs"
              >
                Mark all read
              </Button>
            )}
          </div>
        }
        open={open}
        onClose={() => setOpen(false)}
        width={380}
        styles={{ body: { padding: 0 } }}
      >
        {loading ? (
          <div className="flex justify-center py-10"><Spin /></div>
        ) : notifications.length === 0 ? (
          <EmptyState
            icon={<BellOutlined />}
            title="No notifications"
            description="You're all caught up."
            className="py-10"
          />
        ) : (
          <div className="divide-y divide-gray-50">
            {notifications.map((notif) => (
              <div
                key={notif.id}
                onClick={() => handleClick(notif)}
                className={`group px-5 py-3 transition-colors ${
                  notif.link ? 'cursor-pointer' : 'cursor-default'
                } ${
                  notif.is_read
                    ? 'bg-white hover:bg-gray-50'
                    : 'bg-brand-pale/40 hover:bg-brand-pale/60'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      {!notif.is_read && (
                        <span className="w-1.5 h-1.5 rounded-full bg-brand shrink-0" />
                      )}
                      <span className={`text-xs leading-snug ${
                        notif.is_read ? 'text-gray-700' : 'text-gray-900 font-semibold'
                      }`}>
                        {notif.title}
                      </span>
                    </div>
                    {notif.body && (
                      <p className="text-xs text-gray-500 leading-snug">
                        {notif.body.length > 100 ? notif.body.slice(0, 100) + '...' : notif.body}
                      </p>
                    )}
                  </div>
                  <span className="text-[10px] text-gray-400 shrink-0 mt-0.5 tabular-nums">
                    {timeAgo(notif.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Drawer>
    </>
  );
};

export default NotificationBell;
