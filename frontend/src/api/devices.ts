import client from './client';
import type { Device, ShadowDocument } from '../types';

export async function fetchDevices(params?: { status?: string; type?: string }): Promise<Device[]> {
  const { data } = await client.get('/devices', { params });
  return data;
}

export async function fetchDevice(id: string): Promise<Device> {
  const { data } = await client.get(`/devices/${id}`);
  return data;
}

export async function createDevice(body: { name: string; type: string; id?: string; metadata?: Record<string, unknown> }): Promise<Device> {
  const { data } = await client.post('/devices', body);
  return data;
}

export async function deleteDevice(id: string): Promise<void> {
  await client.delete(`/devices/${id}`);
}

export async function fetchShadow(deviceId: string): Promise<ShadowDocument> {
  const { data } = await client.get(`/devices/${deviceId}/shadow`);
  return data;
}

export async function updateDesired(deviceId: string, state: Record<string, unknown>): Promise<{ version: number; delta: Record<string, unknown> }> {
  const { data } = await client.put(`/devices/${deviceId}/shadow/desired`, { state });
  return data;
}
