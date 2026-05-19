'use client';

/**
 * Teacher quick-entry — Variant A, multi-job aware.
 * Ported from JobRadar HiFi design (hifi-teacher.jsx → React/TS, real backend).
 *
 * One source can yield N jobs (微信群截图列 3 个、文章里 5 个 JD)。
 * 解析后竖排 N 张卡片，每张卡独立赛道/标签/删除/单卡提交，
 * 底部 "全部提交 (N)" 一次性 submit 全部。
 */

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from 'react';

import { HFBtn, HFLogo, HFPill, I } from './hifi-primitives';
import {
  OCR_BATCH_MAX,
  type OcrBatchItem,
  type ParsedDraft,
  type SourceType,
  type TeacherStats,
  type Track,
  getStats,
  postDraft,
  postParse,
  postParseImages,
  postSubmit,
} from '@/components/teacher/api';

const TRACK_OPTIONS: Array<[Track, string]> = [
  ['finance', '纯金融'],
  ['fintech', 'FinTech'],
  ['other', '其他'],
];

const TAB_DEFS: Array<{ key: SourceType; icon: string; label: string }> = [
  { key: 'link', icon: '🔗', label: '链接' },
  { key: 'ocr', icon: '📸', label: '截图 OCR' },
  { key: 'text', icon: '📝', label: 'JD 文本' },
];

const SAMPLE_URL = 'https://campus.cicc.com/job/2026-mmt-quant-bj';
const SAMPLE_JD = [
  '【中金公司 · 2026 校招】',
  '1. 量化研究员 (MMT) — 北京 · 全职',
  '   高频做市策略研究、信号挖掘与回测',
  '2. 投行业务部 — 上海 · 全职',
  '   IPO 项目执行、行业研究',
  '3. AI 算法工程师 — 深圳 · 实习',
  '   NLP 模型在客户分析中的应用',
].join('\n');

interface DraftCard {
  uid: string;
  parsed: ParsedDraft;
  track: Track;
  tags: string[];
  newTagDraft: string;
  cardStatus: 'idle' | 'submitting' | 'submitted' | 'failed';
  cardError?: string;
}

function makeCard(p: ParsedDraft): DraftCard {
  return {
    uid: crypto.randomUUID(),
    parsed: p,
    track: p.suggested_track,
    tags: [...p.suggested_tags],
    newTagDraft: '',
    cardStatus: 'idle',
  };
}

interface TopBarProps {
  stats: TeacherStats | null;
}

function TopBar({ stats }: TopBarProps) {
  const teacherName = stats?.teacher_name ?? '张老师';
  const dept = stats?.teacher_dept ?? '金融学院';
  const queue = (stats?.week_pending ?? 0) + (stats?.week_passed ?? 0);
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '18px 32px',
        borderBottom: '1px solid var(--border-warm)',
        background: 'var(--ivory)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <HFLogo size="sm" label="JobRadar" />
        <div style={{ width: 1, height: 20, background: 'var(--border-warm)' }} />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--ink-soft)' }}>教师工作台</span>
          <span className="hf-pill" style={{ height: 22, fontSize: 11.5 }}>Faculty</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <HFPill tone="amber">
          <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--amber-fg)' }} />
          审核队列 {queue}
        </HFPill>
        <span className="hf-cap">{dept} · {teacherName}</span>
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 15,
            background: 'var(--deep-dark)',
            color: '#faf9f5',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 12.5,
            fontWeight: 600,
          }}
        >张</div>
      </div>
    </div>
  );
}

type Stage = 'empty' | 'parsing' | 'parsed' | 'no_jobs' | 'error';

interface CardRowProps {
  card: DraftCard;
  index: number;
  onUpdate: (uid: string, patch: Partial<DraftCard>) => void;
  onDelete: (uid: string) => void;
  onSubmit: (uid: string) => void;
}

