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

export interface InterviewReport {
  overall_score: number;
  dimensions: ReportDimension[];
  highlights: string[];
  improvements: string[];
  overall_comment: string;
}

export interface InterviewReportRow {
  id: number;
  target_job: string;
  duration_seconds: number;
  overall_score: number;
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
