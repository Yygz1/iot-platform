import client from './client';
import type { LogListResponse } from '../types';

export async function fetchLogs(params?: {
  level?: string;
  source?: string;
  device_id?: string;
  limit?: number;
  offset?: number;
}): Promise<LogListResponse> {
  const { data } = await client.get('/logs', { params });
  return data;
}