function CardRow({ card, index, onUpdate, onDelete, onSubmit }: CardRowProps) {
  const { parsed, track, tags, newTagDraft, cardStatus, cardError } = card;

  function addTag() {
    const t = newTagDraft.trim();
    if (!t || tags.includes(t)) {
      onUpdate(card.uid, { newTagDraft: '' });
      return;
    }
    onUpdate(card.uid, { tags: [...tags, t], newTagDraft: '' });
  }

  const isSubmitted = cardStatus === 'submitted';
  const isSubmitting = cardStatus === 'submitting';

  return (
    <div
      className="hf-card"
      style={{
        padding: 16,
        borderRadius: 14,
        background: 'var(--ivory)',
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        opacity: isSubmitted ? 0.55 : 1,
        transition: 'opacity .25s',
        position: 'relative',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: '#1a3a6e',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontFamily: 'var(--font-serif)',
            fontSize: 18,
            fontWeight: 600,
            flexShrink: 0,
          }}
        >{(parsed.company || '?').slice(0, 1)}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span className="hf-cap" style={{ color: 'var(--stone)' }}>#{index + 1}</span>
            <span style={{ fontWeight: 600, fontSize: 16, color: 'var(--ink)' }}>{parsed.title || '尚未解析'}</span>
            <HFPill>{Math.round(parsed.confidence)}%</HFPill>
          </div>
          <div className="hf-cap" style={{ marginTop: 2 }}>
            {[parsed.company, parsed.location, parsed.deadline && `截止 ${parsed.deadline}`].filter(Boolean).join(' · ') || '——'}
          </div>
        </div>
        {isSubmitted ? (
          <HFPill tone="emerald">
            <span style={{ display: 'inline-flex', color: 'var(--emerald)' }}>{I.check(11)}</span>
            已入队
          </HFPill>
        ) : (
          <button
            onClick={() => onDelete(card.uid)}
            style={{
              width: 26,
              height: 26,
              borderRadius: 13,
              color: 'var(--stone)',
              background: 'transparent',
              border: 0,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            title="删除这条"
          >{I.close(12)}</button>
        )}
      </div>

      <hr className="hf-hr" />

      <div style={{ display: 'grid', gridTemplateColumns: '78px 1fr', rowGap: 10, columnGap: 16, fontSize: 13 }}>
        <div className="hf-cap">JD 摘要</div>
        <div style={{ color: 'var(--ink-soft)', lineHeight: 1.55 }}>
          {parsed.jd_summary || <span className="hf-cap">（无摘要）</span>}
        </div>

        <div className="hf-cap">建议赛道</div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {TRACK_OPTIONS.map(([k, l]) => {
            const active = track === k;
            return (
              <button
                key={k}
                onClick={() => onUpdate(card.uid, { track: k })}
                disabled={isSubmitted}
                style={{
                  height: 26,
                  padding: '0 12px',
                  borderRadius: 99,
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: isSubmitted ? 'default' : 'pointer',
                  border: 0,
                  background: active ? 'var(--terracotta)' : 'var(--library-rail)',
                  color: active ? '#fff' : 'var(--ink-soft)',
                  boxShadow: active ? '0 0 0 1px var(--terracotta)' : '0 0 0 1px var(--border-warm)',
                }}
              >{l}</button>
            );
          })}
        </div>

        <div className="hf-cap">薪酬</div>
        <div style={{ color: 'var(--ink)' }}>
          {parsed.salary || <span className="hf-cap">未公开</span>}
        </div>

        <div className="hf-cap">标签</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
          {tags.map((t) => (
            <span key={t} className="hf-pill" style={{ height: 24, fontSize: 11.5 }}>
              {t}
              <span
                onClick={() => !isSubmitted && onUpdate(card.uid, { tags: tags.filter((x) => x !== t) })}
                style={{ marginLeft: 4, cursor: isSubmitted ? 'default' : 'pointer', color: 'var(--stone)' }}
              >×</span>
            </span>
          ))}
          {!isSubmitted && (
            <>
              <input
                value={newTagDraft}
                onChange={(e) => onUpdate(card.uid, { newTagDraft: e.target.value })}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                placeholder="加标签…"
                style={{
                  height: 24,
                  padding: '0 10px',
                  borderRadius: 99,
                  fontSize: 11.5,
                  background: 'transparent',
                  border: 0,
                  outline: 0,
                  boxShadow: '0 0 0 1px var(--border-warm)',
                  width: 90,
                  color: 'var(--ink-soft)',
                }}
              />
              <button
                onClick={addTag}
                style={{
                  height: 24,
                  padding: '0 8px',
                  borderRadius: 99,
                  fontSize: 11.5,
                  color: 'var(--terracotta)',
                  background: 'transparent',
                  border: 0,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 3,
                }}
              >{I.plus(11)} 加</button>
            </>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <span className="hf-cap">
          {cardStatus === 'failed' && cardError ? <span style={{ color: 'var(--crimson)' }}>失败：{cardError}</span> : null}
        </span>
        {!isSubmitted && (
          <HFBtn
            variant="ghost"
            size="sm"
            onClick={() => onSubmit(card.uid)}
            disabled={isSubmitting}
          >{isSubmitting ? '提交中…' : '单独提交'}</HFBtn>
        )}
      </div>
    </div>
  );
}

export function HFTeacher() {
  const [tab, setTab] = useState<SourceType>('text');
  const [url, setUrl] = useState(SAMPLE_URL);
  const [jdText, setJdText] = useState(SAMPLE_JD);

  const [stage, setStage] = useState<Stage>('empty');
  const [parseError, setParseError] = useState('');
  const [parseElapsed, setParseElapsed] = useState(0);

  const [cards, setCards] = useState<DraftCard[]>([]);
  const [note, setNote] = useState('');

  const [stats, setStats] = useState<TeacherStats | null>(null);
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [toast, setToast] = useState<string>('');

  // OCR-tab specific state — supports up to OCR_BATCH_MAX images per batch
  interface OcrFileEntry { file: File; previewUrl: string; uid: string }
  const [ocrFiles, setOcrFiles] = useState<OcrFileEntry[]>([]);
  const [ocrItems, setOcrItems] = useState<OcrBatchItem[]>([]);  // per-image trace from last batch
  const [ocrDragHover, setOcrDragHover] = useState(false);
  const ocrFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStats()
      .then((s) => { if (!cancelled) setStats(s); })
      .catch(() => { /* ignore */ });
    return () => { cancelled = true; };
  }, []);

  function refreshStats() {
    getStats().then(setStats).catch(() => { /* ignore */ });
  }

  const currentPayload = useMemo(() => {
    if (tab === 'link') return url;
    if (tab === 'text') return jdText;
    return ''; // OCR tab is image-only; text is sourced from postParseImages
  }, [tab, url, jdText]);

  // 公众号链接绝大多数是图片渲染，链接抓取拿到的正文文本几乎为空。
  // 提示用户改用 OCR 截图通道，比硬抓后给一堆乱字体验好得多。
  const isWechatArticle = useMemo(() => {
    if (tab !== 'link') return false;
    return /https?:\/\/(?:mp|mpc)\.weixin\.qq\.com\//i.test(url.trim());
  }, [tab, url]);

  // Revoke object URLs on unmount only (per-entry revoke happens in remove/clear).
  useEffect(() => {
    return () => {
      // capture-time snapshot — refs not needed since unmount runs once
      setOcrFiles((current) => {
        for (const f of current) URL.revokeObjectURL(f.previewUrl);
        return current;
      });
    };
  }, []);

  function flashToast(msg: string, ms = 2000) {
    setToast(msg);
    window.setTimeout(() => setToast(''), ms);
  }

  function addOcrFiles(incoming: File[]) {
    if (incoming.length === 0) return;
    setOcrFiles((prev) => {
      const room = OCR_BATCH_MAX - prev.length;
      if (room <= 0) {
        flashToast(`单次最多 ${OCR_BATCH_MAX} 张图`);
        return prev;
      }
      const accepted: OcrFileEntry[] = [];
      let dropped = 0;
      for (const file of incoming.slice(0, room)) {
        if (!file.type.startsWith('image/')) { dropped += 1; continue; }
        if (file.size > 10 * 1024 * 1024) {
          flashToast(`${file.name} 超过 10 MB，已跳过`);
          continue;
        }
        accepted.push({
          file,
          previewUrl: URL.createObjectURL(file),
          uid: crypto.randomUUID(),
        });
      }
      if (incoming.length > room) {
        flashToast(`已加 ${accepted.length} 张，超出 ${OCR_BATCH_MAX} 张上限的被忽略`);
      } else if (dropped > 0) {
        flashToast(`已加 ${accepted.length} 张（${dropped} 张非图片被跳过）`);
      }
      return [...prev, ...accepted];
    });
  }

  function removeOcrFile(uid: string) {
    setOcrFiles((prev) => {
      const target = prev.find((f) => f.uid === uid);
      if (target) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((f) => f.uid !== uid);
    });
  }

  function clearOcrFiles() {
    setOcrFiles((prev) => {
      for (const f of prev) URL.revokeObjectURL(f.previewUrl);
      return [];
    });
    setOcrItems([]);
  }

  // Ctrl+V / Cmd+V → 把剪贴板里的所有图片追加到队列
  useEffect(() => {
    if (tab !== 'ocr') return;
    const handlePaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const found: File[] = [];
      for (const item of Array.from(items)) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile();
          if (file) {
            const named = file.name && file.name !== 'image.png'
              ? file
              : new File([file], `clipboard-${Date.now()}-${found.length + 1}.png`, { type: file.type || 'image/png' });
            found.push(named);
          }
        }
      }
      if (found.length > 0) {
        addOcrFiles(found);
        flashToast(found.length === 1 ? '已粘贴截图' : `已粘贴 ${found.length} 张截图`);
        e.preventDefault();
      }
    };
    window.addEventListener('paste', handlePaste);
    return () => window.removeEventListener('paste', handlePaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function handleParse() {
    // OCR tab: if any images queued, batch them; else fall back to manually pasted OCR text
    const isOcrImageMode = tab === 'ocr' && ocrFiles.length > 0;
    if (tab === 'ocr' && ocrFiles.length === 0) {
      setParseError('请先粘贴 / 拖入 / 选择截图');
      setStage('error');
      return;
    }
    if (!isOcrImageMode && !currentPayload.trim()) {
      setParseError('请先填入内容');
      setStage('error');
      return;
    }
    setStage('parsing');
    setParseError('');
    const t0 = performance.now();
    try {
      let result: ParsedDraft[];
      if (isOcrImageMode) {
        const out = await postParseImages(ocrFiles.map((e) => e.file));
        setOcrItems(out.items);
        result = out.all_drafts;
      } else {
        result = await postParse(tab, currentPayload.trim());
      }
      setParseElapsed(Math.round((performance.now() - t0) / 100) / 10);
      if (result.length === 0) {
        setCards([]);
        setStage('no_jobs');
      } else {
        setCards(result.map(makeCard));
        setStage('parsed');
      }
    } catch (err) {
      setParseError(err instanceof Error ? err.message : String(err));
      setStage('error');
    }
  }

  function patchCard(uid: string, patch: Partial<DraftCard>) {
    setCards((prev) => prev.map((c) => (c.uid === uid ? { ...c, ...patch } : c)));
  }

  function deleteCard(uid: string) {
    setCards((prev) => prev.filter((c) => c.uid !== uid));
  }

  // T1 (2026-05-19): 提交前校验必填字段。
  // detail_url 缺时学生看到推荐点不进去 → 直接拦在前端,提示老师补全。
  function _validateCardForSubmit(card: DraftCard): string | null {
    const url = (card.parsed.detail_url || '').trim();
    const title = (card.parsed.title || '').trim();
    const company = (card.parsed.company || '').trim();
    if (!url) return '岗位申请链接 (detail_url) 必填 — 学生看到岗位会点不进去';
    if (!title) return '岗位标题必填';
    if (!company) return '公司名必填';
    // 简单 URL 格式校验
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      return '岗位申请链接必须是完整 URL (含 http:// 或 https://)';
    }
    return null;
  }

  async function submitOne(uid: string): Promise<boolean> {
    const card = cards.find((c) => c.uid === uid);
    if (!card) return false;

    // T1: 前端校验必填字段
    const err = _validateCardForSubmit(card);
    if (err) {
      patchCard(uid, { cardStatus: 'failed', cardError: err });
      flashToast(err);
      return false;
    }

    patchCard(uid, { cardStatus: 'submitting', cardError: undefined });
    try {
      const draft = await postDraft({
        source_type: tab,
        source_payload: currentPayload,
        parsed_title: card.parsed.title,
        parsed_company: card.parsed.company,
        parsed_location: card.parsed.location,
        parsed_jd_summary: card.parsed.jd_summary,
        parsed_deadline: card.parsed.deadline,
        parsed_salary: card.parsed.salary,
        parsed_detail_url: card.parsed.detail_url,
        parse_confidence: card.parsed.confidence,
        track: card.track,
        tags: card.tags,
        teacher_note: note,
      });
      await postSubmit(draft.id);
      patchCard(uid, { cardStatus: 'submitted' });
      return true;
    } catch (err) {
      patchCard(uid, {
        cardStatus: 'failed',
        cardError: err instanceof Error ? err.message : '未知错误',
      });
      return false;
    }
  }

  async function handleSubmitAll() {
    const pending = cards.filter((c) => c.cardStatus !== 'submitted');
    if (pending.length === 0) {
      flashToast('没有待提交的岗位');
      return;
    }
    setBatchSubmitting(true);
    let ok = 0;
    let fail = 0;
    for (const c of pending) {
      const success = await submitOne(c.uid);
      if (success) ok += 1; else fail += 1;
    }
    setBatchSubmitting(false);
    if (fail === 0) flashToast(`已提交 ${ok} 个岗位 · 25 分钟内上线`);
    else flashToast(`提交完成：成功 ${ok} · 失败 ${fail}`);
    refreshStats();
  }

  async function handleSubmitOne(uid: string) {
    const ok = await submitOne(uid);
    flashToast(ok ? '已入队' : '提交失败');
    refreshStats();
  }

  async function handleSaveAllAsDraft() {
    const pending = cards.filter((c) => c.cardStatus !== 'submitted');
    if (pending.length === 0) {
      flashToast('没有可保存的岗位');
      return;
    }
    let ok = 0;
    for (const c of pending) {
      try {
        await postDraft({
          source_type: tab,
          source_payload: currentPayload,
          parsed_title: c.parsed.title,
          parsed_company: c.parsed.company,
          parsed_location: c.parsed.location,
          parsed_jd_summary: c.parsed.jd_summary,
          parsed_deadline: c.parsed.deadline,
          parsed_salary: c.parsed.salary,
          parsed_detail_url: c.parsed.detail_url,
          parse_confidence: c.parsed.confidence,
          track: c.track,
          tags: c.tags,
          teacher_note: note,
        });
        ok += 1;
      } catch {
        // continue
      }
    }
    flashToast(`已保存 ${ok} 条草稿`);
    refreshStats();
  }

  const cardCount = cards.length;
  const pendingCount = cards.filter((c) => c.cardStatus !== 'submitted').length;
  const previewCard = cards[0];

  return (
    <div className="hf" style={{ minHeight: '100vh', background: 'var(--parchment)', display: 'flex', flexDirection: 'column' }}>
      <TopBar stats={stats} />

      {/* hero */}
      <div
        style={{
          padding: '24px 32px 14px',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 16,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div className="hf-overline" style={{ marginBottom: 8 }}>QUICK ENTRY · 30 秒一岗</div>
          <div className="hf-h1" style={{ margin: 0 }}>录入岗位</div>
          <div className="hf-body" style={{ marginTop: 6 }}>
            一条信息里多个岗位会自动拆开 → 单独编辑或全部提交
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <HFBtn variant="ghost" size="sm" icon={I.book(12)} disabled>批量导入 CSV</HFBtn>
          <HFBtn variant="ghost" size="sm" icon={I.file(12)} disabled>录入历史</HFBtn>
        </div>
      </div>

      {/* main grid */}
      <div
        style={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.25fr) minmax(0, 1fr)',
          gap: 24,
          padding: '8px 32px 32px',
          minHeight: 0,
        }}
      >
        {/* LEFT — input + parsed cards stack */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          {/* tabs */}
          <div
            style={{
              display: 'inline-flex',
              gap: 4,
              padding: 4,
              background: 'var(--library-rail)',
              borderRadius: 12,
              alignSelf: 'flex-start',
              boxShadow: 'inset 0 0 0 1px var(--border-warm)',
            }}
          >
            {TAB_DEFS.map((t) => {
              const active = tab === t.key;
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  style={{
                    height: 32,
                    padding: '0 14px',
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: active ? 600 : 500,
                    background: active ? 'var(--ivory)' : 'transparent',
                    color: active ? 'var(--ink)' : 'var(--olive)',
                    boxShadow: active
                      ? '0 1px 2px rgba(0,0,0,0.06), 0 0 0 1px var(--border-warm)'
                      : 'none',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    cursor: 'pointer',
                    border: 0,
                  }}
                >
                  <span style={{ fontSize: 14 }}>{t.icon}</span>
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* input card */}
          <div className="hf-card" style={{ padding: 16, borderRadius: 14 }}>
            {tab === 'link' && (
              <>
                <div className="hf-overline" style={{ marginBottom: 10 }}>粘贴岗位链接</div>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '0 12px',
                    height: 44,
                    background: 'var(--ivory)',
                    borderRadius: 10,
                    boxShadow: '0 0 0 1px var(--border-strong)',
                  }}
                >
                  <span style={{ color: 'var(--stone)', display: 'inline-flex' }}>{I.search(14)}</span>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="hf-mono"
                    style={{
                      flex: 1,
                      fontSize: 13,
                      color: 'var(--ink)',
                      border: 0,
                      outline: 0,
                      background: 'transparent',
                    }}
                  />
                  <span className="hf-pill emerald" style={{ height: 22, fontSize: 11.5 }}>
                    <span style={{ width: 6, height: 6, borderRadius: 3, background: 'var(--emerald)' }} /> 可识别
                  </span>
                  <HFBtn variant="primary" size="sm" onClick={handleParse} disabled={stage === 'parsing'}>抓取</HFBtn>
                </div>
                <div className="hf-cap" style={{ marginTop: 10 }}>
                  支持 · BOSS 直聘 · 拉勾 · 牛客 · 各券商 / 银行 / 央国企官网 · 公司 careers 站
                </div>
                {isWechatArticle && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: '10px 12px',
                      borderRadius: 10,
                      background: 'var(--amber-wash, rgba(217,138,32,0.10))',
                      boxShadow: '0 0 0 1px var(--amber-fg)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 10,
                      fontSize: 12.5,
                      lineHeight: 1.5,
                      color: 'var(--ink)',
                    }}
                  >
                    <span style={{ fontSize: 14, lineHeight: '20px', flexShrink: 0 }}>⚠️</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 600, marginBottom: 2 }}>检测到微信公众号链接</div>
                      <div style={{ color: 'var(--ink-soft)' }}>
                        公众号文章正文几乎都是图片，直接抓链接抽不到岗位信息。建议截图后改走 OCR 通道。
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setTab('ocr')}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 99,
                        background: 'var(--terracotta)',
                        color: '#fff',
                        border: 0,
                        fontSize: 12,
                        fontWeight: 600,
                        cursor: 'pointer',
                        flexShrink: 0,
                        whiteSpace: 'nowrap',
                      }}
                    >改走 OCR →</button>
                  </div>
                )}
              </>
            )}

            {tab === 'ocr' && (
              <>
                <div
                  style={{
                    marginBottom: 10,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 8,
                  }}
                >
                  <div className="hf-overline">截图 OCR · 本地推理 · 单次最多 {OCR_BATCH_MAX} 张</div>
                  {ocrFiles.length > 0 && (
                    <span className="hf-cap">{ocrFiles.length} / {OCR_BATCH_MAX}</span>
                  )}
                </div>
                <input
                  ref={ocrFileInputRef}
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/jpg"
                  multiple
                  style={{ display: 'none' }}
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    const list = Array.from(e.target.files ?? []);
                    if (list.length > 0) addOcrFiles(list);
                    e.target.value = ''; // allow re-picking the same file(s)
                  }}
                />

                {ocrFiles.length === 0 && (
                  <div
                    style={{
                      marginBottom: 10,
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: 'var(--library-rail)',
                      fontSize: 12.5,
                      lineHeight: 1.55,
                      color: 'var(--ink-soft)',
                      display: 'flex',
                      gap: 8,
                      alignItems: 'flex-start',
                    }}
                  >
                    <span style={{ fontSize: 13, lineHeight: '18px', flexShrink: 0 }}>💡</span>
                    <span>
                      公众号招聘海报 / 微信群截图 / 招聘 PDF 截图都可以 — 图里多个岗位会自动拆成多张卡片，
                      单次 {OCR_BATCH_MAX} 张并发识别
                    </span>
                  </div>
                )}

                {/* Drop zone — always visible (clickable) when room remaining */}
                {ocrFiles.length < OCR_BATCH_MAX && (
                  <div
                    onClick={() => ocrFileInputRef.current?.click()}
                    onDragOver={(e: DragEvent<HTMLDivElement>) => { e.preventDefault(); setOcrDragHover(true); }}
                    onDragLeave={() => setOcrDragHover(false)}
                    onDrop={(e: DragEvent<HTMLDivElement>) => {
                      e.preventDefault();
                      setOcrDragHover(false);
                      const list = Array.from(e.dataTransfer.files ?? []);
                      if (list.length > 0) addOcrFiles(list);
                    }}
                    style={{
                      height: ocrFiles.length === 0 ? 140 : 88,
                      borderRadius: 12,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 14,
                      cursor: 'pointer',
                      background: 'var(--terracotta-wash)',
                      backgroundImage: 'radial-gradient(circle, rgba(201,100,66,0.18) 1px, transparent 1px)',
                      backgroundSize: '12px 12px',
                      boxShadow: ocrDragHover
                        ? '0 0 0 2px var(--terracotta)'
                        : '0 0 0 1.5px var(--terracotta-ring)',
                      transition: 'box-shadow .15s, height .2s',
                    }}
                  >
                    <div
                      style={{
                        width: ocrFiles.length === 0 ? 56 : 40,
                        height: ocrFiles.length === 0 ? 56 : 40,
                        borderRadius: 28,
                        background: 'var(--terracotta)',
                        color: '#fff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >{I.upload(ocrFiles.length === 0 ? 22 : 18)}</div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14.5, color: 'var(--ink)' }}>
                        {ocrFiles.length === 0
                          ? '粘贴 (Ctrl+V) / 拖进来 / 点击选择'
                          : `继续添加（还能加 ${OCR_BATCH_MAX - ocrFiles.length} 张）`}
                      </div>
                      <div className="hf-cap" style={{ marginTop: 4 }}>
                        PNG · JPG · WebP · &lt; 10 MB · 本地 OCR 不上传外网
                      </div>
                    </div>
                  </div>
                )}

                {/* Thumbnails grid */}
                {ocrFiles.length > 0 && (
                  <div
                    style={{
                      marginTop: 12,
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                      gap: 10,
                    }}
                  >
                    {ocrFiles.map((entry, idx) => {
                      const item = ocrItems.find((it) => it.filename === entry.file.name);
                      const hasError = !!item?.error;
                      const draftCount = item?.drafts.length ?? 0;
                      return (
                        <div
                          key={entry.uid}
                          style={{
                            position: 'relative',
                            padding: 6,
                            borderRadius: 10,
                            background: 'var(--ivory)',
                            boxShadow: hasError
                              ? '0 0 0 1.5px var(--crimson)'
                              : '0 0 0 1px var(--border-warm)',
                          }}
                        >
                          <img
                            src={entry.previewUrl}
                            alt={entry.file.name}
                            style={{
                              width: '100%',
                              height: 80,
                              objectFit: 'cover',
                              borderRadius: 6,
                              background: 'var(--library-rail)',
                              display: 'block',
                            }}
                          />
                          <div className="hf-cap" style={{ marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            #{idx + 1} · {entry.file.name}
                          </div>
                          <div className="hf-cap" style={{ marginTop: 2 }}>
                            {(entry.file.size / 1024).toFixed(1)} KB
                            {item ? (
                              hasError
                                ? <span style={{ color: 'var(--crimson)' }}> · {item.error}</span>
                                : <span style={{ color: 'var(--emerald)' }}> · {draftCount} 岗</span>
                            ) : null}
                          </div>
                          <button
                            onClick={() => removeOcrFile(entry.uid)}
                            disabled={stage === 'parsing'}
                            title="移除"
                            style={{
                              position: 'absolute',
                              top: 4,
                              right: 4,
                              width: 22,
                              height: 22,
                              borderRadius: 11,
                              background: 'rgba(20,20,19,0.7)',
                              color: '#fff',
                              border: 0,
                              cursor: stage === 'parsing' ? 'default' : 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                            }}
                          >{I.close(11)}</button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {ocrFiles.length > 0 && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                    <HFBtn variant="ghost" size="sm" onClick={clearOcrFiles} disabled={stage === 'parsing'}>
                      清空
                    </HFBtn>
                    <HFBtn variant="primary" size="sm" onClick={handleParse} disabled={stage === 'parsing'}>
                      {stage === 'parsing' ? `识别中…（${ocrFiles.length} 张）` : `识别 + 解析（${ocrFiles.length} 张）`}
                    </HFBtn>
                  </div>
                )}

                {/* Per-image OCR text trace (collapsed) */}
                {ocrItems.length > 0 && ocrItems.some((it) => it.ocr_text) && (
                  <details style={{ marginTop: 10 }}>
                    <summary style={{ cursor: 'pointer', color: 'var(--olive)', fontSize: 12.5 }}>
                      OCR 识别到的文字（{ocrItems.length} 张）
                    </summary>
                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {ocrItems.map((it, i) => (
                        <div
                          key={`${it.filename}-${i}`}
                          style={{
                            padding: 10,
                            borderRadius: 8,
                            background: 'var(--library-rail)',
                            boxShadow: '0 0 0 1px var(--border-warm)',
                          }}
                        >
                          <div className="hf-cap" style={{ marginBottom: 4 }}>
                            #{i + 1} · {it.filename}
                            {it.error && <span style={{ color: 'var(--crimson)' }}> · {it.error}</span>}
                          </div>
                          <pre
                            style={{
                              margin: 0,
                              fontFamily: 'var(--font-mono)',
                              fontSize: 12,
                              lineHeight: 1.5,
                              color: 'var(--ink-soft)',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-all',
                            }}
                          >{it.ocr_text || '（无识别结果）'}</pre>
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </>
            )}

            {tab === 'text' && (
              <>
                <div className="hf-overline" style={{ marginBottom: 10 }}>粘贴 JD 全文（支持多个岗位）</div>
                <textarea
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  style={{
                    width: '100%',
                    height: 160,
                    resize: 'vertical',
                    padding: 12,
                    borderRadius: 10,
                    background: 'var(--ivory)',
                    boxShadow: '0 0 0 1px var(--border-warm)',
                    border: 0,
                    outline: 0,
                    fontSize: 13,
                    lineHeight: 1.55,
                    color: 'var(--ink-soft)',
                    fontFamily: 'var(--font-mono)',
                  }}
                />
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 10 }}>
                  <HFBtn variant="primary" size="sm" onClick={handleParse} disabled={stage === 'parsing'}>解析</HFBtn>
                </div>
              </>
            )}
          </div>

          {/* status row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div className="hf-overline">
              系统抓取到 {cardCount > 0 && <span style={{ color: 'var(--terracotta)' }}>· {cardCount} 个岗位</span>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--stone)' }}>
              {stage === 'parsing' && (<><span className="hf-spin" /> 正在抽取字段…</>)}
              {stage === 'parsed' && (
                <>
                  <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>{I.check(12)}</span>
                  解析完成 · {parseElapsed}s
                </>
              )}
              {stage === 'no_jobs' && (
                <span style={{ color: 'var(--amber-fg)' }}>未识别到岗位 · 确认下输入是不是 JD？</span>
              )}
              {stage === 'error' && (
                <span style={{ color: 'var(--crimson)' }}>解析失败 · {parseError}</span>
              )}
              {stage !== 'empty' && (
                <button
                  onClick={handleParse}
                  style={{ marginLeft: 6, color: 'var(--terracotta)', background: 'transparent', border: 0, cursor: 'pointer', fontSize: 12 }}
                >重新抓取</button>
              )}
            </div>
          </div>

          {/* cards stack */}
          {stage === 'parsed' && cards.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {cards.map((c, i) => (
                <CardRow
                  key={c.uid}
                  card={c}
                  index={i}
                  onUpdate={patchCard}
                  onDelete={deleteCard}
                  onSubmit={handleSubmitOne}
                />
              ))}
            </div>
          ) : (
            <div
              className="hf-card"
              style={{
                padding: 24,
                borderRadius: 14,
                textAlign: 'center',
                color: 'var(--stone)',
                fontSize: 13,
                background: 'var(--ivory)',
              }}
            >
              {stage === 'parsing'
                ? '解析中…'
                : stage === 'no_jobs'
                  ? '这段内容里没识别到岗位 — 也可能是输入不是 JD（比如系统说明 / 聊天记录），换一段试试'
                  : stage === 'error'
                    ? '请重试或换一种来源'
                    : '解析后会展开成卡片，每张可单独编辑'}
            </div>
          )}
        </div>

        {/* RIGHT — student preview + submit */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, minWidth: 0 }}>
          <div className="hf-overline">学生端预览（首条）</div>
          <div className="hf-card lift" style={{ padding: 16, borderRadius: 14 }}>
            {previewCard ? (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 56 }}>
                  <div
                    style={{
                      fontFamily: 'var(--font-serif)',
                      fontSize: 32,
                      fontWeight: 600,
                      color: 'var(--terracotta)',
                      lineHeight: 1,
                    }}
                  >92</div>
                  <div className="hf-cap" style={{ marginTop: 2 }}>match</div>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontWeight: 600, fontSize: 14.5 }}>{previewCard.parsed.title}</span>
                    {cardCount > 1 && <HFPill tone="terra">+{cardCount - 1} 其他岗位</HFPill>}
                  </div>
                  <div className="hf-cap" style={{ marginTop: 2 }}>
                    {[
                      previewCard.parsed.company,
                      previewCard.parsed.location,
                      TRACK_OPTIONS.find(([k]) => k === previewCard.track)?.[1],
                    ].filter(Boolean).join(' · ') || '——'}
                  </div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 8, flexWrap: 'wrap' }}>
                    {previewCard.tags.slice(0, 3).map((t) => (<HFPill key={t}>{t}</HFPill>))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="hf-cap" style={{ textAlign: 'center', padding: '12px 0' }}>解析后会出现学生端预览</div>
            )}
          </div>

          <div className="hf-overline">备注 · 全部岗位共享</div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. 这是合作券商提前批，优先推荐金融工程方向同学…"
            style={{
              width: '100%',
              minHeight: 90,
              resize: 'vertical',
              padding: 12,
              borderRadius: 12,
              background: 'var(--ivory)',
              boxShadow: '0 0 0 1px var(--border-warm)',
              border: 0,
              outline: 0,
              fontSize: 13,
              lineHeight: 1.55,
              color: 'var(--ink)',
            }}
          />

          <div style={{ display: 'flex', gap: 10 }}>
            <HFBtn
              variant="ghost"
              style={{ flex: 1 }}
              onClick={handleSaveAllAsDraft}
              disabled={batchSubmitting || pendingCount === 0}
            >保存草稿</HFBtn>
            <HFBtn
              variant="primary"
              iconRight={I.arrowRight(14)}
              style={{ flex: 1.4 }}
              onClick={handleSubmitAll}
              disabled={batchSubmitting || pendingCount === 0}
            >{batchSubmitting ? '提交中…' : `全部提交 (${pendingCount})`}</HFBtn>
          </div>
          <div className="hf-cap" style={{ textAlign: 'center' }}>
            提交后 → 审核员双签 → 进对应赛道 → 学生 5 分钟内可见
          </div>

          {/* weekly stats */}
          <div className="hf-card warm" style={{ padding: 14, borderRadius: 14, marginTop: 'auto' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="hf-overline">本周你的录入</span>
              <span className="hf-cap">配额 {stats?.week_used ?? 0} / {stats?.week_quota ?? 30}</span>
            </div>
            <div style={{ display: 'flex', gap: 12 }}>
              {([
                ['通过', stats?.week_passed ?? 0, 'var(--emerald)'],
                ['在审', stats?.week_pending ?? 0, 'var(--amber-fg)'],
                ['驳回', stats?.week_rejected ?? 0, 'var(--crimson)'],
              ] as Array<[string, number, string]>).map(([l, n, c]) => (
                <div
                  key={l}
                  style={{
                    flex: 1,
                    padding: '10px 12px',
                    background: 'var(--ivory)',
                    borderRadius: 10,
                    boxShadow: '0 0 0 1px var(--border-warm)',
                  }}
                >
                  <div className="hf-cap">{l}</div>
                  <div style={{ fontFamily: 'var(--font-serif)', fontSize: 24, fontWeight: 600, color: c, marginTop: 2 }}>{n}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {toast && (
        <div
          className="hf-slide"
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '12px 18px',
            borderRadius: 99,
            background: 'var(--deep-dark)',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            fontSize: 13.5,
            boxShadow: '0 12px 32px rgba(0,0,0,0.18)',
            zIndex: 50,
          }}
        >
          <span style={{ color: 'var(--emerald)', display: 'inline-flex' }}>{I.check(14)}</span>
          {toast}
        </div>
      )}
    </div>
  );
}

export default HFTeacher;
