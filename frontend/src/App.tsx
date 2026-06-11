import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AppLayout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { DevicesPage } from './pages/Devices';
import { RulesPage } from './pages/Rules';
import { LogsPage } from './pages/Logs';
import { AgentsPage } from './pages/Agents';
import { SettingsPage } from './pages/Settings';
import { LoginPage } from './pages/Login';
import { MqttBridge } from './hooks/mqttContext';
import { getToken } from './api/auth';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false, retry: 1, staleTime: 3000 },
  },
});

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getToken());

  useEffect(() => {
    // 检查 Token 是否有效
    const token = getToken();
    if (token) {
      setIsAuthenticated(true);
    }
  }, []);

  const handleLogin = (_token: string, _username: string) => {
    setIsAuthenticated(true);
  };

  if (!isAuthenticated) {
    return (
      <QueryClientProvider client={queryClient}>
        <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1677ff' } }}>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage onLogin={handleLogin} />} />
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </BrowserRouter>
        </ConfigProvider>
      </QueryClientProvider>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: '#1677ff' } }}>
        <BrowserRouter>
          <MqttBridge>
            <Routes>
              <Route element={<AppLayout />}>
                <Route index element={<Dashboard />} />
                <Route path="devices" element={<DevicesPage />} />
                <Route path="rules" element={<RulesPage />} />
                <Route path="logs" element={<LogsPage />} />
                <Route path="agents" element={<AgentsPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
              <Route path="/login" element={<Navigate to="/" replace />} />
            </Routes>
          </MqttBridge>
        </BrowserRouter>
      </ConfigProvider>
    </QueryClientProvider>
  );
};

export default App;
