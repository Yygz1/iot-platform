import React, { useState } from 'react';
import { Button, Table, Tag, Space, Switch, Modal, Form, Input, InputNumber, Select, Popconfirm, message, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchRules, createRule, updateRule, deleteRule, toggleRule, type RuleCreateBody } from '../../api/rules';
import type { ColumnsType } from 'antd/es/table';
import type { Rule, ActionType } from '../../types';

const { Title } = Typography;
const { TextArea } = Input;

const actionTypeOptions: { value: ActionType; label: string }[] = [
  { value: 'log', label: '日志记录' },
  { value: 'mqtt_publish', label: 'MQTT 发布' },
  { value: 'http_webhook', label: 'HTTP Webhook' },
  { value: 'set_shadow_desired', label: '设置影子期望状态' },
];

export const RulesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [form] = Form.useForm();

  const { data: rules, isLoading } = useQuery({ queryKey: ['rules'], queryFn: () => fetchRules() });

  const createMut = useMutation({
    mutationFn: (body: RuleCreateBody) => editingRule ? updateRule(editingRule.id, body) : createRule(body),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); setModalOpen(false); form.resetFields(); message.success(editingRule ? '规则已更新' : '规则已创建'); },
    onError: (err: Error) => { message.error('操作失败: ' + err.message); },
  });

  const deleteMut = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); message.success('规则已删除'); },
    onError: (err: Error) => { message.error('删除失败: ' + err.message); },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => toggleRule(id, enabled),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['rules'] }); },
    onError: (err: Error) => { message.error('切换失败: ' + err.message); },
  });

  const openCreate = () => { setEditingRule(null); form.resetFields(); setModalOpen(true); };
  const openEdit = (rule: Rule) => {
    setEditingRule(rule);
    form.setFieldsValue({
      ...rule,
      actions: rule.actions.map((a) => ({
        action_type: a.action_type,
        action_config: JSON.stringify(a.action_config, null, 2),
        order_index: a.order_index,
      })),
    });
    setModalOpen(true);
  };

  const handleSubmit = () => {
    form.validateFields().then((values) => {
      let actions;
      try {
        actions = (values.actions || []).map((a: Record<string, unknown>, i: number) => ({
          action_type: a.action_type,
          action_config: typeof a.action_config === 'string' ? JSON.parse(a.action_config as string) : a.action_config,
          order_index: i,
        }));
      } catch {
        message.error('动作配置 JSON 格式错误，请检查');
        return;
      }
      const body: RuleCreateBody = { ...values, actions };
      createMut.mutate(body);
    }).catch(() => {}); // validateFields 失败时由表单自身提示
  };

  const columns: ColumnsType<Rule> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '监听主题', dataIndex: 'topic_filter', key: 'topic_filter', render: (v: string) => <code>{v}</code> },
    { title: '条件', dataIndex: 'condition', key: 'condition', render: (v: string | null) => v ? <code>{v}</code> : '-' },
    {
      title: '启用', dataIndex: 'enabled', key: 'enabled',
      render: (v: boolean, record) => (
        <Switch checked={v} size="small" onChange={(checked) => toggleMut.mutate({ id: record.id, enabled: checked })} />
      ),
    },
    { title: '冷却(秒)', dataIndex: 'cooldown_seconds', key: 'cooldown_seconds' },
    {
      title: '动作数', key: 'actions_count',
      render: (_, record) => <Tag>{record.actions?.length ?? 0} 个动作</Tag>,
    },
    {
      title: '操作', key: 'actions',
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除？" onConfirm={() => deleteMut.mutate(record.id)}>
            <Button size="small" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>规则引擎</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增规则</Button>
      </div>

      <Table columns={columns} dataSource={rules ?? []} rowKey="id" loading={isLoading}
        pagination={{ pageSize: 20 }} />

      <Modal title={editingRule ? '编辑规则' : '新增规则'} open={modalOpen} onCancel={() => setModalOpen(false)}
        onOk={handleSubmit} width={800} confirmLoading={createMut.isPending}>
        <Form form={form} layout="vertical" initialValues={{ cooldown_seconds: 60, actions: [] }}>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="description" label="描述"><TextArea rows={2} /></Form.Item>
          <Form.Item name="topic_filter" label="监听主题" rules={[{ required: true }]}
            help="支持 MQTT 通配符 + 和 #"><Input placeholder="devices/+/telemetry" /></Form.Item>
          <Form.Item name="condition" label="条件表达式"
            help="例如: payload.temperature > 30"><Input placeholder="payload.temperature > 30" /></Form.Item>
          <Form.Item name="cooldown_seconds" label="冷却时间(秒)"><InputNumber min={0} max={3600} /></Form.Item>
          <Form.List name="actions">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...rest }) => (
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                    <Form.Item {...rest} name={[name, 'action_type']} rules={[{ required: true }]}>
                      <Select options={actionTypeOptions} style={{ width: 150 }} placeholder="动作类型" />
                    </Form.Item>
                    <Form.Item {...rest} name={[name, 'action_config']} rules={[{ required: true }]}
                      help='JSON 配置，如: {"level":"warning","topic":"alerts/high_temp"}'>
                      <TextArea rows={3} style={{ width: 350, fontFamily: 'monospace', fontSize: 12 }}
                        placeholder='{"level":"warning"}' />
                    </Form.Item>
                    <Button danger onClick={() => remove(name)}>删除</Button>
                  </Space>
                ))}
                <Button type="dashed" onClick={() => add({ action_type: 'log', action_config: '{}' })} block>
                  + 添加动作
                </Button>
              </>
            )}
          </Form.List>
        </Form>
      </Modal>
    </div>
  );
};
