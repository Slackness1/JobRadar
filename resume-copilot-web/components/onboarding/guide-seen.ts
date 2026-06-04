// 向导"已看过"状态 — 浏览器本地,不动数据库。
// key 带版本号:日后面板大改可 bump 到 V2 重新对所有人弹一次。
const GUIDE_SEEN_KEY = 'jobradar.onboarding.guideSeenV1';

export function hasSeenGuide(): boolean {
  if (typeof window === 'undefined') return true; // SSR: 视为已看过, 不自动弹
  return window.localStorage.getItem(GUIDE_SEEN_KEY) === '1';
}

export function markGuideSeen(): void {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(GUIDE_SEEN_KEY, '1');
}
