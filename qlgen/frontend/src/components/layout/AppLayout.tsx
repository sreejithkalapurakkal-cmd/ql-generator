import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';


const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/welcome', icon: '✦', label: 'Home' },
    { key: '/dashboard', icon: '▦', label: 'Dashboard' },
    { key: '/icp', icon: '◈', label: 'Saved Searches' },
  ];

  const selectedKey = menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/dashboard';

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

          <div className="gnav-right">
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
