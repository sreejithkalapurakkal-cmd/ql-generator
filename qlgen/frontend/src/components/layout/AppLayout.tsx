import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Avatar, Dropdown, type MenuProps } from 'antd';
import { UserOutlined, LogoutOutlined, TeamOutlined } from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';


const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const menuItems = [
    { key: '/welcome', icon: '✦', label: 'Home' },
    { key: '/dashboard', icon: '▦', label: 'Dashboard' },
    { key: '/icp', icon: '◈', label: 'Saved ICPs' },
    { key: '/tools', icon: '⚙', label: 'Tools' },
  ];

  // Add Users link for super_admin
  if (user?.role === 'super_admin') {
    menuItems.push({ key: '/admin/users', icon: '👥', label: 'Users' });
  }

  // Don't highlight "Saved Searches" when on ICP form pages (new or edit)
  const isICPFormPage = location.pathname === '/icp/new' || location.pathname.match(/^\/icp\/[^/]+\/edit$/);
  const selectedKey = isICPFormPage
    ? null
    : menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/dashboard';

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
            {user?.role === 'super_admin' ? 'Super Admin' : 'User'}
          </div>
        </div>
      ),
      disabled: true,
    },
    { type: 'divider' },
    ...(user?.role === 'super_admin'
      ? [
        {
          key: 'users',
          icon: <TeamOutlined />,
          label: 'Manage Users',
          onClick: () => navigate('/admin/users'),
        },
        { type: 'divider' as const },
      ]
      : []),
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: 'Sign out',
      onClick: handleLogout,
    },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', overflowX: 'hidden' }}>
      {/* Global Navigation */}
      <nav className="global-nav">
        <div className="gnav-container">
          <div className="gnav-logo" onClick={() => navigate('/welcome')}>
            <div className="gnav-logo-mark">ql</div>
            <span className="gnav-logo-text">qlGen</span>
          </div>

          <div className="gnav-links">
            {menuItems.map((item) => (
              <button
                key={item.key}
                className={`gnav-link ${selectedKey === item.key ? 'active' : ''}`}
                onClick={() => navigate(item.key)}
              >
                <span className="gnav-icon">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>

          <div className="gnav-right" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
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
              <img
                src="images/gadgeon.svg"
                alt="Gadgeon"
                style={{ height: '24px' }}
              />
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div style={{ flex: 1, background: 'var(--g50)', overflowX: 'hidden' }}>
        {children}
      </div>
    </div>
  );
};

export default AppLayout;
