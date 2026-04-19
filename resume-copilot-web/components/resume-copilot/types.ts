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
  rule_score: number;
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
};

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
