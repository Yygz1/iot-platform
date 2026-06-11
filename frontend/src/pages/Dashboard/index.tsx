import React from 'react';
import { Card, Col, Row, Space, Statistic, Table, Tag, Typography, Progress } from 'antd';
import { useQuery } from '@tanstack/react-query';
import client from '../../api/client';
import { fetchStats } from '../../api/stats';
import { fetchDevices } from '../../api/devices';
import { fetchLogs } from '../../api/logs';
import { useMqttContext } from '../../hooks/mqttContext';
import type { ColumnsType } from 'antd/es/table';
import type { Device, LogEntry } from '../../types';
import { toBeijingTime, relativeTime } from '../../utils/time';
import { RobotOutlined, AlertOutlined, CheckCircleOutlined, ApiOutlined } from '@ant-design/icons';

const { Title, Text } = Typography;

interface AgentSnapshot {
  agent_id: string;
  device_name: string;
  current_state: string;
}

const deviceColumns: ColumnsType<Device> = [
  { title: '名称', dataIndex: 'name', key: 'name' },
  { title: '类型', dataIndex: 'type', key: 'type' },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    render: (s: string) => <Tag color={s === 'online' ? 'green' : 'red'}>{s === 'online' ? '在线' : '离线'}</Tag>,
  },
  {
    title: '最后上线', dataIndex: 'last_seen_at', key: 'last_seen_at',
    render: (v: string | null, record: Device) => (
      <span style={{ color: record.status === 'online' ? '#3f8600' : '#999' }}>
        {record.status === 'online' ? '● ' : '○ '}{relativeTime(v)}
      </span>
    ),
  },
];

const logColumns: ColumnsType<LogEntry> = [
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180, render: (v: string) => toBeijingTime(v) },
  {
    title: '级别',
    dataIndex: 'level',
    key: 'level',
    width: 80,
    render: (l: string) => <Tag color={l === 'error' ? 'red' : l === 'warning' ? 'orange' : 'blue'}>{l}</Tag>,
  },
  { title: '来源', dataIndex: 'source', key: 'source', width: 100 },
  { title: '消息', dataIndex: 'message', key: 'message' },
];

const stateColors: Record<string, string> = {
  offline: '#999', normal: '#3f8600', warning: '#fa8c16', critical: '#cf1322',
};

const stateLabels: Record<string, string> = {
  offline: '离线', normal: '正常', warning: '预警', critical: '告警',
};

