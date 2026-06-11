import React, { useState } from 'react';
import { Table, Tag, Button, Modal, Form, Input, Select, Switch, Space, message, Popconfirm, Tabs, Typography, Alert } from 'antd';
import { PlusOutlined, DeleteOutlined, EditOutlined, SendOutlined, BellOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import { toBeijingTime } from '../../utils/time';

const { Title } = Typography;

interface NotificationConfig {
  id: number;
  name: string;
  channel: string;
  config: Record<string, unknown>;
  enabled: boolean;
  level: string;
  created_at: string;
}

interface NotificationLogEntry {
  id: number;
  channel: string;
  device_id: string | null;
  title: string;
  message: string;
  success: boolean;
  error_msg: string | null;
  timestamp: string;
}

const channelLabels: Record<string, string> = {
  dingtalk: '钉钉',
  wechat: '企业微信',
  email: '邮件',
};

const channelColors: Record<string, string> = {
  dingtalk: 'blue',
  wechat: 'green',
  email: 'orange',
};

export const SettingsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<NotificationConfig | null>(null);
  const [form] = Form.useForm();

  const { data: configs, isLoading } = useQuery({
    queryKey: ['notification-configs'],
    queryFn: async () => (await client.get('/notifications')).data as NotificationConfig[],
    refetchInterval: 10000,
  });

  const { data: logs } = useQuery({
    queryKey: ['notification-logs'],
    queryFn: async () => (await client.get('/notifications/log-entries?limit=50')).data as NotificationLogEntry[],
    refetchInterval: 10000,
  });

  const createMut = useMutation({
    mutationFn: async (values: Record<string, unknown>) => {
      await client.post('/notifications', values);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-configs'] });
      setAddModalOpen(false);
      form.resetFields();
      message.success('通知配置已添加');
    },
    onError: () => message.error('添加失败'),
  });

  const updateMut = useMutation({
    mutationFn: async ({ id, ...values }: Record<string, unknown>) => {
      await client.put(`/notifications/${id}`, values);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-configs'] });
      setEditItem(null);
      form.resetFields();
      message.success('已更新');
    },
    onError: () => message.error('更新失败'),
  });

  const deleteMut = useMutation({
    mutationFn: async (id: number) => {
      await client.delete(`/notifications/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notification-configs'] });
      message.success('已删除');
    },
    onError: () => message.error('删除失败'),
  });

  const testMut = useMutation({
    mutationFn: async (id: number) => {
      const resp = await client.post(`/notifications/${id}/test`);
      return resp.data;
    },
    onSuccess: (data) => {
      message.success(data.success ? '测试发送成功' : '测试发送失败');
      queryClient.invalidateQueries({ queryKey: ['notification-logs'] });
    },
    onError: () => message.error('测试发送失败'),
  });

  const openEdit = (item: NotificationConfig) => {
    setEditItem(item);
    form.setFieldsValue({
      name: item.name,
      channel: item.channel,
      level: item.level,
      enabled: item.enabled,
      webhook_url: item.config.webhook_url || '',
      smtp_host: item.config.smtp_host || '',
      smtp_port: item.config.smtp_port || 465,
      username: item.config.username || '',
      password: item.config.password || '',
      to_email: item.config.to_email || '',
      use_ssl: item.config.use_ssl ?? true,
    });
  };

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      const config: Record<string, unknown> = {};
      if (values.channel === 'dingtalk' || values.channel === 'wechat') {
        config.webhook_url = values.webhook_url;
      } else if (values.channel === 'email') {
        config.smtp_host = values.smtp_host;
        config.smtp_port = values.smtp_port;
        config.username = values.username;
        config.password = values.password;
        config.to_email = values.to_email;
        config.use_ssl = values.use_ssl;
      }

      if (editItem) {
        updateMut.mutate({ id: editItem.id, name: values.name, config, level: values.level, enabled: values.enabled });
      } else {
        createMut.mutate({ name: values.name, channel: values.channel, config, level: values.level, enabled: values.enabled });
      }
    });
  };

  const channel = Form.useWatch('channel', form);

  const configColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    {
      title: '渠道', dataIndex: 'channel', key: 'channel',
      render: (v: string) => <Tag color={channelColors[v]}>{channelLabels[v] ?? v}</Tag>,
    },
    {
      title: '最低级别', dataIndex: 'level', key: 'level',
      render: (v: string) => <Tag color={v === 'critical' ? 'red' : 'orange'}>{v === 'critical' ? '仅告警' : '预警+告警'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '操作', key: 'actions',
      render: (_: unknown, record: NotificationConfig) => (
        <Space>
          <Button size="small" icon={<SendOutlined />} onClick={() => testMut.mutate(record.id)} loading={testMut.isPending}>测试</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => deleteMut.mutate(record.id)}>
            <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const logColumns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', render: (v: string) => toBeijingTime(v) },
    { title: '渠道', dataIndex: 'channel', key: 'channel', render: (v: string) => <Tag color={channelColors[v]}>{channelLabels[v] ?? v}</Tag> },
    { title: '标题', dataIndex: 'title', key: 'title', ellipsis: true },
    { title: '设备', dataIndex: 'device_id', key: 'device_id', render: (v: string) => v || '-' },
    { title: '结果', dataIndex: 'success', key: 'success', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? '成功' : '失败'}</Tag> },
  ];

  return (
    <div>
      <Title level={4}><BellOutlined style={{ marginRight: 8 }} />告警通知设置</Title>

      <Tabs items={[
        {
          key: 'configs',
          label: '通知渠道',
          children: (
            <>
              <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditItem(null); form.resetFields(); setAddModalOpen(true); }}>
                  添加通知渠道
                </Button>
              </div>
              <Table columns={configColumns} dataSource={configs ?? []} rowKey="id" loading={isLoading} pagination={false} />
            </>
          ),
        },
        {
          key: 'logs',
          label: '通知历史',
          children: (
            <Table columns={logColumns} dataSource={logs ?? []} rowKey="id" pagination={{ pageSize: 20 }} />
          ),
        },
      ]} />

      <Modal
        title={editItem ? '编辑通知渠道' : '添加通知渠道'}
        open={addModalOpen || !!editItem}
        onCancel={() => { setAddModalOpen(false); setEditItem(null); form.resetFields(); }}
        onOk={handleSubmit}
        confirmLoading={createMut.isPending || updateMut.isPending}
        width={600}
      >
        <Form form={form} layout="vertical" initialValues={{ channel: 'dingtalk', level: 'warning', enabled: true }}>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: 运维告警群" />
          </Form.Item>
          <Form.Item name="channel" label="通知渠道" rules={[{ required: true }]}>
            <Select options={[
              { value: 'dingtalk', label: '钉钉 Webhook' },
              { value: 'wechat', label: '企业微信 Webhook' },
              { value: 'email', label: '邮件 SMTP' },
            ]} disabled={!!editItem} />
          </Form.Item>
          <Form.Item name="level" label="最低通知级别">
            <Select options={[
              { value: 'warning', label: '预警 + 告警（推荐）' },
              { value: 'critical', label: '仅告警（严重问题才通知）' },
            ]} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>

          {(channel === 'dingtalk' || channel === 'wechat') && (
            <Form.Item name="webhook_url" label="Webhook URL" rules={[{ required: true, message: '请输入 Webhook URL' }]}>
              <Input placeholder={channel === 'dingtalk' ? 'https://oapi.dingtalk.com/robot/send?access_token=...' : 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...'} />
            </Form.Item>
          )}

          {channel === 'email' && (
            <>
              <Form.Item name="smtp_host" label="SMTP 服务器" rules={[{ required: true }]}>
                <Input placeholder="smtp.qq.com" />
              </Form.Item>
              <Form.Item name="smtp_port" label="端口" rules={[{ required: true }]}>
                <Input type="number" placeholder="465" />
              </Form.Item>
              <Form.Item name="username" label="发件人邮箱" rules={[{ required: true }]}>
                <Input placeholder="your@email.com" />
              </Form.Item>
              <Form.Item name="password" label="密码/授权码" rules={[{ required: true }]}>
                <Input.Password placeholder="邮箱授权码" />
              </Form.Item>
              <Form.Item name="to_email" label="收件人邮箱" rules={[{ required: true }]}>
                <Input placeholder="admin@example.com" />
              </Form.Item>
              <Form.Item name="use_ssl" label="使用 SSL" valuePropName="checked">
                <Switch defaultChecked />
              </Form.Item>
            </>
          )}

          <Alert
            type="info"
            message="钉钉/企业微信：在群设置中添加自定义机器人，复制 Webhook URL。邮件：使用 SMTP 授权码（非登录密码）。"
            showIcon
          />
        </Form>
      </Modal>
    </div>
  );
};
