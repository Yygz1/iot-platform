// Token 管理工具函数（拦截器在 client.ts 中）

export function getToken(): string | null {
  return localStorage.getItem('iot_token');
}

export function getUsername(): string | null {
  return localStorage.getItem('iot_username');
}

export function logout() {
  localStorage.removeItem('iot_token');
  localStorage.removeItem('iot_username');
  window.location.href = '/login';
}
