export interface ResumeEducationItem {
  school: string;
  degree: string;
  major: string;
  start_date: string;
  end_date: string;
  highlights: string[];
}

export interface ResumeInternshipItem {
  company: string;
  role: string;
  start_date: string;
  end_date: string;
  bullets: string[];
}

export interface ResumeProjectItem {
  name: string;
  role: string;
  tech_stack: string[];
  bullets: string[];
}

export interface ResumeSkillsPayload {
  technical: string[];
  tools: string[];
  languages: string[];
}

export interface ResumeProfilePayload {
  basic_info: Record<string, string>;
  education: ResumeEducationItem[];
  internships: ResumeInternshipItem[];
  projects: ResumeProjectItem[];
  skills: ResumeSkillsPayload;
  languages: string[];
  awards: string[];
  candidate_summary: string;
  inferred_roles: string[];
  inferred_tracks: string[];
  // 2026-05-22 P3: 学生目标 office 区域,值域 {'hk','sg','mainland','global'}
  inferred_offices: string[];
}

export interface ResumePreferencePayload {
  preferred_tracks: string[];
  preferred_locations: string[];
  preferred_roles: string[];
  preferred_company_types: string[];
  accept_relocation: boolean;
  accept_internship: boolean;
  campus_only: boolean;
  social_ok: boolean;
  preference_notes: string;
  all_skipped: boolean;
}

export interface ResumeCopilotSession {
  id: number;
  file_name: string;
  name: string;
  status: string;
  error_message: string;
  recommendation_status: string;
  feedback_status: string;
  has_parsed_profile: boolean;
  has_confirmed_profile: boolean;
  has_preferences: boolean;
  has_recommendations: boolean;
  has_feedback: boolean;
  has_direction_analysis: boolean;
  recommendations_stale?: boolean;
  plan_status?: string;
  has_plan?: boolean;
  created_at: string | null;
  updated_at: string | null;
  finished_at: string | null;
}

export interface ResumeCopilotSessionListItem {
  id: number;
  file_name: string;
  name: string;
  status: string;
  has_recommendations: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface ResumeCopilotSessionCreatedOut {
  session_id: number;
  status: string;
  page_count?: number;
  file_size_bytes?: number;
}

export interface ResumeParsedProfileOut {
  session_id: number;
  profile: ResumeProfilePayload;
}

export interface ResumeConfirmedProfileOut {
  session_id: number;
  profile: ResumeProfilePayload;
}

export interface ResumePreferenceOut {
  session_id: number;
  preferences: ResumePreferencePayload;
}

export interface ResumeRecommendationItem {
  job_id: string;
  company: string;
  job_title: string;
  location: string;
  detail_url: string;
  objective_score: number;
  preference_score: number;
  base_job_score: number;
  company_priority_score: number;
  base_match_score: number;
  enhanced_score: number;
  final_score: number;
  matched_track_key: string;
  matched_track_label: string;
  matched_role_family: string;
  company_priority_tier: string;
  company_priority_label: string;
  need_enrichment: boolean;
  enrichment_reason: string;
  topic_key: string;
  topic_cache_status: string;
  topic_summary: string;
  quick_enrichment_profile: {
    summary: string;
    likely_orientation: string;
    likely_department: string;
    target_track_fit: string;
    uncertainty_points: string[];
    search_queries: string[];
    sources: Array<{
      title: string;
      url: string;
      snippet: string;
    }>;
  };
  used_ai: boolean;
  why_recommended: string[];
  strengths: string[];
  risks: string[];
  target_direction: string;
  tier_label?: string;       // '强匹配' | '可迁移' | '有差距'
  priority_letter?: string;  // 'A' | 'B' | 'C' | 'D'
  track_match_kind?: string; // debug
  /** 2026-05-20: 校招 / 实习 分流 — LeftRecommendRail 据此切 tab。 */
  is_internship?: boolean;
}

export interface ResumeAgentTraceItem {
  agent: string;
  message: string;
  status: string;
  tool?: string;
  step_index?: number;
  result_summary?: string;
}

export interface ResumeRecommendationResult {
  session_id: number;
  status: string;
  items: ResumeRecommendationItem[];
  agent_trace: ResumeAgentTraceItem[];
  used_ai: boolean;
  fallback_reason: string;
  error_message: string;
}

export interface ResumeFeedbackDiagnosticItem {
  title: string;
  description: string;
}

export interface ResumeFeedbackRewriteExample {
  section: string;
  original: string;
  improved: string;
  rationale: string;
}

export interface ResumeFeedbackResult {
  session_id: number;
  status: string;
  error_message: string;
  diagnostics: ResumeFeedbackDiagnosticItem[];
  rewrite_examples: ResumeFeedbackRewriteExample[];
}

export interface DirectionTierResult {
  direction: string;
  tier: 1 | 2 | 3;
  tier_label: string;
  strengths: string[];
  gaps: string[];
  transferable_from: string[];
}

export interface RewriteAuditRisk {
  kind: string;          // 'overclaim' | 'leadership_unverified' | 'tech_unverified' | 'missing_metric' | 'vague_verb'
  detail: string;
  blocking: boolean;
}

export interface RewriteOption {
  option_id: string;
  label: string;
  section: string;
  field_path: string;
  target_title: string;
  original: string[];
  improved: string[];
  rationale: string;
  warning?: string;
  audit_risks?: RewriteAuditRisk[];
  warning_severity?: 'info' | 'warn' | 'severe';
}

export interface CopilotMessage {
  id: number;
  role: 'system' | 'user' | 'assistant';
  content: string;
  rewrite_options: RewriteOption[] | null;
  applied_option_id: string | null;
  created_at: string | null;
}

export interface ApplyRewriteOut {
  profile: ResumeProfilePayload;
  applied: boolean;
}

export const EMPTY_PROFILE: ResumeProfilePayload = {
  basic_info: {},
  education: [],
  internships: [],
  projects: [],
  skills: {
    technical: [],
    tools: [],
    languages: [],
  },
  languages: [],
  awards: [],
  candidate_summary: '',
  inferred_roles: [],
  inferred_tracks: [],
  inferred_offices: [],
};

// ── Platform aggregation (Phase 3 BE + Phase 4 FE) ───────────────────────────

export interface ResumeRecommendationPlatformJobBrief {
  job_id: string;
  job_title: string;
  final_score: number;
  priority_letter: string;
  tier_label: string;
  is_internship: boolean;
  location: string;
  detail_url: string;
}

export interface ResumeRecommendationPlatform {
  company: string;
  company_priority_label: string;
  company_priority_tier: string;
  platform_score: number;
  n_jobs: number;
  n_campus: number;
  n_internship: number;
  n_xhs_insights: number;
  track_match_kind: string;
  priority_letter: string;
  tier_label: string;
  matched_track_label: string;
  top_jobs: ResumeRecommendationPlatformJobBrief[];
  all_job_ids: string[];
}

export interface ResumeRecommendationPlatformsOut {
  session_id: number;
  status: string;
  platforms: ResumeRecommendationPlatform[];
  n_total_jobs: number;
  used_ai: boolean;
  fallback_reason: string;
}

export const EMPTY_PREFERENCES: ResumePreferencePayload = {
  preferred_tracks: [],
  preferred_locations: [],
  preferred_roles: [],
  preferred_company_types: [],
  accept_relocation: false,
  accept_internship: false,
  campus_only: false,
  social_ok: false,
  preference_notes: '',
  all_skipped: false,
};
