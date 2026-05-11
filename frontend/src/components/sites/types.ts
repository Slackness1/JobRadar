export type AlertLevel = 'green' | 'yellow' | 'red' | 'unknown';

export interface TrackCount {
  track: string;
  count: number;
}

export interface SitesSummary {
  active: number;
  alerted: number;
  disabled: number;
  total_today_new: number;
  last_batch_at: string | null;
  last_batch_status: string | null;
  today_enriched_count?: number;
  today_jobs_total?: number;
  today_track_distribution?: TrackCount[];
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

export interface SitesDigest {
  text: string;
  generated_at: string | null;
}

// ─── Teacher entry (admin view) ───
export type TeacherDraftStatus = 'draft' | 'pending' | 'approved' | 'rejected';
export type TeacherSourceType = 'link' | 'ocr' | 'text';

export interface TeacherDraftRow {
  id: number;
  teacher_name: string;
  teacher_dept: string;
  source_type: TeacherSourceType;
  source_payload: string;
  parse_confidence: number;
  parsed_title: string;
  parsed_company: string;
  parsed_location: string;
  parsed_jd_summary: string;
  parsed_deadline: string;
  parsed_salary: string;
  parsed_detail_url: string;
  track: string;
  tags: string[];
  teacher_note: string;
  status: TeacherDraftStatus;
  reject_reason: string;
  submitted_at: string | null;
  created_at: string;
}

export interface TeacherDraftBucket {
  draft: number;
  pending: number;
  approved: number;
  rejected: number;
  total: number;
}

export interface TeacherSourceCount {
  source_type: string;
  count: number;
}

export interface TeacherTopTeacher {
  teacher_user_key: string;
  teacher_name: string;
  teacher_dept: string;
  count: number;
}

export interface TeacherEntrySummary {
  today: TeacherDraftBucket;
  week: TeacherDraftBucket;
  all_time: TeacherDraftBucket;
  by_source_today: TeacherSourceCount[];
  top_teachers_week: TeacherTopTeacher[];
  pending_oldest_age_minutes: number;
}
