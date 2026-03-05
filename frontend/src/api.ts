const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export interface RunRequest {
  catalog: string | null;
  mode: 'suggest' | 'agent';
  group_names?: string[];
}

export interface RunResult {
  run_id: string;
  catalog: string;
  mode: string;
  columns_scanned: number;
  tables_scanned: number;
  diff: { new_count: number; updated_count: number; deleted_count: number };
  classifications_count: number;
  label_counts: Record<string, number>;
  suggestions: Suggestion[];
  applied: AppliedAction[];
  pii_pci_candidates: number;
}

export interface Suggestion {
  column: string;
  labels: string[];
  confidence: number;
  recommended_actions: string[];
}

export interface AppliedAction {
  action: string;
  column?: string;
  table?: string;
  tag_key?: string;
  tag_value?: string;
  mask_function?: string;
  filter_function?: string;
  groups?: string[];
  error?: string;
}

export interface TrailChanges {
  new_count: number;
  updated_count: number;
  deleted_count: number;
  columns_scanned?: number;
  tables_scanned?: number;
  classifications_count?: number;
  label_counts?: Record<string, number>;
}

export interface TrailEntry {
  run_id: string;
  started_at: string;
  finished_at: string | null;
  catalogs: string;
  mode: string;
  changes_detected: TrailChanges | null;
  suggestions: Suggestion[] | null;
  applied: AppliedAction[] | null;
  notification_status: string;
}

export interface GroupInfo {
  display_name: string;
  id: string;
  member_count: number;
}

export async function getCatalogs(): Promise<string[]> {
  const data = await request<{ catalogs: string[] }>('/catalogs');
  return data.catalogs;
}

export async function getGroups(): Promise<GroupInfo[]> {
  const data = await request<{ groups: GroupInfo[] }>('/groups');
  return data.groups;
}

export async function startRun(body: RunRequest): Promise<RunResult> {
  return request<RunResult>('/run', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function getTrail(limit = 50): Promise<TrailEntry[]> {
  const data = await request<{ trail: TrailEntry[] }>(`/trail?limit=${limit}`);
  return data.trail;
}

export async function getRuns(limit = 50): Promise<TrailEntry[]> {
  const data = await request<{ runs: TrailEntry[] }>(`/runs?limit=${limit}`);
  return data.runs;
}
