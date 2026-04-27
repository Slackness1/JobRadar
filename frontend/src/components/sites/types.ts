export type AlertLevel = 'green' | 'yellow' | 'red' | 'unknown';

export interface SitesSummary {
  active: number;
  alerted: number;
  disabled: number;
  total_today_new: number;
  last_batch_at: string | null;
  last_batch_status: string | null;
}

export interface SiteRow {
  company: string;
  source: string;
  last_run_at: string | null;
  last_status: string | null;
  today_new: number;
  last_error_short: string;
  alert_level: AlertLevel;
}

export interface SiteRun {
  id: number;
  source: string;
  started_at: string;
  finished_at: string | null;
  status: string;
  fetched_count: number;
  new_count: number;
  error_message: string;
  duration_ms: number;
  suggested_fix: string;
}

export interface SiteRecrawlOut {
  parent_log_id: number;
  message: string;
}
