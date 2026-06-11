import React, { useState, useRef, useEffect } from 'react';
import { Card, Col, Row, Table, Tag, Typography, Timeline, Statistic, Alert, Space, Descriptions, Input, Button } from 'antd';
import { RobotOutlined, AlertOutlined, CheckCircleOutlined, SwapOutlined, RiseOutlined, FallOutlined, MinusOutlined, SendOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import client from '../../api/client';
import { toBeijingTime } from '../../utils/time';

const { Title, Text } = Typography;

interface AgentSnapshot {
  agent_id: string;
  device_name: string;
  device_type: string;
  current_state: string;
  previous_state: string | null;
  entered_at: string;
  timeout_seconds: number;
}

interface AgentDecision {
  id: number;
  agent_id: string;
  device_id: string;
  state_from: string;
  state_to: string;
  trigger: string;
  timestamp: string;
}

interface CollaborationEvent {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  device_id: string;
  message: string;
}

interface TrendField {
  current: number;
  moving_avg: number;
  slope: number;
  direction: string;
  predicted: number;
  change_rate: number;
  is_anomaly: boolean;
  confidence: number;
}

interface TrendData {
  device_id: string;
  fields: Record<string, TrendField>;
}

const stateColors: Record<string, string> = {
  offline: '#999', normal: '#3f8600', warning: '#fa8c16', critical: '#cf1322',
};

const stateIcons: Record<string, React.ReactNode> = {
  offline: <CheckCircleOutlined />,
  normal: <CheckCircleOutlined />,
  warning: <AlertOutlined />,
  critical: <AlertOutlined />,
};

const directionIcon = (d: string) => {
  if (d === 'rising') return <RiseOutlined style={{ color: '#cf1322' }} />;
  if (d === 'falling') return <FallOutlined style={{ color: '#3f8600' }} />;
  return <MinusOutlined style={{ color: '#999' }} />;
};

interface ChatMessage {
  role: 'user' | 'agent';
  content: string;
  time: string;
}

export const AgentsPage: React.FC = () => {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState<Record<string, ChatMessage[]>>({});
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages, selectedAgent]);

  const sendQuestion = async (question: string) => {
    if (!selectedAgent || !question.trim()) return;
    const userMsg: ChatMessage = { role: 'user', content: question, time: new Date().toLocaleTimeString() };
    setChatMessages(prev => ({
      ...prev,
      [selectedAgent]: [...(prev[selectedAgent] ?? []), userMsg],
    }));
    setChatInput('');
    setChatLoading(true);
    try {
      const resp = await client.post(`/agents/${selectedAgent}/ask`, { question });
      const agentMsg: ChatMessage = { role: 'agent', content: resp.data.answer, time: new Date().toLocaleTimeString() };
      setChatMessages(prev => ({
        ...prev,
        [selectedAgent]: [...(prev[selectedAgent] ?? []), agentMsg],
      }));
    } catch {
      const errMsg: ChatMessage = { role: 'agent', content: '抱歉，暂时无法回答。', time: new Date().toLocaleTimeString() };
      setChatMessages(prev => ({
        ...prev,
        [selectedAgent]: [...(prev[selectedAgent] ?? []), errMsg],
      }));
    } finally {
      setChatLoading(false);
    }
  };

  const { data: agents, isLoading } = useQuery({
    queryKey: ['agents'], queryFn: async () => (await client.get('/agents')).data as AgentSnapshot[],
    refetchInterval: 3000,
  });

  const { data: decisions } = useQuery({
    queryKey: ['agent-decisions', selectedAgent],
    queryFn: async () => selectedAgent ? (await client.get(`/agents/${selectedAgent}/decisions?limit=30`)).data as AgentDecision[] : [],
    enabled: !!selectedAgent,
    refetchInterval: 3000,
  });

  const { data: trend } = useQuery({
    queryKey: ['agent-trend', selectedAgent],
    queryFn: async () => selectedAgent ? (await client.get(`/agents/${selectedAgent}/trend`)).data as TrendData : null,
    enabled: !!selectedAgent,
    refetchInterval: 5000,
  });

  const { data: collaborations } = useQuery({
    queryKey: ['agent-collaborations'],
    queryFn: async () => {
      try {
        const resp = await client.get('/logs', { params: { source: 'agent_collaboration', limit: 20 } });
        return (resp.data?.items ?? []) as CollaborationEvent[];
      } catch { return []; }
    },
    refetchInterval: 3000,
  });

  const stateCounts = (agents ?? []).reduce((acc, a) => {
    acc[a.current_state] = (acc[a.current_state] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const selectedName = agents?.find(a => a.agent_id === selectedAgent)?.device_name;

  return (
    <div>
      <Title level={4}>
        <RobotOutlined style={{ marginRight: 8 }} />
        分布式智能体
      </Title>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={12} sm={6}><Card><Statistic title="Agent 总数" value={agents?.length ?? 0} prefix={<RobotOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="NORMAL" value={stateCounts['normal'] ?? 0} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="WARNING" value={stateCounts['warning'] ?? 0} valueStyle={{ color: '#fa8c16' }} prefix={<AlertOutlined />} /></Card></Col>
        <Col xs={12} sm={6}><Card><Statistic title="CRITICAL" value={stateCounts['critical'] ?? 0} valueStyle={{ color: '#cf1322' }} prefix={<AlertOutlined />} /></Card></Col>
      </Row>

      {/* Agent 状态分布图 */}
      <Card title="智能体状态分布" size="small" style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          {(agents ?? []).map((a) => (
            <Col xs={24} sm={12} md={8} lg={6} key={a.agent_id}>
              <Card
                size="small"
                hoverable
                onClick={() => setSelectedAgent(a.agent_id)}
                style={{
                  borderLeft: `4px solid ${stateColors[a.current_state]}`,
                  background: selectedAgent === a.agent_id ? '#e6f4ff' : undefined,
                }}
              >
                <Space direction="vertical" size={2} style={{ width: '100%' }}>
                  <Text strong>{a.device_name}</Text>
                  <Space>
                    <Tag color={stateColors[a.current_state]} icon={stateIcons[a.current_state]}>
                      {a.current_state.toUpperCase()}
                    </Tag>
                    {a.previous_state && (
                      <Text type="secondary" style={{ fontSize: 12 }}>← {a.previous_state}</Text>
                    )}
                  </Space>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    进入: {toBeijingTime(a.entered_at)}
                  </Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 状态转换图 */}
      <Card title="状态转换规则" size="small" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16, flexWrap: 'wrap', padding: '16px 0' }}>
          {['offline', 'normal', 'warning', 'critical'].map((state, i) => (
            <React.Fragment key={state}>
              {i > 0 && <span style={{ fontSize: 24, color: '#999' }}>→</span>}
              <div style={{
                border: `3px solid ${stateColors[state]}`,
                borderRadius: 12,
                padding: '12px 24px',
                textAlign: 'center',
                background: (agents ?? []).some(a => a.current_state === state) ? `${stateColors[state]}15` : '#fafafa',
                minWidth: 100,
              }}>
                <div style={{ fontSize: 16, fontWeight: 'bold', color: stateColors[state] }}>{state.toUpperCase()}</div>
                <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                  {(agents ?? []).filter(a => a.current_state === state).length} 个Agent
                </div>
              </div>
            </React.Fragment>
          ))}
        </div>
      </Card>

      {collaborations && collaborations.length > 0 && (
        <Card
          title={<><SwapOutlined style={{ marginRight: 8 }} />Agent 协作动态</>}
          style={{ marginBottom: 24 }}
          size="small"
        >
          <Timeline
            items={collaborations.slice(0, 10).map((evt) => ({
              color: 'blue',
              children: (
                <div>
                  <Space>
                    <Tag color="blue">协作</Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>{toBeijingTime(evt.timestamp)}</Text>
                  </Space>
                  <br />
                  <Text style={{ fontSize: 13 }}>{evt.message}</Text>
                </div>
              ),
            }))}
          />
        </Card>
      )}

      <Title level={5}>Agent 列表</Title>
      <Table
        dataSource={agents ?? []} rowKey="agent_id" loading={isLoading}
        pagination={{ pageSize: 20 }} size="small"
        onRow={(record) => ({
          onClick: () => setSelectedAgent(record.agent_id),
          style: {
            background: selectedAgent === record.agent_id ? '#e6f4ff' : undefined,
            cursor: 'pointer',
          },
        })}
        columns={[
          { title: '名称', dataIndex: 'device_name', key: 'name' },
          { title: '类型', dataIndex: 'device_type', key: 'type' },
          {
            title: '当前状态', dataIndex: 'current_state', key: 'state',
            render: (v: string) => (
              <Tag color={stateColors[v]} icon={stateIcons[v]}>{v.toUpperCase()}</Tag>
            ),
          },
          {
            title: '上一状态', dataIndex: 'previous_state', key: 'prev',
            render: (v: string | null) => v ? <Tag>{v.toUpperCase()}</Tag> : '-',
          },
          {
            title: '进入时间', dataIndex: 'entered_at', key: 'time',
            render: (v: string) => toBeijingTime(v),
          },
        ]}
      />

      {/* 趋势分析卡片 */}
      {selectedAgent && trend && Object.keys(trend.fields).length > 0 && (
        <Card title={<><RiseOutlined style={{ marginRight: 8 }} />趋势分析 — {selectedName}</>} style={{ marginTop: 24 }} size="small">
          <Row gutter={[16, 16]}>
            {Object.entries(trend.fields).map(([field, t]) => (
              <Col xs={24} sm={12} md={8} key={field}>
                <Card size="small" style={{ borderLeft: `3px solid ${t.is_anomaly ? '#cf1322' : t.direction === 'rising' ? '#fa8c16' : '#3f8600'}` }}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Text strong>{field}</Text>
                    <Space>
                      <Text style={{ fontSize: 20 }}>{t.current}</Text>
                      {directionIcon(t.direction)}
                      <Tag color={t.direction === 'rising' ? 'red' : t.direction === 'falling' ? 'green' : 'default'}>
                        {t.direction === 'rising' ? '上升' : t.direction === 'falling' ? '下降' : '平稳'}
                      </Tag>
                      {t.is_anomaly && <Tag color="red">异常</Tag>}
                    </Space>
                    <Descriptions size="small" column={2}>
                      <Descriptions.Item label="移动均值">{t.moving_avg}</Descriptions.Item>
                      <Descriptions.Item label="变化率">{t.change_rate > 0 ? '+' : ''}{t.change_rate}</Descriptions.Item>
                      <Descriptions.Item label="预测值">{t.predicted}</Descriptions.Item>
                      <Descriptions.Item label="斜率">{t.slope}</Descriptions.Item>
                    </Descriptions>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {/* 智能问答 */}
      {selectedAgent && (
        <Card
          title={<><QuestionCircleOutlined style={{ marginRight: 8 }} />智能问答 — {selectedName}</>}
          style={{ marginTop: 24 }}
          size="small"
        >
          {/* 快捷问题 */}
          <Space wrap style={{ marginBottom: 12 }}>
            {['为什么进入当前状态？', '预测趋势？', '建议什么操作？'].map((q) => (
              <Button key={q} size="small" onClick={() => sendQuestion(q)}>{q}</Button>
            ))}
          </Space>

          {/* 对话历史 */}
          <div style={{ maxHeight: 300, overflow: 'auto', marginBottom: 12, padding: '8px 0' }}>
            {(chatMessages[selectedAgent] ?? []).length === 0 && (
              <Text type="secondary">点击上方快捷问题或输入你想问的问题</Text>
            )}
            {(chatMessages[selectedAgent] ?? []).map((msg, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                marginBottom: 8,
              }}>
                <div style={{
                  maxWidth: '80%',
                  padding: '8px 12px',
                  borderRadius: 12,
                  background: msg.role === 'user' ? '#1677ff' : '#f5f5f5',
                  color: msg.role === 'user' ? '#fff' : '#333',
                }}>
                  <div style={{ fontSize: 13 }}>{msg.content}</div>
                  <div style={{ fontSize: 10, opacity: 0.6, marginTop: 4, textAlign: 'right' }}>{msg.time}</div>
                </div>
              </div>
            ))}
            {chatLoading && (
              <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 8 }}>
                <div style={{ padding: '8px 12px', borderRadius: 12, background: '#f5f5f5' }}>
                  <Text type="secondary">思考中...</Text>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          {/* 输入框 */}
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onPressEnter={() => sendQuestion(chatInput)}
              placeholder="输入问题，如：为什么温度高？"
              disabled={chatLoading}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={() => sendQuestion(chatInput)}
              loading={chatLoading}
            />
          </Space.Compact>
        </Card>
      )}

      {selectedAgent && decisions && (
        <div style={{ marginTop: 24 }}>
          <Title level={5}>决策历史 — {selectedName}</Title>
          {decisions.length === 0 ? (
            <Alert type="info" message="暂无决策记录" showIcon />
          ) : (
            <Timeline
              items={decisions.map((d) => {
                const isCollab = d.trigger?.includes('协作') || d.trigger?.includes('cooling') || d.trigger?.includes('request');
                return {
                  color: d.state_to === 'critical' ? 'red' : d.state_to === 'warning' ? 'orange' : d.state_to === 'normal' ? 'green' : 'gray',
                  children: (
                    <div>
                      <Space>
                        <Tag color={stateColors[d.state_to]}>{d.state_from} → {d.state_to}</Tag>
                        {isCollab && <Tag color="blue" icon={<SwapOutlined />}>协作</Tag>}
                        <Text type="secondary" style={{ fontSize: 12 }}>{toBeijingTime(d.timestamp)}</Text>
                      </Space>
                      <br />
                      <Text style={{ fontSize: 13 }}>{d.trigger}</Text>
                    </div>
                  ),
                };
              })}
            />
          )}
        </div>
      )}
    </div>
  );
};
