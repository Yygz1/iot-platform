import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Typography, message, Space, Alert } from 'antd';
import { UserOutlined, LockOutlined, RobotOutlined } from '@ant-design/icons';
import client from '../../api/client';

const { Title, Text } = Typography;

interface LoginPageProps {
  onLogin: (token: string, username: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLogin }) => {
  const [loading, setLoading] = useState(false);
  const [isRegister, setIsRegister] = useState(false);
  const [hasUsers, setHasUsers] = useState<boolean | null>(null);

  useEffect(() => {
    client.get('/auth/check').then((r) => {
      setHasUsers(r.data.has_users);
      if (!r.data.has_users) setIsRegister(true);
    }).catch(() => setHasUsers(true));
  }, []);

  const handleSubmit = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const endpoint = isRegister ? '/auth/register' : '/auth/login';
      const resp = await client.post(endpoint, values);
      const { token, username } = resp.data;
      localStorage.setItem('iot_token', token);
      localStorage.setItem('iot_username', username);
      message.success(isRegister ? '注册成功' : '登录成功');
      onLogin(token, username);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '操作失败';
      message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (hasUsers === null) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>加载中...</div>;
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100vh', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <Card style={{ width: 400, borderRadius: 12, boxShadow: '0 8px 32px rgba(0,0,0,0.2)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <RobotOutlined style={{ fontSize: 48, color: '#1677ff' }} />
          <Title level={3} style={{ marginTop: 12, marginBottom: 4 }}>IoT Platform</Title>
          <Text type="secondary">设备影子与分布式智能体平台</Text>
        </div>

        {isRegister && !hasUsers && (
          <Alert
            type="info"
            message="首次使用，请创建管理员账号"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Form layout="vertical" onFinish={handleSubmit} initialValues={{ username: '', password: '' }}>
          <Form.Item name="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少6位' }]}>
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              {isRegister ? '注册' : '登录'}
            </Button>
          </Form.Item>
        </Form>

        {hasUsers && (
          <div style={{ textAlign: 'center' }}>
            <Space>
              <Text type="secondary">{isRegister ? '已有账号？' : '没有账号？'}</Text>
              <Button type="link" size="small" onClick={() => setIsRegister(!isRegister)}>
                {isRegister ? '去登录' : '去注册'}
              </Button>
            </Space>
          </div>
        )}
      </Card>
    </div>
  );
};
