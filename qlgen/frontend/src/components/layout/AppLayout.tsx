import React, { useState } from 'react';
import { Layout } from 'antd';
import {
  UserOutlined,
  LeftOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const menuItems = [
    { key: '/dashboard', icon: '▦', label: 'Dashboard' },
    { key: '/icp', icon: '◈', label: 'Saved ICPs' },
    { key: '/icp/new', icon: '+', label: 'New Run' },
  ];

  const selectedKey = menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/dashboard';

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

        {/* <div
          style={{
            padding: '14px 16px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            borderTop: '1px solid var(--g200)',
            justifyContent: collapsed ? 'center' : 'flex-start',
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--orange), #f7934b)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 13,
              fontWeight: 600,
              color: '#fff',
              flexShrink: 0,
            }}
          >
            <UserOutlined />
          </div>
          {!collapsed && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--g700)' }}>User</div>
              <div style={{ fontSize: 11, color: 'var(--g400)', marginTop: 1 }}>Sales Lead</div>
            </div>
          )}
        </div> */}

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
