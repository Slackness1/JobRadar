export type InterviewRole = 'user' | 'assistant';

export interface InterviewMessage {
  role: InterviewRole;
  content: string;
}

export interface ReportDimension {
  name: string;
  score: number;
  comment: string;
}

export interface ReportMeta {
  fallback_reason?: string;
  score_capped_for_fabrication?: boolean;
  mentor_fallback_count?: number;
  transferability?: string;
}

export interface InterviewReport {
  overall_score: number | null;   // null when LLM fallback (Day 11 B1)
  dimensions: ReportDimension[];
  highlights: string[];
  improvements: string[];
  overall_comment: string;
  _meta?: ReportMeta;
  _fabrication_suppressed?: boolean;
}

export interface InterviewReportRow {
  id: number;
  target_job: string;
  duration_seconds: number;
  overall_score: number | null;
  created_at: string;
}

export interface SavedReport {
  id: number;
  target_job: string;
  transcript: InterviewMessage[];
  report: InterviewReport;
  duration_seconds: number;
  created_at: string;
}

export type InterviewState =
  | 'interviewing'
  | 'wrapping_up'
  | 'generating_report'
  | 'report_ready';
