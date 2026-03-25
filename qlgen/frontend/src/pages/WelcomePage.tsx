import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Avatar, Dropdown, Tooltip, type MenuProps } from 'antd';
import { SearchOutlined, UnorderedListOutlined, GoogleOutlined, UserOutlined, LogoutOutlined, TeamOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;
const REDIRECT_URI = `${window.location.origin}/auth/callback`;

function buildGoogleAuthUrl() {
  const params = new URLSearchParams({
    client_id: GOOGLE_CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: 'code',
    scope: 'openid email profile',
    access_type: 'offline',
    prompt: 'select_account',
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();

  const handleGoogleLogin = () => {
    window.location.href = buildGoogleAuthUrl();
  };

  const handleLogout = async () => {
    await logout();
  };

  const handleCTAClick = (path: string) => {
    if (isAuthenticated) {
      navigate(path);
    } else {
      handleGoogleLogin();
    }
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
      {/* Header */}
      <nav className="global-nav">
        <div className="gnav-container">
          <div className="gnav-logo" onClick={() => navigate('/welcome')}>
            <div className="gnav-logo-mark">ql</div>
            <span className="gnav-logo-text">qlGen</span>
          </div>

          {isAuthenticated && (
            <div className="gnav-links">
              {[
                { key: '/welcome', icon: '✦', label: 'Home' },
                { key: '/dashboard', icon: '▦', label: 'Dashboard' },
                { key: '/icp', icon: '◈', label: 'Saved ICPs' },
                ...(user?.role === 'super_admin'
                  ? [
                    { key: '/tools', icon: '⚙', label: 'Tools' },
                    { key: '/admin/users', icon: '👥', label: 'Users' },
                  ]
                  : []),
              ].map((item) => (
                <button
                  key={item.key}
                  className={`gnav-link ${item.key === '/welcome' ? 'active' : ''}`}
                  onClick={() => navigate(item.key)}
                >
                  <span className="gnav-icon">{item.icon}</span>
                  {item.label}
                </button>
              ))}
            </div>
          )}

          <div className="gnav-right" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {isAuthenticated && (
              <Tooltip title="User Guide">
                <QuestionCircleOutlined
                  onClick={() => window.open('/qlGen-User-Guide.pdf', '_blank')}
                  style={{ fontSize: 18, color: 'rgba(0,0,0,0.45)', cursor: 'pointer', transition: 'color 0.2s' }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = '#5C2D8F')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'rgba(0,0,0,0.45)')}
                />
              </Tooltip>
            )}
            {isAuthenticated ? (
              <Dropdown menu={{ items: userMenuItems }} placement="bottomRight" trigger={['click']}>
                <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                  {user?.picture_url ? (
                    <Avatar size={32} src={user.picture_url} />
                  ) : (
                    <Avatar size={32} icon={<UserOutlined />} style={{ background: '#5C2D8F' }} />
                  )}
                </div>
              </Dropdown>
            ) : (
              <button
                onClick={handleGoogleLogin}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 20px',
                  background: 'var(--purple)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = '#6d28d9'; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--purple)'; }}
              >
                <GoogleOutlined />
                Sign in with Google
              </button>
            )}
            <div className="gnav-brand">
              <img src="images/gadgeon.svg" alt="Gadgeon" style={{ height: '24px' }} />
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div style={{
        flex: 1,
        background: '#f8fafc',
        backgroundImage: 'linear-gradient(to right, #e2e8f080 1px, transparent 1px), linear-gradient(to bottom, #e2e8f080 1px, transparent 1px)',
        backgroundSize: '40px 40px',
        overflow: 'hidden'
      }}>
        <main style={{ display: 'flex', alignItems: 'center', minHeight: 'calc(100vh - 60px)' }}>
          <div style={{
            maxWidth: 1400,
            margin: '0 auto',
            padding: '48px 32px',
            width: '100%',
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 64,
            alignItems: 'center'
          }}>
            {/* Left Column - Content */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 24, zIndex: 10 }}>
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 16px',
                borderRadius: 9999,
                background: '#fce7f3',
                border: '1px solid #fbcfe8',
                color: '#db2777',
                fontWeight: 600,
                fontSize: 14,
                width: 'fit-content',
                marginBottom: 8
              }}>
                ⚡ AI-Powered Lead Discovery
              </div>

              <h1 style={{
                fontSize: 56,
                fontWeight: 800,
                color: 'var(--g900)',
                lineHeight: 1.1,
                margin: 0
              }}>
                Build a pipeline of <br />
                <span className="text-gradient">qualified leads</span> in minutes.
              </h1>

              <p style={{
                fontSize: 18,
                color: 'var(--g600)',
                lineHeight: 1.6,
                maxWidth: 560,
                fontWeight: 500,
                margin: 0
              }}>
                Convert your Ideal Customer Profile (ICP) into a sales-ready list of target companies and key decision-makers. qlGen automatically discovers, enriches, and BANT-scores every opportunity.
              </p>

              <div style={{ display: 'flex', flexDirection: 'row', gap: 16, marginTop: 24 }}>
                <button
                  onClick={() => handleCTAClick('/icp/new')}
                  style={{
                    padding: '16px 32px',
                    background: 'var(--purple)',
                    color: 'white',
                    fontWeight: 700,
                    borderRadius: 12,
                    boxShadow: '0 8px 20px rgba(92, 45, 143, 0.3)',
                    border: 'none',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 12,
                    fontSize: 18,
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = '#6d28d9';
                    e.currentTarget.style.boxShadow = '0 12px 25px rgba(92, 45, 143, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'var(--purple)';
                    e.currentTarget.style.boxShadow = '0 8px 20px rgba(92, 45, 143, 0.3)';
                  }}
                >
                  <SearchOutlined style={{ fontSize: 20 }} /> Start Your Search
                </button>

                <button
                  onClick={() => handleCTAClick('/dashboard')}
                  style={{
                    padding: '16px 32px',
                    background: 'white',
                    color: 'var(--g800)',
                    border: '2px solid var(--g200)',
                    fontWeight: 700,
                    borderRadius: 12,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 12,
                    fontSize: 18,
                    transition: 'all 0.2s',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'var(--g50)';
                    e.currentTarget.style.borderColor = 'var(--g300)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'white';
                    e.currentTarget.style.borderColor = 'var(--g200)';
                  }}
                >
                  <UnorderedListOutlined style={{ fontSize: 20 }} /> Explore past searches
                </button>
              </div>
            </div>

            {/* Right Column - Fanout Graphic */}
            <div className="fanout-container" style={{ display: 'flex' }}>
              <svg className="connecting-lines" viewBox="0 0 600 500" preserveAspectRatio="xMidYMid meet">
                <g stroke="#cbd5e1" strokeWidth="2" strokeDasharray="6,6" fill="none">
                  <path d="M300,250 L110,380" />
                  <path d="M300,250 L60,250" />
                  <path d="M300,250 L140,100" />
                  <path d="M300,250 L300,40" />
                  <path d="M300,250 L460,100" />
                  <path d="M300,250 L540,250" />
                  <path d="M300,250 L490,380" />
                </g>
              </svg>

              <div className="central-hub">qlGen</div>

              <div className="fanout-node fanout-node-1">
                <img src="images/linkedin.png" alt="LinkedIn" />
                <span>LinkedIn</span>
              </div>

              <div className="fanout-node fanout-node-2">
                <img src="images/lusha.svg" alt="Lusha" />
                <span>Lusha</span>
              </div>

              <div className="fanout-node fanout-node-3">
                <img src="images/duckduckgo.svg" alt="Tavily" />
                <span>DuckDuckGo</span>
              </div>

              <div className="fanout-node fanout-node-4">
                <img src="images/tavily.jpeg" alt="Tavily" />
                <span>Tavily</span>
              </div>

              <div className="fanout-node fanout-node-5">
                <img src="images/apollo.jpeg" alt="Apollo.io" />
                <span>Apollo.io</span>
              </div>

              <div className="fanout-node fanout-node-6">
                <img src="images/exa.jpeg" alt="Exa.ai" />
                <span>Exa.ai</span>
              </div>

              <div className="fanout-node fanout-node-7">
                <img src="images/hunter.svg" alt="Hunter.io" />
                <span>Hunter.io</span>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default WelcomePage;