export const Dashboard: React.FC = () => {
  const { data: stats } = useQuery({ queryKey: ['stats'], queryFn: fetchStats, refetchInterval: 5000 });
  const { data: devices } = useQuery({ queryKey: ['devices'], queryFn: () => fetchDevices(), refetchInterval: 5000 });
  const { data: logs } = useQuery({ queryKey: ['logs-recent'], queryFn: () => fetchLogs({ limit: 50 }), refetchInterval: 5000 });
  const { data: agents } = useQuery({ queryKey: ['agents'], queryFn: async () => (await client.get('/agents')).data as AgentSnapshot[], refetchInterval: 5000 });
  const { connected: mqttConnected, telemetry: liveTelemetry } = useMqttContext();

  const onlineCount = stats?.online_count ?? 0;
  const totalCount = stats?.device_count ?? 0;
  const offlineCount = totalCount - onlineCount;
  const onlineRate = totalCount > 0 ? Math.round((onlineCount / totalCount) * 100) : 0;

  const agentStateCounts = (agents ?? []).reduce((acc, a) => {
    acc[a.current_state] = (acc[a.current_state] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div>
      {/* 监控状态提示栏 */}
      <div style={{
        background: mqttConnected ? 'linear-gradient(135deg, #f6ffed 0%, #e6f7ff 100%)' : 'linear-gradient(135deg, #fff2f0 0%, #fff1f0 100%)',
        border: `1px solid ${mqttConnected ? '#b7eb8f' : '#ffccc7'}`,
        borderRadius: 12, padding: '16px 24px', marginBottom: 24,
      }}>
        <Row align="middle" gutter={24}>
          <Col flex="auto">
            <Space size="large">
              <Tag color={mqttConnected ? 'green' : 'red'} style={{ fontSize: 14, padding: '4px 12px' }}>
                {mqttConnected ? '● 系统在线' : '● 系统离线'}
              </Tag>
              <Text>
                <ApiOutlined style={{ marginRight: 4 }} />
                <b>{totalCount}</b> 台设备已注册，
                <b style={{ color: '#3f8600' }}>{onlineCount}</b> 台在线监控中，
                <b style={{ color: '#cf1322' }}>{offlineCount}</b> 台离线
              </Text>
              <Text>
                <RobotOutlined style={{ marginRight: 4 }} />
                智能体：
                <Tag color="green" style={{ marginLeft: 4 }}>正常 {agentStateCounts['normal'] ?? 0}</Tag>
                <Tag color="orange">预警 {agentStateCounts['warning'] ?? 0}</Tag>
                <Tag color="red">告警 {agentStateCounts['critical'] ?? 0}</Tag>
              </Text>
            </Space>
          </Col>
          <Col>
            <Progress
              type="circle"
              percent={onlineRate}
              size={64}
              format={(p) => <span style={{ fontSize: 16, fontWeight: 'bold' }}>{p}%</span>}
              strokeColor={onlineRate > 80 ? '#3f8600' : onlineRate > 50 ? '#fa8c16' : '#cf1322'}
            />
            <div style={{ textAlign: 'center', fontSize: 12, color: '#999', marginTop: 4 }}>在线率</div>
          </Col>
        </Row>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic title="设备总数" value={totalCount} prefix={<ApiOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic title="在线设备" value={onlineCount} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic title="智能体" value={agents?.length ?? 0} prefix={<RobotOutlined />} />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card hoverable>
            <Statistic title="告警数" value={agentStateCounts['critical'] ?? 0} valueStyle={{ color: '#cf1322' }} prefix={<AlertOutlined />} />
          </Card>
        </Col>
      </Row>

      {/* 实时遥测 */}
      <Title level={5}>
        实时遥测
        <Tag color={mqttConnected ? 'green' : 'red'} style={{ marginLeft: 8 }}>
          {mqttConnected ? 'WebSocket 实时' : 'HTTP 轮询'}
        </Tag>
      </Title>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {Object.entries(liveTelemetry).slice(0, 6).map(([deviceId, record]) => {
          const agent = agents?.find(a => a.agent_id === deviceId);
          const state = agent?.current_state ?? 'normal';
          return (
            <Col key={deviceId} xs={24} sm={12} md={8} lg={6}>
              <Card
                size="small"
                title={<Space><span>{agent?.device_name ?? deviceId}</span><Tag color={stateColors[state]} style={{ fontSize: 11 }}>{stateLabels[state] ?? state}</Tag></Space>}
                style={{ borderLeft: `4px solid ${stateColors[state]}` }}
              >
                {Object.entries(record.data).map(([key, value]) => (
                  <div key={key} style={{ marginBottom: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{key}</Text>
                    <br />
                    <Text strong style={{ fontSize: 18 }}>
                      {typeof value === 'number' ? value.toFixed(1) : String(value)}
                    </Text>
                  </div>
                ))}
              </Card>
            </Col>
          );
        })}
        {Object.keys(liveTelemetry).length === 0 && (
          <Col span={24}><Text type="secondary">等待设备上线...</Text></Col>
        )}
      </Row>

      {/* 设备列表 */}
      <Title level={5}>设备列表</Title>
      <Table columns={deviceColumns} dataSource={devices ?? []} rowKey="id" size="small" style={{ marginBottom: 24 }}
        pagination={false} />

      {/* 最近事件 */}
      <Title level={5}>最近事件</Title>
      <Table columns={logColumns} dataSource={logs?.items ?? []} rowKey="id" size="small"
        pagination={{ pageSize: 10 }} />
    </div>
  );
};
