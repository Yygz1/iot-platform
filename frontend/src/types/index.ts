export interface Device {
  id: string;
  name: string;
  type: string;
  status: 'online' | 'offline';
  lifecycle: 'pending' | 'active' | 'suspended' | 'decommissioned';
  location: string | null;
  description: string | null;
  metadata: Record<string, unknown>;
  registered_at: string;
  updated_at: string;
  last_seen_at: string | null;
}

export interface ShadowDocument {
  device_id: string;
  state: {
    reported: Record<string, unknown>;
    desired: Record<string, unknown>;
  };
  metadata: {
    reported: Record<string, { timestamp: string }>;
    desired: Record<string, { timestamp: string }>;
  };
  version: number;
  timestamp: number;
}

export interface RuleAction {
  id?: number;
  action_type: 'log' | 'mqtt_publish' | 'http_webhook' | 'set_shadow_desired';
  action_config: Record<string, unknown>;
  order_index: number;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  topic_filter: string;
  condition: string | null;
  cooldown_seconds: number;
  created_at: string;
  updated_at: string;
  actions: RuleAction[];
}

export interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  device_id: string | null;
  rule_id: string | null;
  message: string;
  detail: string | null;
}

export interface LogListResponse {
  items: LogEntry[];
  total: number;
}

export interface Stats {
  device_count: number;
  online_count: number;
  rule_count: number;
  active_rule_count: number;
}

export interface Health {
  status: string;
  mqtt_connected: boolean;
}

export type ActionType = RuleAction['action_type'];
