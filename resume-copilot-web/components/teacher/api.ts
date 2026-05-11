// Teacher quick-entry API client.
// Backend identifies the teacher via the X-Teacher-User-Key header.
// Single-tenant demo: any non-empty key → 张老师 / 金融学院.

const TEACHER_KEY_STORAGE_KEY = 'jobradar.teacherEntry.userKey';

export function getOrCreateTeacherKey(): string {
  if (typeof window === 'undefined') return '';
  let key = window.localStorage.getItem(TEACHER_KEY_STORAGE_KEY) || '';
  if (!key) {
    key = `teacher_${crypto.randomUUID().slice(0, 8)}`;
    window.localStorage.setItem(TEACHER_KEY_STORAGE_KEY, key);
  }
  return key;
}

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const key = getOrCreateTeacherKey();
  const response = await fetch(input, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-Teacher-User-Key': key,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

export type SourceType = 'link' | 'ocr' | 'text';
export type Track = 'finance' | 'fintech' | 'other';

export interface ParsedDraft {
  title: string;
  company: string;
  location: string;
  jd_summary: string;
  deadline: string;
  salary: string;
  detail_url: string;
  suggested_track: Track;
  suggested_tags: string[];
  confidence: number;
}

export interface DraftRow {
  id: number;
  teacher_name: string;
  teacher_dept: string;
  source_type: SourceType;
  source_payload: string;
  parse_confidence: number;
  parsed_title: string;
  parsed_company: string;
  parsed_location: string;
  parsed_jd_summary: string;
  parsed_deadline: string;
  parsed_salary: string;
  parsed_detail_url: string;
  track: Track;
  tags: string[];
  teacher_note: string;
  status: 'draft' | 'pending' | 'approved' | 'rejected';
  reject_reason: string;
  submitted_at: string | null;
  created_at: string;
}

export interface TeacherStats {
  week_passed: number;
  week_pending: number;
  week_rejected: number;
  week_used: number;
  week_quota: number;
  teacher_name: string;
  teacher_dept: string;
}

export function postParse(source_type: SourceType, payload: string) {
  return requestJson<ParsedDraft[]>('/api/teacher-entry/parse', {
    method: 'POST',
    body: JSON.stringify({ source_type, payload }),
  });
}

export interface OcrParseResult {
  ocr_text: string;
  drafts: ParsedDraft[];
}

export async function postParseImage(file: File): Promise<OcrParseResult> {
  const key = getOrCreateTeacherKey();
  const form = new FormData();
  form.append('file', file);
  const response = await fetch('/api/teacher-entry/parse-image', {
    method: 'POST',
    headers: { 'X-Teacher-User-Key': key },
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return JSON.parse(await response.text()) as OcrParseResult;
}

export interface OcrBatchItem {
  filename: string;
  ocr_text: string;
  drafts: ParsedDraft[];
  error: string;
}

export interface OcrBatchResult {
  items: OcrBatchItem[];
  all_drafts: ParsedDraft[];
}

export const OCR_BATCH_MAX = 5;

export async function postParseImages(files: File[]): Promise<OcrBatchResult> {
  if (files.length === 0) throw new Error('请至少选择 1 张图');
  if (files.length > OCR_BATCH_MAX) throw new Error(`单次最多 ${OCR_BATCH_MAX} 张图`);
  const key = getOrCreateTeacherKey();
  const form = new FormData();
  for (const f of files) form.append('files', f);

  let response: Response;
  try {
    response = await fetch('/api/teacher-entry/parse-images', {
      method: 'POST',
      headers: { 'X-Teacher-User-Key': key },
      body: form,
    });
  } catch (e) {
    // 网络层断开 / TypeError "Failed to fetch" 之类
    throw new Error(`网络异常 (${(e as Error).message}) — 多半是 LLM 太慢或代理超时，重试一下`);
  }
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 240);
    // 把 status 显式带出来，方便老师反馈我们能立刻定位
    throw new Error(`HTTP ${response.status} ${response.statusText}${detail ? ' — ' + detail : ''}`);
  }
  return JSON.parse(await response.text()) as OcrBatchResult;
}

export interface CreateDraftBody {
  source_type: SourceType;
  source_payload: string;
  parsed_title: string;
  parsed_company: string;
  parsed_location: string;
  parsed_jd_summary: string;
  parsed_deadline: string;
  parsed_salary: string;
  parsed_detail_url: string;
  parse_confidence: number;
  track: Track;
  tags: string[];
  teacher_note: string;
}

export function postDraft(body: CreateDraftBody) {
  return requestJson<DraftRow>('/api/teacher-entry/drafts', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export function postSubmit(draftId: number) {
  return requestJson<{ id: number; status: string; submitted_at: string }>(
    `/api/teacher-entry/drafts/${draftId}/submit`,
    { method: 'POST' }
  );
}

export function getStats() {
  return requestJson<TeacherStats>('/api/teacher-entry/stats');
}
