import React, { useState } from 'react';
import { Button, Modal, Table, Tag, Typography, Descriptions, Space, Popconfirm, message, Form, Input, Select } from 'antd';
import { PlusOutlined, EditOutlined, RobotOutlined, CheckCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import client from '../../api/client';
import { fetchDevices, deleteDevice, fetchShadow, updateDesired, createDevice } from '../../api/devices';
import { JsonDiff } from '../../components/JsonDiff';
import type { ColumnsType } from 'antd/es/table';
import type { Device, ShadowDocument } from '../../types';
import { relativeTime } from '../../utils/time';

const { Title } = Typography;

interface AgentSnapshot {
  agent_id: string;
  device_name: string;
  current_state: string;
}

const lifecycleColors: Record<string, string> = {
  pending: 'blue', active: 'green', suspended: 'orange', decommissioned: 'red',
};
const lifecycleLabels: Record<string, string> = {
  pending: '待激活', active: '运行中', suspended: '已禁用', decommissioned: '已退役',
};

export const DevicesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { data: devices, isLoading } = useQuery({ queryKey: ['devices'], queryFn: () => fetchDevices(), refetchInterval: 5000 });
  const { data: agents } = useQuery({ queryKey: ['agents'], queryFn: async () => (await client.get('/agents')).data as AgentSnapshot[], refetchInterval: 5000 });
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [shadow, setShadow] = useState<ShadowDocument | null>(null);
  const [desiredForm] = Form.useForm();
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addForm] = Form.useForm();
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editDevice, setEditDevice] = useState<Device | null>(null);
  const [editForm] = Form.useForm();

  const createMut = useMutation({
    mutationFn: createDevice,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setAddModalOpen(false);
      addForm.resetFields();
      message.success(`设备 ${data.id} 已创建`);
    },
    onError: (err: Error) => { message.error('创建失败: ' + err.message); },
  });

  const deleteMut = useMutation({
    mutationFn: deleteDevice,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['devices'] }); message.success('已删除'); },
    onError: (err: Error) => { message.error('删除失败: ' + err.message); },
  });

  const desiredMut = useMutation({
    mutationFn: ({ deviceId, state }: { deviceId: string; state: Record<string, unknown> }) =>
      updateDesired(deviceId, state),
    onSuccess: (data) => {
      message.success(`期望状态已更新, 版本 v${data.version}`);
      desiredForm.resetFields();
      if (selectedDevice) fetchShadow(selectedDevice.id).then(setShadow);
    },
    onError: (err: Error) => { message.error('更新期望状态失败: ' + err.message); },
  });

  const openShadow = async (device: Device) => {
    setSelectedDevice(device);
    try {
      const s = await fetchShadow(device.id);
      setShadow(s);
    } catch {
      setShadow(null);
    }
  };

  const handleSetDesired = () => {
    desiredForm.validateFields().then((values) => {
      if (!selectedDevice) return;
      const state: Record<string, unknown> = {};
      for (const item of values.items || []) {
        if (item.key) {
          const v = item.value;
          if (v === 'true') state[item.key] = true;
          else if (v === 'false') state[item.key] = false;
          else if (/^-?\d+(\.\d+)?$/.test(v)) state[item.key] = parseFloat(v);
          else state[item.key] = v;
        }
      }
      if (Object.keys(state).length > 0) {
        desiredMut.mutate({ deviceId: selectedDevice.id, state });
      }
    });
  };

  const toggleLifecycle = async (deviceId: string, enable: boolean) => {
    try {
      const endpoint = enable ? `/api/devices/${deviceId}/enable` : `/api/devices/${deviceId}/disable`;
      await client.post(endpoint);
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      message.success(enable ? '设备已激活' : '设备已禁用');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '操作失败';
      message.error(msg);
    }
  };

  const openEdit = (device: Device) => {
    setEditDevice(device);
    editForm.setFieldsValue({
      name: device.name,
      type: device.type,
      location: device.location || '',
      description: device.description || '',
    });
    setEditModalOpen(true);
  };

  const handleEdit = async () => {
    if (!editDevice) return;
    try {
      const values = await editForm.validateFields();
      await client.put(`/devices/${editDevice.id}`, values);
      queryClient.invalidateQueries({ queryKey: ['devices'] });
      setEditModalOpen(false);
      message.success('设备信息已更新');
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '更新失败';
      message.error(msg);
    }
  };

  const columns: ColumnsType<Device> = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type' },
    {
      title: '连接状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={s === 'online' ? 'green' : 'red'}>{s === 'online' ? '在线' : '离线'}</Tag>,
    },
    {
      title: '生命周期', dataIndex: 'lifecycle', key: 'lifecycle',
      render: (v: string) => <Tag color={lifecycleColors[v] ?? 'default'}>{lifecycleLabels[v] ?? v}</Tag>,
    },
    {
      title: <><RobotOutlined style={{ marginRight: 4 }} />Agent</>, key: 'agent',
      render: (_, record) => {
        const agent = agents?.find(a => a.agent_id === record.id);
        if (!agent) return <Tag color="default">-</Tag>;
        const colors: Record<string, string> = { normal: 'green', warning: 'orange', critical: 'red', offline: 'default' };
        const labels: Record<string, string> = { normal: '正常', warning: '预警', critical: '告警', offline: '离线' };
        return <Tag color={colors[agent.current_state] ?? 'default'}>{labels[agent.current_state] ?? agent.current_state}</Tag>;
      },
    },
    { title: '位置', dataIndex: 'location', key: 'location', render: (v: string) => v || '-' },
    {
      title: '最后上线', dataIndex: 'last_seen_at', key: 'last_seen_at',
      render: (v: string | null, record: Device) => (
        <span style={{ color: record.status === 'online' ? '#3f8600' : '#999' }}>
          {record.status === 'online' ? '● ' : '○ '}{relativeTime(v)}
        </span>
      ),
    },
    {
      title: '操作', key: 'actions',
      render: (_, record) => (
        <Space>
          <Button size="small" onClick={() => openShadow(record)}>影子</Button>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          {record.lifecycle === 'active' ? (
            <Button size="small" icon={<PauseCircleOutlined />} onClick={() => toggleLifecycle(record.id, false)} style={{ color: '#fa8c16' }}>
              禁用
            </Button>
          ) : record.lifecycle === 'suspended' ? (
            <Button size="small" icon={<CheckCircleOutlined />} onClick={() => toggleLifecycle(record.id, true)} style={{ color: '#3f8600' }}>
              启用
            </Button>
          ) : record.lifecycle === 'pending' ? (
            <Button size="small" icon={<CheckCircleOutlined />} onClick={() => toggleLifecycle(record.id, true)} type="primary">
              激活
            </Button>
          ) : null}
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
        <Title level={4} style={{ margin: 0 }}>设备管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { addForm.resetFields(); setAddModalOpen(true); }}>
          添加设备
        </Button>
      </div>
      <Table columns={columns} dataSource={devices ?? []} rowKey="id" loading={isLoading}
        pagination={{ pageSize: 20 }} />

      {/* 添加设备弹窗 */}
      <Modal title="添加设备" open={addModalOpen} onCancel={() => setAddModalOpen(false)}
        onOk={() => addForm.validateFields().then((values) => {
          createMut.mutate({ name: values.name, type: values.type, id: values.id || undefined, metadata: {} });
        })} confirmLoading={createMut.isPending}>
        <Form form={addForm} layout="vertical" initialValues={{ type: 'temperature_sensor' }}>
          <Form.Item name="name" label="设备名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如: 机房温度传感器-01" />
          </Form.Item>
          <Form.Item name="type" label="设备类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'temperature_sensor', label: '温度传感器' },
              { value: 'humidity_sensor', label: '湿度传感器' },
              { value: 'smart_light', label: '智能灯' },
              { value: 'smart_fan', label: '智能风扇' },
            ]} />
          </Form.Item>
          <Form.Item name="id" label="设备ID"
            help="可选，不填则自动生成。模拟器启动时需指定相同ID才能接管此设备">
            <Input placeholder="可选，如 sensor-01" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑设备弹窗 */}
      <Modal title="编辑设备" open={editModalOpen} onCancel={() => setEditModalOpen(false)}
        onOk={handleEdit}>
        <Form form={editForm} layout="vertical">
          <Form.Item name="name" label="设备名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="type" label="设备类型">
            <Select options={[
              { value: 'temperature_sensor', label: '温度传感器' },
              { value: 'humidity_sensor', label: '湿度传感器' },
              { value: 'smart_light', label: '智能灯' },
              { value: 'smart_fan', label: '智能风扇' },
            ]} />
          </Form.Item>
          <Form.Item name="location" label="位置/区域">
            <Input placeholder="例如: R1机柜" />
          </Form.Item>
          <Form.Item name="description" label="设备描述">
            <Input.TextArea placeholder="设备用途、安装位置等备注" rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 设备影子弹窗 */}
      <Modal title={`设备影子 - ${selectedDevice?.name ?? ''}`} open={!!selectedDevice} onCancel={() => setSelectedDevice(null)}
        footer={null} width={800}>
        {shadow && (
          <div>
            <Descriptions column={2} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="设备ID">{shadow.device_id}</Descriptions.Item>
              <Descriptions.Item label="版本">{shadow.version}</Descriptions.Item>
            </Descriptions>
            <Title level={5}>期望状态 vs 上报状态</Title>
            <JsonDiff reported={shadow.state.reported} desired={shadow.state.desired} />

            <div style={{ marginTop: 24, border: '1px solid #f0f0f0', padding: 16, borderRadius: 8 }}>
              <Title level={5} style={{ marginTop: 0 }}>修改期望状态</Title>
              <Form form={desiredForm} layout="inline" style={{ flexWrap: 'wrap', gap: 8 }}>
                <Form.List name="items" initialValue={[{ key: '', value: '' }]}>
                  {(fields, { add, remove }) => (
                    <div style={{ width: '100%' }}>
                      {fields.map(({ key, name, ...rest }) => (
                        <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                          <Form.Item {...rest} name={[name, 'key']} rules={[{ required: true, message: '属性名' }]}>
                            <Input placeholder="属性名, 如 target_temp" style={{ width: 160 }} />
                          </Form.Item>
                          <Form.Item {...rest} name={[name, 'value']} rules={[{ required: true, message: '值' }]}>
                            <Input placeholder="值, 如 23.0" style={{ width: 160 }} />
                          </Form.Item>
                          {fields.length > 1 && (
                            <Button size="small" danger onClick={() => remove(name)}>删除</Button>
                          )}
                        </Space>
                      ))}
                      <Button type="dashed" onClick={() => add({ key: '', value: '' })} size="small">
                        + 添加属性
                      </Button>
                      <Button type="primary" onClick={handleSetDesired} loading={desiredMut.isPending}
                        style={{ marginLeft: 16 }} size="small">
                        提交期望状态
                      </Button>
                    </div>
                  )}
                </Form.List>
              </Form>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};
