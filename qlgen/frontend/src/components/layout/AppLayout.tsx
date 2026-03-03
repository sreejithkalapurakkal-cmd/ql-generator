import React, { useState, useEffect } from 'react';
import { Layout } from 'antd';
import {
  LeftOutlined,
  RightOutlined,
  MenuOutlined,
  CloseOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content } = Layout;

const useIsMobile = () => {
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return isMobile;
};

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const isMobile = useIsMobile();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const menuItems = [
    { key: '/welcome', icon: '✦', label: 'Welcome' },
    { key: '/dashboard', icon: '▦', label: 'Dashboard' },
    { key: '/icp', icon: '◈', label: 'Saved ICPs' },
    { key: '/icp/new', icon: '+', label: 'New Run' },
  ];

  const selectedKey = menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/dashboard';

  // Close mobile menu on route change
  useEffect(() => { setMobileMenuOpen(false); }, [location.pathname]);

  if (isMobile) {
    return (
      <Layout style={{ minHeight: '100vh' }}>
        {/* Mobile top bar */}
        <div style={{
          background: '#fff',
          borderBottom: '1px solid var(--g200)',
          padding: '10px 16px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 100,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{
              width: 30, height: 30,
              background: 'linear-gradient(135deg, var(--purple), var(--purple-l))',
              borderRadius: 7, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: '#fff',
              boxShadow: '0 2px 8px rgba(92,45,143,.3)',
            }}>ql</div>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--g800)' }}>qlGen</span>
          </div>
          <div onClick={() => setMobileMenuOpen(!mobileMenuOpen)} style={{ cursor: 'pointer', fontSize: 18, color: 'var(--g600)' }}>
            {mobileMenuOpen ? <CloseOutlined /> : <MenuOutlined />}
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {mobileMenuOpen && (
          <div style={{
            background: '#fff',
            borderBottom: '1px solid var(--g200)',
            padding: '4px 8px 8px',
            position: 'sticky',
            top: 50,
            zIndex: 99,
            boxShadow: 'var(--shadow-md)',
          }}>
            {menuItems.map((item) => (
              <div
                key={item.key}
                onClick={() => navigate(item.key)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '10px 14px', margin: '2px 0', borderRadius: 8,
                  color: selectedKey === item.key ? 'var(--purple)' : 'var(--g600)',
                  background: selectedKey === item.key ? 'var(--purple-pale)' : 'transparent',
                  cursor: 'pointer', fontSize: 14, fontWeight: 500,
                }}
              >
                <span style={{ width: 20, textAlign: 'center', fontSize: 15 }}>{item.icon}</span>
                <span>{item.label}</span>
              </div>
            ))}
          </div>
        )}

        <Content style={{ padding: '16px 12px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
          {children}
        </Content>
      </Layout>
    );
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={248}
        collapsedWidth={64}
        collapsed={collapsed}
        theme="light"
        style={{
          background: '#fff',
          borderRight: '1px solid var(--g200)',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 100,
          transition: 'width 0.2s ease',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '20px 20px 0',
            marginBottom: 28,
            fontSize: 18,
            fontWeight: 700,
            color: 'var(--g800)',
            letterSpacing: '-0.3px',
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              background: 'linear-gradient(135deg, var(--purple), var(--purple-l))',
              borderRadius: 9,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              fontWeight: 700,
              color: '#fff',
              flexShrink: 0,
              boxShadow: '0 2px 8px rgba(92,45,143,.3)',
            }}
          >
            ql
          </div>
          {!collapsed && <span>qlGen</span>}
        </div>

        <div style={{ padding: '0 8px' }}>
          {menuItems.map((item) => (
            <div
              key={item.key}
              onClick={() => navigate(item.key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: collapsed ? '12px' : '9px 12px 9px 16px',
                margin: '1px 0',
                borderRadius: 8,
                color: selectedKey === item.key ? 'var(--purple)' : 'var(--g500)',
                background: selectedKey === item.key ? 'var(--purple-pale)' : 'transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                fontSize: 14,
                fontWeight: 500,
                justifyContent: collapsed ? 'center' : 'flex-start',
              }}
              onMouseEnter={(e) => {
                if (selectedKey !== item.key) {
                  e.currentTarget.style.background = 'var(--g100)';
                  e.currentTarget.style.color = 'var(--g800)';
                }
              }}
              onMouseLeave={(e) => {
                if (selectedKey !== item.key) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--g500)';
                }
              }}
            >
              <span style={{ width: 20, textAlign: 'center', flexShrink: 0, fontSize: 15 }}>
                {item.icon}
              </span>
              {!collapsed && <span>{item.label}</span>}
            </div>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <div
          onClick={() => setCollapsed(!collapsed)}
          style={{
            padding: '10px 20px',
            color: 'var(--g400)',
            cursor: 'pointer',
            fontSize: 12,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            borderTop: '1px solid var(--g200)',
            transition: 'color 0.15s',
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--g700)')}
          onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--g400)')}
        >
          {collapsed ? <RightOutlined /> : <LeftOutlined />}
          {!collapsed && <span>Collapse</span>}
        </div>
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 64 : 248, transition: 'margin-left 0.2s ease' }}>
        <Content style={{ padding: '28px 32px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
