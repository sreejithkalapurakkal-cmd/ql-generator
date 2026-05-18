import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Avatar, Dropdown, Input, Tooltip, type MenuProps } from 'antd';
import {
  UserOutlined, LogoutOutlined, TeamOutlined, SettingOutlined,
  MenuFoldOutlined, MenuUnfoldOutlined, SearchOutlined,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';
import NotificationBell from '../NotificationBell';

interface NavGroup {
  label: string;
  items: { key: string; icon: string; label: string; adminOnly?: boolean }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: 'Main',
    items: [
      { key: '/dashboard', icon: '▦', label: 'Dashboard' },
      { key: '/signals', icon: '◇', label: 'Signal Feed' },
      { key: '/accounts', icon: '◎', label: 'Accounts' },
    ],
  },
  {
    label: 'Research',
    items: [
      { key: '/icp', icon: '◈', label: 'Saved ICPs' },
      { key: '/all-leads', icon: '◉', label: 'All Leads' },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { key: '/tracking', icon: '⊙', label: 'Tracking Lists' },
      { key: '/signals/rules', icon: '⚡', label: 'Signal Rules' },
      { key: '/ingest', icon: '↑', label: 'Ingest' },
    ],
  },
  {
    label: 'Admin',
    items: [
      { key: '/tools', icon: '⚙', label: 'Tools', adminOnly: true },
      { key: '/admin/users', icon: '👥', label: 'Users', adminOnly: true },
    ],
  },
];

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';

  const getParentNavKey = (pathname: string): string | null => {
    if (pathname.startsWith('/tracking/')) return '/tracking';
    if (pathname.startsWith('/signals/rules')) return '/signals/rules';
    if (pathname.startsWith('/signals')) return '/signals';
    if (pathname.startsWith('/ingest/')) return '/ingest';
    if (pathname.startsWith('/accounts/')) return '/accounts';
    if (pathname.startsWith('/leads/')) return '/all-leads';
    if (pathname.startsWith('/pipeline/')) return '/all-leads';
    if (pathname.match(/^\/icp\//)) return '/icp';
    return null;
  };

  const selectedKey = getParentNavKey(location.pathname)
    || NAV_GROUPS.flatMap(g => g.items).find(item => location.pathname === item.key)?.key
    || '/dashboard';

  const handleLogout = async () => {
    await logout();
    navigate('/welcome');
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      label: (
        <div style={{ padding: '4px 0' }}>
          <div style={{ fontWeight: 500 }}>{user?.name || user?.email}</div>
          <div style={{ fontSize: 12, color: '#888' }}>{user?.email}</div>
          <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
            {user?.role === 'super_admin' ? 'Super Admin' : user?.role === 'admin' ? 'Admin' : 'User'}
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Sign out',
      onClick: handleLogout,
    },
  ];

  const sidebarWidth = collapsed ? 64 : 240;

  return (
    <div style={{ minHeight: '100vh', display: 'flex', overflowX: 'hidden' }}>
      {/* Sidebar */}
      <aside
        style={{
          width: sidebarWidth,
          minWidth: sidebarWidth,
          height: '100vh',
          position: 'fixed',
          top: 0,
          left: 0,
          zIndex: 100,
          background: '#fff',
          borderRight: '1px solid var(--g200, #e8e8e8)',
          display: 'flex',
          flexDirection: 'column',
          transition: 'width 0.2s ease',
          overflow: 'hidden',
        }}
      >
        {/* Logo */}
        <div
          style={{
            height: 56,
            display: 'flex',
            alignItems: 'center',
            padding: collapsed ? '0 16px' : '0 20px',
            gap: 10,
            cursor: 'pointer',
            borderBottom: '1px solid var(--g100, #f5f5f5)',
            flexShrink: 0,
          }}
          onClick={() => navigate('/dashboard')}
        >
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'var(--purple, #5C2D8F)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 800, flexShrink: 0,
          }}>
            ql
          </div>
          {!collapsed && (
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--g900, #111)' }}>qlGen</span>
          )}
        </div>

        {/* Nav groups */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 0' }}>
          {NAV_GROUPS.map((group) => {
            const visibleItems = group.items.filter(item => !item.adminOnly || isAdmin);
            if (visibleItems.length === 0) return null;
            return (
              <div key={group.label} style={{ marginBottom: 16 }}>
                {!collapsed && (
                  <div style={{
                    padding: '0 20px', marginBottom: 4,
                    fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                    letterSpacing: '0.05em', color: 'var(--g400, #999)',
                  }}>
                    {group.label}
                  </div>
                )}
                {visibleItems.map((item) => {
                  const isActive = selectedKey === item.key;
                  const btn = (
                    <button
                      key={item.key}
                      onClick={() => navigate(item.key)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        width: '100%',
                        padding: collapsed ? '8px 0' : '8px 20px',
                        justifyContent: collapsed ? 'center' : 'flex-start',
                        border: 'none',
                        background: isActive ? 'var(--purple-pale, #f0e6ff)' : 'transparent',
                        color: isActive ? 'var(--purple, #5C2D8F)' : 'var(--g600, #555)',
                        fontSize: 13,
                        fontWeight: isActive ? 600 : 500,
                        cursor: 'pointer',
                        borderRadius: 0,
                        borderRight: isActive ? '3px solid var(--purple, #5C2D8F)' : '3px solid transparent',
                        transition: 'all 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        if (!isActive) (e.currentTarget.style.background = 'var(--g50, #fafafa)');
                      }}
                      onMouseLeave={(e) => {
                        if (!isActive) (e.currentTarget.style.background = 'transparent');
                      }}
                    >
                      <span style={{ fontSize: 15, width: 20, textAlign: 'center', flexShrink: 0 }}>{item.icon}</span>
                      {!collapsed && <span>{item.label}</span>}
                    </button>
                  );
                  return collapsed ? (
                    <Tooltip key={item.key} title={item.label} placement="right">{btn}</Tooltip>
                  ) : btn;
                })}
              </div>
            );
          })}
        </nav>

        {/* Collapse toggle */}
        <div style={{
          padding: '12px 16px',
          borderTop: '1px solid var(--g100, #f5f5f5)',
          flexShrink: 0,
        }}>
          <button
            onClick={() => setCollapsed(!collapsed)}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '100%', height: 32, border: 'none',
              background: 'var(--g50, #fafafa)', borderRadius: 6,
              color: 'var(--g500, #888)', cursor: 'pointer', fontSize: 14,
            }}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div style={{ marginLeft: sidebarWidth, flex: 1, display: 'flex', flexDirection: 'column', transition: 'margin-left 0.2s ease' }}>
        {/* Top bar */}
        <header style={{
          height: 56,
          background: '#fff',
          borderBottom: '1px solid var(--g200, #e8e8e8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 24px',
          gap: 12,
          flexShrink: 0,
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}>
          <Input
            placeholder="Search accounts, signals..."
            prefix={<SearchOutlined style={{ color: '#999' }} />}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onPressEnter={() => {
              if (searchQuery.trim()) {
                navigate(`/accounts?search=${encodeURIComponent(searchQuery.trim())}`);
                setSearchQuery('');
              }
            }}
            style={{ width: 280, borderRadius: 8, marginRight: 'auto' }}
            allowClear
          />
          <NotificationBell />
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              {user?.picture_url ? (
                <Avatar size={32} src={user.picture_url} />
              ) : (
                <Avatar size={32} icon={<UserOutlined />} style={{ background: '#5C2D8F' }} />
              )}
            </div>
          </Dropdown>
          <div className="gnav-brand">
            <img src="images/gadgeon.svg" alt="Gadgeon" style={{ height: '24px' }} />
          </div>
        </header>

        {/* Content */}
        <main style={{ flex: 1, background: 'var(--g50, #fafafa)', overflowX: 'hidden' }}>
          {children}
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
