import React from 'react';
import { Row, Col, Card, Typography } from 'antd';

const { Text } = Typography;

interface Props {
  reported: Record<string, unknown>;
  desired: Record<string, unknown>;
}

export const JsonDiff: React.FC<Props> = ({ reported, desired }) => {
  const allKeys = new Set([...Object.keys(reported), ...Object.keys(desired)]);

  const renderValue = (key: string, val: unknown, isDesired: boolean) => {
    const reportedVal = reported[key];
    const desiredVal = desired[key];
    const isDiff = isDesired
      ? JSON.stringify(desiredVal) !== JSON.stringify(reportedVal)
      : JSON.stringify(reportedVal) !== JSON.stringify(desiredVal);
    const hasDesired = key in desired;
    const hasReported = key in reported;

    let color = '#000';
    if (hasDesired && hasReported && isDiff) color = '#fa8c16';
    else if (hasDesired && !hasReported) color = '#1677ff';
    else if (!hasDesired && hasReported) color = '#52c41a';

    return <Text style={{ color, fontFamily: 'monospace', fontSize: 13 }}>{JSON.stringify(val)}</Text>;
  };

  return (
    <Row gutter={16}>
      <Col span={12}>
        <Card title="上报状态 (Reported)" size="small" style={{ background: '#f6ffed' }}>
          {[...allKeys].filter((k) => !k.startsWith('_')).map((key) => (
            <div key={key} style={{ marginBottom: 4 }}>
              <Text strong>{key}: </Text>
              {renderValue(key, reported[key], false)}
            </div>
          ))}
        </Card>
      </Col>
      <Col span={12}>
        <Card title="期望状态 (Desired)" size="small" style={{ background: '#fff7e6' }}>
          {[...allKeys].filter((k) => !k.startsWith('_')).map((key) => (
            <div key={key} style={{ marginBottom: 4 }}>
              <Text strong>{key}: </Text>
              {renderValue(key, desired[key], true)}
            </div>
          ))}
        </Card>
      </Col>
    </Row>
  );
};
