import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout as AntLayout, Menu, Typography, Button, Space } from 'antd';
import {
  DashboardOutlined,
  ApiOutlined,
  NodeIndexOutlined,
  FileTextOutlined,
  RobotOutlined,
  SettingOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { getUsername, logout } from '../api/auth';

const { Header, Sider, Content } = AntLayout;
const { Title, Text } = Typography;

const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '仪表盘' },
  { key: '/devices', icon: <ApiOutlined />, label: '设备管理' },
  { key: '/rules', icon: <NodeIndexOutlined />, label: '规则引擎' },
  { key: '/logs', icon: <FileTextOutlined />, label: '事件日志' },
  { key: '/agents', icon: <RobotOutlined />, label: '智能体' },
  { key: '/settings', icon: <SettingOutlined />, label: '告警通知' },
];

export const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const username = getUsername();

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="60">
        <div style={{ padding: '16px', textAlign: 'center' }}>
          <Title level={5} style={{ color: '#fff', margin: 0 }}>
            IoT Platform
          </Title>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={4} style={{ margin: '16px 0' }}>
            {menuItems.find((m) => m.key === location.pathname)?.label ?? '物联网设备影子与规则引擎平台'}
          </Title>
          <Space>
            <UserOutlined />
            <Text>{username || 'admin'}</Text>
            <Button type="text" icon={<LogoutOutlined />} onClick={logout} size="small">
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8, overflow: 'auto' }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
};
