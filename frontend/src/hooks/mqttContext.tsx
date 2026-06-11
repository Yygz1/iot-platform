import React, { createContext, useContext } from 'react';
import { useMqtt } from './useMqtt';

interface MqttContextValue {
  connected: boolean;
  error: string | null;
  telemetry: Record<string, { device_id: string; data: Record<string, unknown>; timestamp: number }>;
}

const MqttContext = createContext<MqttContextValue>({ connected: false, error: null, telemetry: {} });

export const useMqttContext = () => useContext(MqttContext);

export const MqttBridge: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const mqtt = useMqtt();
  return <MqttContext.Provider value={mqtt}>{children}</MqttContext.Provider>;
};
