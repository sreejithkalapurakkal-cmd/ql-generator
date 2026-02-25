import React from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  SettingOutlined,
  RocketOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = Layout;

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { key: '/dashboard', icon: <DashboardOutlined />, label: 'Dashboard' },
    { key: '/icp', icon: <SettingOutlined />, label: 'ICP Configs' },
    { key: '/icp/new', icon: <RocketOutlined />, label: 'New ICP' },
  ];

  const selectedKey = menuItems.find((item) => location.pathname.startsWith(item.key))?.key || '/dashboard';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={220} theme="dark" style={{ background: '#001529' }}>
        <div style={{ padding: '20px 16px', textAlign: 'center' }}>
          <h2 style={{ color: '#fff', margin: 0, fontSize: 22, fontWeight: 700 }}>
            <TeamOutlined style={{ marginRight: 8 }} />
            qlGen
          </h2>
          <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, margin: '4px 0 0' }}>
            Lead Generation Tool
          </p>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          <h3 style={{ margin: 0, lineHeight: '64px', color: '#1F4E79' }}>
            ICP-Driven Qualified Lead Generation
          </h3>
        </Header>
        <Content style={{ margin: '24px', minHeight: 280 }}>{children}</Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
