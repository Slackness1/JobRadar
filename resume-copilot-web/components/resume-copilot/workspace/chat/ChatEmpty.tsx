'use client';

/**
 * ChatEmpty — P1 chat 空状态 (MiddleChatPane, messages.length === 0).
 *
 * 设计参考 `hifi-ws-chat.jsx::HFChatEmpty`.
 *
 * 学生上传简历 + 跑完推荐但还没主动发问时, 不再显单行 "从输入框发起问题",
 * 而是给一个有名字打招呼 + 4 张引导卡的 2x2 grid, 让学生知道能问什么.
 *
 * Quick-pick 点击 → `onQuickPick(title)` 回调到 MiddleChatPane 现有 sendChatMessage.
 */

import { I } from '@/components/hifi/hifi-primitives';
import { AIOrb } from '@/components/interview/primitives';

export interface ChatEmptyCard {
  key: string;
  icon: React.ReactNode;
  title: string;
  sub: string;
  /** prompt 实际发给 chat — 默认 = title. */
  prompt?: string;
}

const DEFAULT_CARDS: ChatEmptyCard[] = [
  {
    key: 'explain-score',
    icon: I.search(16),
    title: '解释推荐分数',
    sub: '为什么 XX 排在第一? 它跟我的简历哪几条命中?',
    prompt: '解释一下推荐列表的分数, 第一家为什么排前面?',
  },
  {
    key: 'weak-bullets',
    icon: I.edit(16),
    title: '挑可加强的 bullet',
    sub: '看看我实习经历哪几条偏弱 / 量化缺失',
    prompt: '帮我看下实习经历里哪几条 bullet 偏弱, 哪些需要补量化?',
  },
  {
    key: 'customize-company',
    icon: I.target(16),
    title: '针对一家公司定制',
    sub: '会切到 Coach mode 跟 AI 做 STAR 拆解',
    prompt: '我想针对一家公司定制简历, 请帮我开 Coach 模式',
  },
  {
    key: 'peer-intel',
    icon: I.book(16),
    title: '看同辈情报',
    sub: '展开任意公司卡 → 点小红书角标查 verbatim quote',
    prompt: '怎么查同辈情报? 哪几家有同辈洞察?',
  },
];

export interface ChatEmptyProps {
  studentName?: string;
  /** 简历摘要文案 (例如 "易方达 / 中信 / SAIF MF"); 不传则默认 "你的简历". */
  resumeSubtitle?: string;
  /** 今天跑的公司卡数. 缺省时不显示该 inline 数字. */
  companyCount?: number | null;
  /** 4 张卡, 默认走 DEFAULT_CARDS. */
  cards?: ChatEmptyCard[];
  /** 学生点卡 → 发到 chat. */
  onQuickPick: (prompt: string) => void;
  /** Fix-2a #4 (2026-05-27): "针对一家公司定制" 卡走 Coach 入口而非 chat
   *  prompt — 不传时 fallback 到 onQuickPick (老行为). */
  onEnterCoach?: () => void;
  /** 是否可发问 (canChat). false 时卡按钮 disabled — 例如 demo 或 feedback 还在跑. */
  disabled?: boolean;
}

function greetingByHour(): string {
  if (typeof window === 'undefined') return '你好';
  const h = new Date().getHours();
  if (h < 6) return '夜深了';
  if (h < 11) return '早上好';
  if (h < 14) return '中午好';
  if (h < 18) return '下午好';
  return '晚上好';
}

export function ChatEmpty({
  studentName,
  resumeSubtitle,
  companyCount,
  cards = DEFAULT_CARDS,
  onQuickPick,
  onEnterCoach,
  disabled = false,
}: ChatEmptyProps) {
  const greeting = greetingByHour();
  const displayName = (studentName || '').trim();
  return (
    <div
      className="workspace-hifi__chat-empty-v2"
      role="region"
      aria-label="Chat 引导"
      style={{
        // AIOrb 需要 token 在 scope 内 (workspace 默认没声明).
        ['--terracotta' as string]: '#c96442',
        ['--terracotta-strong' as string]: '#a84f34',
        ['--border' as string]: '#e8e6dc',
        ['--border-strong' as string]: '#d1cfc5',
      }}
    >
      <div className="workspace-hifi__chat-empty-v2-head">
        <div className="workspace-hifi__chat-empty-v2-orb" aria-hidden>
          <AIOrb size={28} />
        </div>
        <span className="hf-overline workspace-hifi__chat-empty-v2-overline">
          Resume Copilot
        </span>
      </div>
      <h2 className="workspace-hifi__chat-empty-v2-h2">
        {greeting}{displayName ? `, ${displayName}` : ''}。
      </h2>
      <p className="workspace-hifi__chat-empty-v2-sub">
        我读了你的简历{resumeSubtitle ? ` (${resumeSubtitle})` : ''}
        {typeof companyCount === 'number' && companyCount > 0 ? (
          <>, 也跑完了今天的 <b>{companyCount} 张公司卡</b></>
        ) : null}
        。从哪里开始?
      </p>

      <div className="workspace-hifi__chat-empty-v2-grid">
        {cards.map((c) => (
          <button
            key={c.key}
            type="button"
            className="workspace-hifi__chat-empty-v2-card"
            onClick={() => {
              // Fix-2a #4: "customize-company" 卡走 Coach 入口而非 chat
              if (c.key === 'customize-company' && onEnterCoach) {
                onEnterCoach();
                return;
              }
              onQuickPick(c.prompt || c.title);
            }}
            disabled={disabled}
          >
            <div className="workspace-hifi__chat-empty-v2-card-head">
              <span className="workspace-hifi__chat-empty-v2-card-icon" aria-hidden>
                {c.icon}
              </span>
              <span className="workspace-hifi__chat-empty-v2-card-title">
                {c.title}
              </span>
            </div>
            <div className="workspace-hifi__chat-empty-v2-card-sub">{c.sub}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
