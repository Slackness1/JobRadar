'use client';
import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ResumeScorePanel } from '../../../components/resume-copilot/workspace/hub/resume/ResumeScorePanel';
import { ResumeEditorOverlay } from '../../../components/resume-copilot/workspace/hub/resume/editor/ResumeEditorOverlay';
import {
  SAMPLE_PROFILE,
  DEFAULT_LAYOUT,
  profilePayloadToResumeProfile,
  type Lang,
  type LayoutState,
  type ResumeProfile,
} from '../../../components/resume-copilot/workspace/hub/resume/editor/resumeSample';
import {
  getEditorDraft,
  getResumeCopilotConfirmedProfile,
  getResumeCopilotParsedProfile,
  putEditorDraft,
  translateProfile,
} from '../../../components/resume-copilot/api';

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

function Inner() {
  const params = useSearchParams();
  const mock = params.get('mock') === '1';
  const sessionId = Number(params.get('session') || '0');
  const [editorOpen, setEditorOpen] = useState(false);
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
    if (en) { setLang('en'); return; }      // 已翻过 → 只切语言,不重复调用
    setTranslating(true);
    try {
      const out = await translateProfile(zh);
      setEn(out.profile as ResumeProfile);
      setLang('en');
    } catch {
      setLang('zh');                          // 失败留在中文(en 仍为 null)
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
    return <div style={{ padding: 40, fontFamily: 'system-ui' }}>缺少 ?session=&lt;id&gt; 或 ?mock=1</div>;
  }
  return (
    <div className="hf" data-theme="hub" style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', justifyContent: 'flex-end' }}>
      <div style={{ width: 500, height: '100vh', background: 'var(--ivory)', boxShadow: '-8px 0 24px rgba(0,0,0,0.06)' }}>
        <ResumeScorePanel
          sessionId={sessionId}
          mock={mock}
          onExpandEditor={() => setEditorOpen(true)}
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
      </div>
      {editorOpen && (
        <ResumeEditorOverlay
          sessionId={sessionId}
          mock={mock}
          onClose={() => setEditorOpen(false)}
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

export default function Page() {
  return (
    <Suspense fallback={<div style={{ padding: 40 }}>加载中…</div>}>
      <Inner />
    </Suspense>
  );
}
