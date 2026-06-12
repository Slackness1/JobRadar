'use client';

/**
 * ResumeCanvas — 简历优化的「打分面板 + 全屏编辑器浮层」一体组件.
 *
 * 这是「无感嵌入」的核心: 同一份逻辑(草稿持久化 / 翻译 / 真简历加载 / 编辑器浮层)
 * 既给 Hub 右侧画布槽内嵌用(active==='resume' → 保留左对话, 不再瞬移走全屏页),
 * 也给 /resume-copilot/hub-score 深链兜底页复用. 区别只是外层壳:
 *   - 画布槽: 直接撑满 500px 槽位(height:100%), onClose 收回全宽对话.
 *   - 深链页: 外面套一层右对齐全屏壳(见 hub-score/page.tsx).
 *
 * 状态全在这里持有(从原 hub-score/page.tsx 的 Inner() 原样搬来):
 *   - zh/en 双语 + lang + translate(B5 调真后端翻译, 已翻则只切语言)
 *   - template/layout/hidden 共享态(打分预览 + 全屏编辑器同源)
 *   - editor_draft 持久化: localStorage 即时回显 + 后端 PUT 防抖落库(跨设备真源)
 *
 * 编辑器浮层是 position:fixed inset:0 zIndex:60 —— 不管挂在槽里还是页里都盖满视口.
 */

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ResumeScorePanel } from './resume/ResumeScorePanel';
import { ResumeEditorOverlay } from './resume/editor/ResumeEditorOverlay';
import {
  SAMPLE_PROFILE,
  DEFAULT_LAYOUT,
  profilePayloadToResumeProfile,
  type LayoutState,
  type Lang,
  type ResumeProfile,
} from './resume/editor/resumeSample';
import {
  getEditorDraft,
  getResumeCopilotConfirmedProfile,
  getResumeCopilotParsedProfile,
  putEditorDraft,
  translateProfile,
} from '../../api';

// ── 简历编辑器草稿持久化(跨设备)──────────────────────────────────────────────
// 编辑器改的是渲染模型 + 模板/布局/隐藏项, 后端 confirmed-profile 装不下这套, 单独
// 落 editor_draft_json 列。换设备/浏览器也能恢复上次编辑。localStorage 仍当即时缓存:
// 加载时本地优先即时回显, 同时拉后端真源对齐; 保存时本地即写 + 防抖 PUT 落库。
const draftKey = (sid: number) => `hub-resume-draft:${sid}`;

interface EditorDraft {
  profile: ResumeProfile;
  template: string;
  layout: LayoutState;
  hidden: string[];
}

function loadDraft(sid: number): EditorDraft | null {
  if (typeof window === 'undefined' || !sid) return null;
  try {
    const raw = window.localStorage.getItem(draftKey(sid));
    return raw ? (JSON.parse(raw) as EditorDraft) : null;
  } catch {
    return null;
  }
}

function saveDraft(sid: number, d: EditorDraft): void {
  if (typeof window === 'undefined' || !sid) return;
  try {
    window.localStorage.setItem(draftKey(sid), JSON.stringify(d));
  } catch {
    /* 配额满/隐私模式 → 静默, 不阻断编辑 */
  }
}

export interface ResumeCanvasProps {
  sessionId: number;
  /** 无 session 时渲染原型样例,供独立目测 */
  mock?: boolean;
  /** 槽内嵌用: 收回全宽对话(深链页不传则面板不显示 ✕)。 */
  onClose?: () => void;
  /**
   * embedded=true: Hub 右侧画布槽内嵌 —— 只渲染「打分 + 小预览」面板, **不**把展开的
   * 大编辑器塞进对话(用户明确只要小预览)。点「展开编辑器/深度优化」→ 跳独立编辑页。
   * embedded=false(默认): 独立 /hub-score 页 —— 编辑器作右侧浮层就地展开。
   */
  embedded?: boolean;
  /** 独立页用: ?editor=1 进来时直接展开编辑器(embedded 模式忽略)。 */
  initialEditorOpen?: boolean;
}

