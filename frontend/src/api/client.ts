import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 10000,
});

// 请求拦截器：自动添加 Token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('iot_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 时跳转登录
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const path = window.location.pathname;
      if (!path.includes('/login')) {
        localStorage.removeItem('iot_token');
        localStorage.removeItem('iot_username');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default client;
