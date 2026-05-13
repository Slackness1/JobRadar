// Wire-level types matching backend services/resume_copilot/plan.py
// Keep field names in lockstep with the Pydantic models.

export type PlanStatus =
  | 'idle'
  | 'drafting_plan'
  | 'awaiting_plan_approval'
  | 'clarifying'
  | 'reviewing'
  | 'done'
  | 'paused';

export type ItemStatus =
  | 'pending'
  | 'clarifying'
  | 'ready_to_write'
  | 'drafting'
  | 'awaiting_review'
  | 'finalized'
  | 'dropped'
  | 'blocked';

export type ItemKind =
  | 'self_intro'
  | 'education'
  | 'internship'
  | 'project'
  | 'campus_activity'
  | 'skill'
  | 'award';

export type EvidenceTagType =
  | 'metric' | 'tech' | 'role' | 'scope'
  | 'duration' | 'outcome' | 'tool' | 'verb_subject';

export interface EvidenceTag {
  type: EvidenceTagType;
  value: string;
  raw: string;
}

export interface Evidence {
  id: string;
  source: 'parsed_resume' | 'user_clarification' | 'uploaded_doc';
  text: string;
  tags: EvidenceTag[];
  citation_msg_id?: string | null;
  extracted_at?: string;
}

export type RiskKind =
  | 'overclaim' | 'missing_metric' | 'vague_verb'
  | 'tech_unverified' | 'leadership_unverified';

export interface RiskFlag {
  kind: RiskKind;
  detail: string;
  blocking: boolean;
}

export interface Draft {
  text: string;
  used_evidence_ids: string[];
  risk_flags: RiskFlag[];
  generated_at?: string;
}

export interface OpenQuestion {
  id: string;
  text: string;
  asked_at?: string;
  answered_at?: string | null;
  answer_msg_id?: string | null;
}

export interface PlanItem {
  id: string;
  kind: ItemKind;
  title: string;
  parent_id?: string | null;
  order: number;
  status: ItemStatus;
  evidence: Evidence[];
  draft: Draft | null;
  open_questions: OpenQuestion[];
  rationale?: string | null;
  last_transition_at?: string;
}

export interface PlanState {
  version: number;
  status: PlanStatus;
  current_item_id?: string | null;
  items: PlanItem[];
  replan_count: number;
  created_at?: string;
  updated_at?: string;
}
