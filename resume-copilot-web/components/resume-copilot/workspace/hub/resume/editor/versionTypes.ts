// 简历版本 + 编辑器对话 的前端持久化数据形态。
// 整组以 JSON 数组落库(见 api.ts getResumeVersions/putResumeVersions
// / getEditorConversations/putEditorConversations)。
import type { ScoreReportData } from '../../../../api';
import type { ResumeProfile } from './resumeSample';

// 一个版本 = 当前简历快照(profile)+ 该版本对应的打分报告(report,可为 null = 未打分)。
export interface ResumeVersion {
  id: string;
  label: string; // 'V1' / 'V2' …
  savedAt: string; // ISO 字符串
  profile: ResumeProfile;
  report: ScoreReportData | null;
}

// 深度优化的一个对话(独立会话)。messages 为 ChatThread 可水合的视图模型数组。
// 会话本体「无上限」全部留存;updatedAt / title 供历史浮层按时间排序 + 展示。
export interface EditorConversation {
  id: number;
  messages: unknown[];
  updatedAt?: string; // ISO;最近改动时间(历史按它倒序)
  title?: string; // 派生标题(首条用户消息;为空给序号占位)
}

// 「打开的对话 tab」上限。会话历史无上限,但同时可见/可切的 tab 仍封顶 3。
export const MAX_OPEN_EDITOR_TABS = 3;
// 兼容旧引用:历史上这个常量同时表示「会话总数上限」+「tab 上限」,
// 现已拆分(会话无上限),保留别名指向 tab 上限。
export const MAX_EDITOR_CONVERSATIONS = MAX_OPEN_EDITOR_TABS;

// 落库时附在 conversations 数组末尾的「打开态」元记录。
// 用非数字 id 让旧前端(按 typeof id === 'number' 过滤)天然跳过 → 向后兼容。
export interface EditorTabsMeta {
  __meta__: true;
  openTabIds: number[];
  activeTabId: number;
}