export default function ResumeCanvas({
  sessionId,
  mock = false,
  onClose,
  embedded = false,
  initialEditorOpen = false,
}: ResumeCanvasProps) {
  const router = useRouter();
  const [editorOpen, setEditorOpen] = useState(!embedded && initialEditorOpen);
  // 「展开编辑器/深度优化」: 内嵌态不就地展开大编辑器(用户只要对话里看小预览),
  // 改为跳独立编辑页; 独立页态就地展开浮层。
  const openEditor = () => {
    if (embedded) {
      router.push(`/resume-copilot/hub-score?session=${sessionId}&editor=1`);
    } else {
      setEditorOpen(true);
    }
  };
  // 双语简历:zh 源 + en(翻译后填充)+ 当前语言。模板/布局/显隐为共享态(下方)。
  // 草稿持久化只存 zh 源(en 是按需翻译的派生, 不落草稿); 真实 session 先看本地
  // 草稿、无草稿再拉后端 confirmed(回退 parsed)profile —— 都写进 zh。
  const [zh, setZh] = useState<ResumeProfile>(SAMPLE_PROFILE);
  const [en, setEn] = useState<ResumeProfile | null>(null);
  const [lang, setLang] = useState<Lang>('zh');
  const activeProfile = lang === 'en' && en ? en : zh;
  const setActiveProfile = (p: ResumeProfile) => (lang === 'en' ? setEn(p) : setZh(p));
  // B5: 调真后端翻译。已翻过则直接切语言;出错留中文不崩。
  const [translating, setTranslating] = useState(false);
  const handleTranslate = async () => {
    if (en) {
      setLang('en');
      return;
    } // 已翻过 → 只切语言,不重复调用
    setTranslating(true);
    try {
      const out = await translateProfile(zh);
      setEn(out.profile as ResumeProfile);
      setLang('en');
    } catch {
      setLang('zh'); // 失败留在中文(en 仍为 null)
    } finally {
      setTranslating(false);
    }
  };
  const [template, setTemplate] = useState<string>('classic');
  const [layout, setLayout] = useState<LayoutState>(DEFAULT_LAYOUT);
  const [hidden, setHidden] = useState<Set<string>>(() => new Set());
  const loadedRef = useRef(false); // 初次加载完成前不写草稿(防覆盖)
  const putTimer = useRef<ReturnType<typeof setTimeout> | null>(null); // 落库防抖

  // 真实会话:本地缓存即时回显 + 后端草稿(跨设备真源)对齐; 都无草稿再拉真简历。
  useEffect(() => {
    if (mock || !sessionId) {
      loadedRef.current = true;
      return;
    }
    let cancelled = false;
    const applyDraft = (d: EditorDraft) => {
      setZh(d.profile);
      setTemplate(d.template);
      setLayout(d.layout);
      setHidden(new Set(d.hidden));
    };
    const fetchProfileIntoZh = () =>
      getResumeCopilotConfirmedProfile(sessionId)
        .then((r) => {
          if (!cancelled && r?.profile) setZh(profilePayloadToResumeProfile(r.profile));
        })
        .catch(() =>
          getResumeCopilotParsedProfile(sessionId)
            .then((r) => {
              if (!cancelled && r?.profile) setZh(profilePayloadToResumeProfile(r.profile));
            })
            .catch(() => {
              /* 都拿不到则保持示例,不致崩 */
            }),
        );
    const local = loadDraft(sessionId);
    if (local) {
      // 本地缓存即时回显(微任务避免 effect 内同步 setState 级联渲染 lint)。
      Promise.resolve().then(() => {
        if (!cancelled) applyDraft(local);
      });
    }
    // 后端草稿是跨设备真源:有则覆盖本地; 无草稿且本地也无 → 拉真简历 profile。
    getEditorDraft(sessionId)
      .then((r) => {
        if (cancelled) return undefined;
        if (r?.draft) {
          applyDraft({
            profile: r.draft.profile as ResumeProfile,
            template: r.draft.template,
            layout: r.draft.layout as LayoutState,
            hidden: r.draft.hidden ?? [],
          });
          return undefined;
        }
        return local ? undefined : fetchProfileIntoZh();
      })
      .catch(() => (cancelled || local ? undefined : fetchProfileIntoZh()))
      .finally(() => {
        if (!cancelled) loadedRef.current = true;
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, mock]);

  // 自动保存草稿:任何编辑落本地即写(刷新不丢)+ 防抖 PUT 落库(跨设备恢复)。
  useEffect(() => {
    if (mock || !sessionId || !loadedRef.current) return;
    const d: EditorDraft = { profile: zh, template, layout, hidden: [...hidden] };
    saveDraft(sessionId, d);
    if (putTimer.current) clearTimeout(putTimer.current);
    putTimer.current = setTimeout(() => {
      putEditorDraft(sessionId, d).catch(() => {
        /* 网络/未登录态 → 留本地缓存, 不阻断编辑 */
      });
    }, 1500);
  }, [zh, template, layout, hidden, sessionId, mock]);

  // 保存按钮:已自动存, 这里立即 flush 本地 + 落库(反馈由编辑器本地给)。
  const onSaveDraft = () => {
    if (mock || !sessionId) return;
    const d: EditorDraft = { profile: zh, template, layout, hidden: [...hidden] };
    saveDraft(sessionId, d);
    putEditorDraft(sessionId, d).catch(() => {
      /* 落库失败留本地 */
    });
  };

  const toggleHidden = (id: string) =>
    setHidden((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  if (!mock && !sessionId) {
    return (
      <div style={{ padding: 40, fontFamily: 'system-ui' }}>缺少 ?session=&lt;id&gt; 或 ?mock=1</div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0, background: 'var(--ivory)' }}>
      <ResumeScorePanel
        sessionId={sessionId}
        mock={mock}
        onExpandEditor={openEditor}
        onClose={onClose}
        profile={activeProfile}
        template={template}
        onTemplate={setTemplate}
        layout={layout}
        hidden={hidden}
        lang={lang}
        onLang={setLang}
        onTranslate={handleTranslate}
        translating={translating}
      />
      {!embedded && editorOpen && (
        <ResumeEditorOverlay
          sessionId={sessionId}
          mock={mock}
          onClose={() => {
            // 「返回主工作台」要名实相符: 从 Hub 跳来(?editor=1)的编辑器, 宿主是
            // 左空白的深链兜底页 —— 只关浮层会把人留在空白页上回不去, 必须真路由
            // 回 /hub。本页自己展开的浮层(无 editor=1)才是就地关闭。
            if (initialEditorOpen && !mock && sessionId) {
              router.push(`/hub?session=${sessionId}`);
            } else {
              setEditorOpen(false);
            }
          }}
          profile={activeProfile}
          onProfile={setActiveProfile}
          template={template}
          onTemplate={setTemplate}
          layout={layout}
          onLayout={setLayout}
          hidden={hidden}
          onToggleHidden={toggleHidden}
          onSave={onSaveDraft}
          lang={lang}
          onLang={setLang}
          onTranslate={handleTranslate}
          translating={translating}
        />
      )}
    </div>
  );
}
