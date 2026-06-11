import { useEffect, useRef, useState } from 'react';
import mqtt from 'mqtt';
import client from '../api/client';

interface TelemetryRecord {
  device_id: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export function useMqtt() {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [telemetry, setTelemetry] = useState<Record<string, TelemetryRecord>>({});
  const clientRef = useRef<mqtt.MqttClient | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // MQTT WebSocket 连接（优先走 nginx 代理 /mqtt，回退直连 9001）
  useEffect(() => {
    const isDocker = window.location.port === '80' || window.location.port === '';
    const wsUrl = isDocker
      ? `ws://${window.location.host}/mqtt`
      : `ws://${window.location.hostname}:9001`;

    const client = mqtt.connect(wsUrl, {
      clientId: `web_${Math.random().toString(16).slice(2, 10)}`,
      clean: true,
      connectTimeout: 5000,
      reconnectPeriod: 5000,
    });

    clientRef.current = client;

    client.on('connect', () => {
      setConnected(true);
      setError(null);
      client.subscribe('devices/+/telemetry', { qos: 1 }, (err) => {
        if (err) setError('MQTT 订阅失败: ' + err.message);
      });
    });

    client.on('message', (topic: string, message: Buffer) => {
      try {
        const data = JSON.parse(message.toString());
        const parts = topic.split('/');
        if (parts.length >= 2 && parts[0] === 'devices' && parts[2] === 'telemetry') {
          const deviceId = parts[1];
          setTelemetry((prev) => ({
            ...prev,
            [deviceId]: { device_id: deviceId, data, timestamp: Date.now() },
          }));
        }
      } catch { console.error('MQTT message error'); }
    });

    client.on('error', (err: Error) => {
      setError(err.message);
      setConnected(false);
    });

    client.on('close', () => {
      setConnected(false);
    });

    return () => {
      client.end(true);
    };
  }, []);

  // HTTP 轮询兜底：每 3 秒从后端 API 拉取遥测数据
  useEffect(() => {
    const poll = async () => {
      try {
        const resp = await client.get('/telemetry');
        if (resp.status === 200) {
          const data = resp.data;
          const items: TelemetryRecord[] = data.items || [];
          setTelemetry((prev) => {
            const next = { ...prev };
            for (const item of items) {
              const existing = next[item.device_id];
              // 后端 timestamp 是秒，前端是毫秒，统一转换为毫秒比较
              const itemTs = item.timestamp > 1e12 ? item.timestamp : item.timestamp * 1000;
              const existTs = existing?.timestamp ?? 0;
              if (!existing || itemTs > existTs) {
                next[item.device_id] = { ...item, timestamp: itemTs };
              }
            }
            return next;
          });
        }
      } catch { console.error('MQTT message error'); }
    };

    poll(); // 立即执行一次
    pollingRef.current = setInterval(poll, 3000);
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [connected]); // 当 MQTT 连接建立后开始轮询

  return { connected, error, telemetry };
}
