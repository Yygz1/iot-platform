import client from './client';
import type { Rule, RuleAction } from '../types';

export interface RuleCreateBody {
  name: string;
  description?: string;
  topic_filter: string;
  condition?: string | null;
  cooldown_seconds?: number;
  actions: RuleAction[];
}

export async function fetchRules(enabled?: boolean): Promise<Rule[]> {
  const { data } = await client.get('/rules', { params: enabled !== undefined ? { enabled } : {} });
  return data;
}

export async function fetchRule(id: string): Promise<Rule> {
  const { data } = await client.get(`/rules/${id}`);
  return data;
}

export async function createRule(body: RuleCreateBody): Promise<Rule> {
  const { data } = await client.post('/rules', body);
  return data;
}

export async function updateRule(id: string, body: RuleCreateBody): Promise<Rule> {
  const { data } = await client.put(`/rules/${id}`, body);
  return data;
}

export async function deleteRule(id: string): Promise<void> {
  await client.delete(`/rules/${id}`);
}

export async function toggleRule(id: string, enabled: boolean): Promise<Rule> {
  const { data } = await client.post(`/rules/${id}/toggle`, { enabled });
  return data;
}
