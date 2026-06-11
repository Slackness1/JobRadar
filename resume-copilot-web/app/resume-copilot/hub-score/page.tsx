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
  getResumeCopilotConfirmedProfile,
  getResumeCopilotParsedProfile,
  translateProfile,
} from '../../../components/resume-copilot/api';

// ── 简历编辑器草稿持久化(本地) ──────────────────────────────────────────────
// 编辑器改的是渲染模型 + 模板/布局/隐藏项, 后端 confirmed-profile 装不下这套。
// 跨设备同步要等统一加 DB 列(避免现在与并行会话的在途迁移撞 alembic head),
// 当前先用 localStorage 按会话存, 刷新自动恢复 —— 解决"改了刷新就没"。
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

  // 真实会话:本地草稿优先(恢复上次编辑), 否则拉真简历 profile。
  useEffect(() => {
    if (mock || !sessionId) {
      loadedRef.current = true;
      return;
    }
    let cancelled = false;
    const draft = loadDraft(sessionId);
    if (draft) {
      // 微任务里应用, 避免在 effect 内同步 setState(级联渲染 lint)。
      Promise.resolve().then(() => {
        if (cancelled) return;
        setZh(draft.profile);
        setTemplate(draft.template);
        setLayout(draft.layout);
        setHidden(new Set(draft.hidden));
        loadedRef.current = true;
      });
      return () => {
        cancelled = true;
      };
    }
    getResumeCopilotConfirmedProfile(sessionId)
      .then((r) => {
        if (!cancelled && r?.profile) setZh(profilePayloadToResumeProfile(r.profile));
      })
      .catch(() => {
        getResumeCopilotParsedProfile(sessionId)
          .then((r) => {
            if (!cancelled && r?.profile) setZh(profilePayloadToResumeProfile(r.profile));
          })
          .catch(() => {
            /* 都拿不到则保持示例,不致崩 */
          });
      })
      .finally(() => {
        if (!cancelled) loadedRef.current = true;
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, mock]);

  // 自动保存草稿:任何编辑(简历内容/模板/布局/隐藏)落本地, 刷新不丢。
  useEffect(() => {
    if (mock || !sessionId || !loadedRef.current) return;
    saveDraft(sessionId, { profile: zh, template, layout, hidden: [...hidden] });
  }, [zh, template, layout, hidden, sessionId, mock]);

  // 保存按钮:已自动存, 这里立即 flush(反馈由编辑器本地给)。
  const onSaveDraft = () => {
    if (!mock && sessionId) saveDraft(sessionId, { profile: zh, template, layout, hidden: [...hidden] });
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
