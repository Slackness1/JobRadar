// Plan-mode API client. Mirrors the four backend endpoints:
//   POST /api/resume-copilot/sessions/{id}/plan/start
//   GET  /api/resume-copilot/sessions/{id}/plan
//   POST /api/resume-copilot/sessions/{id}/plan/approve
//   POST /api/resume-copilot/sessions/{id}/plan/turn
//
// Reuses the X-Resume-User-Key + X-Guest header convention from
// components/resume-copilot/api.ts so identity / demo-session rules are
// applied consistently.

import { getOrCreateUserKey, isGuestUser } from '../api';
import type { PlanState } from './types';

async function planRequest<T>(input: string, init?: RequestInit): Promise<T> {
  const userKey = getOrCreateUserKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Resume-User-Key': userKey,
  };
  if (isGuestUser()) headers['X-Guest'] = '1';
  const res = await fetch(input, {
    ...init,
    headers: { ...headers, ...init?.headers },
  });
  if (!res.ok) {
    let detail: unknown = await res.text();
    try { detail = JSON.parse(detail as string); } catch { /* keep text */ }
    const err = new Error(`${res.status} ${res.statusText}`) as Error & { status?: number; detail?: unknown };
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return (await res.json()) as T;
}

export async function startPlan(sessionId: number): Promise<PlanState> {
  return planRequest<PlanState>(
    `/api/resume-copilot/sessions/${sessionId}/plan/start`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export async function getPlan(sessionId: number): Promise<PlanState> {
  return planRequest<PlanState>(
    `/api/resume-copilot/sessions/${sessionId}/plan`,
    { method: 'GET' },
  );
}

export async function approvePlan(sessionId: number): Promise<PlanState> {
  return planRequest<PlanState>(
    `/api/resume-copilot/sessions/${sessionId}/plan/approve`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export interface PlanTurnIn {
  content: string;
  targetItemId?: string | null;
}

export async function postPlanTurn(sessionId: number, body: PlanTurnIn): Promise<PlanState> {
  const qs = body.targetItemId ? `?target_item_id=${encodeURIComponent(body.targetItemId)}` : '';
  return planRequest<PlanState>(
    `/api/resume-copilot/sessions/${sessionId}/plan/turn${qs}`,
    { method: 'POST', body: JSON.stringify({ content: body.content }) },
  );
}
