// 简历打分结果的本地短缓存 ——
// Hub 对话里跑「简历优化」技能时已打过一次 LLM 打分(给结果卡填真实现状分),
// 紧接着点开打分报告页又会再打一次, 重复烧 OpenCode 额度(与学生流量共用)。
// 这里把技能时取到的分按会话缓存 ~10 分钟, 报告页优先复用, 避免一次交互打两遍 LLM。
import type { ScoreReportData } from '../../api';

const TTL_MS = 10 * 60 * 1000;
const key = (sid: number) => `hub-score-cache:${sid}`;

interface Cached {
  report: ScoreReportData;
  ts: number;
}

export function cacheScoreReport(sid: number, report: ScoreReportData): void {
  if (typeof window === 'undefined' || !sid) return;
  try {
    window.localStorage.setItem(key(sid), JSON.stringify({ report, ts: Date.now() }));
  } catch {
    /* 配额满 / 隐私模式 → 静默, 不阻断 */
  }
}

export function readFreshScoreReport(sid: number): ScoreReportData | null {
  if (typeof window === 'undefined' || !sid) return null;
  try {
    const raw = window.localStorage.getItem(key(sid));
    if (!raw) return null;
    const c = JSON.parse(raw) as Cached;
    if (!c?.report || typeof c.ts !== 'number') return null;
    if (Date.now() - c.ts > TTL_MS) return null;
    return c.report;
  } catch {
    return null;
  }
}
