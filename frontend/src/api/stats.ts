import client from './client';
import type { Stats } from '../types';

export async function fetchStats(): Promise<Stats> {
  const { data } = await client.get('/stats');
  return data;
}
