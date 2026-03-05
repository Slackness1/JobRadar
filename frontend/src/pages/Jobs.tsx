import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  Table, Input, Select, InputNumber, Card, Row, Col, Statistic, Button,
  Space, Tag, Dropdown, message, Descriptions, Modal, Segmented,
} from 'antd';
import {
  DownloadOutlined, SearchOutlined, UploadOutlined, ReloadOutlined,
  SaveOutlined, DeleteOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getJobs,
  getJobStats,
  getTracks,
  exportCsv,
  exportExcel,
  importCsv,
  updateJobApplicationStatus,
  addCompanyRecrawlTask,
} from '../api';

interface JobScoreItem {
  track_id: number;
  track_key: string;
  track_name: string;
  score: number;
  matched_keywords: string;
}

interface JobItem {
  id: number;
  job_id: string;
  company: string;
  company_type_industry: string;
  department: string;
  job_title: string;
  location: string;
  major_req: string;
  job_req: string;
  job_duty: string;
  application_status: string;
  job_stage: string;
  publish_date: string | null;
  detail_url: string;
  total_score: number;
  scores: JobScoreItem[];
}

interface TrackOption {
  key: string;
  name: string;
}

interface StatsData {
  total_jobs: number;
  today_new: number;
  by_track: Record<string, number>;
  by_stage?: Record<string, number>;
}

interface SavedFilterPreset {
  id: string;
  name: string;
  search: string;
  trackFilter?: string;
  days?: number;
  minScore?: number;
  jobStage?: string;
  createdAt: string;
}

interface LastFilterState {
  search: string;
  trackFilter?: string;
  days?: number;
  minScore?: number;
  jobStage?: string;
}

const SAVED_FILTERS_KEY = 'jobradar.savedFilters.v1';
const LAST_FILTER_KEY = 'jobradar.lastFilterState.v2';

function loadSavedFilters(): SavedFilterPreset[] {
  try {
    const raw = localStorage.getItem(SAVED_FILTERS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item) => item && typeof item.id === 'string' && typeof item.name === 'string');
  } catch {
    return [];
  }
}

function saveSavedFilters(filters: SavedFilterPreset[]) {
  try {
    localStorage.setItem(SAVED_FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // ignore localStorage write errors
  }
}

function loadLastFilterState(): LastFilterState {
  try {
    const raw = localStorage.getItem(LAST_FILTER_KEY);
    if (!raw) return { search: '' };
    const parsed = JSON.parse(raw);
    return {
      search: typeof parsed.search === 'string' ? parsed.search : '',
      trackFilter: typeof parsed.trackFilter === 'string' ? parsed.trackFilter : undefined,
      days: typeof parsed.days === 'number' ? parsed.days : undefined,
      minScore: typeof parsed.minScore === 'number' ? parsed.minScore : undefined,
      jobStage: typeof parsed.jobStage === 'string' ? parsed.jobStage : 'campus',
    };
  } catch {
    return { search: '', jobStage: 'campus' };
  }
}

function saveLastFilterState(state: LastFilterState) {
  try {
    localStorage.setItem(LAST_FILTER_KEY, JSON.stringify(state));
  } catch {
    // ignore localStorage write errors
  }
}

const TRACK_COLORS: Record<string, string> = {
  data_analysis: 'blue',
  tech_consulting: 'purple',
  ai_pm: 'cyan',
  investment_research: 'gold',
  power_trading: 'green',
};

const APPLICATION_STATUS_OPTIONS = [
  { value: '待申请', label: '待申请' },
  { value: '已申请', label: '已申请' },
  { value: '已网测', label: '已网测' },
  { value: '已面试', label: '已面试' },
];

export default function Jobs() {
  const initialFilterState = useMemo(() => loadLastFilterState(), []);
  const navigate = useNavigate();

  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState(initialFilterState.search);
  const [trackFilter, setTrackFilter] = useState<string | undefined>(initialFilterState.trackFilter);
  const [days, setDays] = useState<number | undefined>(initialFilterState.days);
  const [minScore, setMinScore] = useState<number | undefined>(initialFilterState.minScore);
  const [jobStage, setJobStage] = useState<string>(initialFilterState.jobStage || 'campus');
  const [stats, setStats] = useState<StatsData>({ total_jobs: 0, today_new: 0, by_track: {}, by_stage: {} });
  const [trackOptions, setTrackOptions] = useState<TrackOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [savedFilters, setSavedFilters] = useState<SavedFilterPreset[]>(() => loadSavedFilters());
  const [selectedPresetId, setSelectedPresetId] = useState<string>();
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [presetName, setPresetName] = useState('');
  const [recrawlModalOpen, setRecrawlModalOpen] = useState(false);
  const [recrawlCompany, setRecrawlCompany] = useState('');
  const [recrawlDepartment, setRecrawlDepartment] = useState('');
  const [recrawlUrl, setRecrawlUrl] = useState('');
  const [recrawlSubmitting, setRecrawlSubmitting] = useState(false);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        page, page_size: pageSize, sort_by: 'total_score', sort_order: 'desc',
      };
      if (search) params.search = search;
      if (trackFilter) params.tracks = trackFilter;
      if (days) params.days = days;
      if (minScore) params.min_score = minScore;
      if (jobStage) params.job_stage = jobStage;
      const res = await getJobs(params);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, trackFilter, days, minScore, jobStage]);
  const handleCompanyClick = (company: string, department: string) => {
    const params = new URLSearchParams({
      company,
      department,
      scope: 'current',
    });
    if (search) params.set('search', search);
    if (trackFilter) params.set('tracks', trackFilter);
    if (days) params.set('days', String(days));
    if (minScore) params.set('min_score', String(minScore));
    if (jobStage) params.set('job_stage', jobStage);
    navigate(`/company-expand?${params.toString()}`);
  };


  const fetchStats = async () => {
    const res = await getJobStats();
    setStats(res.data);
  };

  const fetchTracks = async () => {
    const res = await getTracks();
    setTrackOptions(res.data.map((t: TrackOption) => ({ key: t.key, name: t.name })));
  };

  useEffect(() => { fetchTracks(); fetchStats(); }, []);
  useEffect(() => { fetchJobs(); }, [fetchJobs]);
  useEffect(() => {
    saveLastFilterState({ search, trackFilter, days, minScore, jobStage });
  }, [search, trackFilter, days, minScore, jobStage]);

  const applyPreset = (presetId: string) => {
    const preset = savedFilters.find((p) => p.id === presetId);
    if (!preset) return;
    setSelectedPresetId(preset.id);
    setSearch(preset.search);
    setTrackFilter(preset.trackFilter);
    setDays(preset.days);
    setMinScore(preset.minScore);
    setJobStage(preset.jobStage || 'campus');
    setPage(1);
    message.success(`已应用筛选：${preset.name}`);
  };

  const openSaveModal = () => {
    const current = savedFilters.find((p) => p.id === selectedPresetId);
    setPresetName(current?.name || '');
    setSaveModalOpen(true);
  };

  const handleSavePreset = () => {
    const name = presetName.trim();
    if (!name) {
      message.warning('请输入筛选名称');
      return;
    }

    setSavedFilters((prev) => {
      const existing = prev.find((p) => p.name === name);
      if (existing && existing.id !== selectedPresetId) {
        const confirmed = window.confirm(`已存在同名筛选「${name}」，是否覆盖？`);
        if (!confirmed) return prev;
      }

      const now = new Date().toISOString();
      const id = existing?.id || selectedPresetId || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const nextPreset: SavedFilterPreset = {
        id,
        name,
        search,
        trackFilter,
        days,
        minScore,
        jobStage,
        createdAt: existing?.createdAt || now,
      };

      const nextList = prev.filter((p) => p.id !== id).concat(nextPreset);
      saveSavedFilters(nextList);
      setSelectedPresetId(id);
      return nextList;
    });

    setSaveModalOpen(false);
    setPresetName('');
    message.success('筛选已保存');
  };

  const handleDeletePreset = () => {
    if (!selectedPresetId) return;
    const target = savedFilters.find((p) => p.id === selectedPresetId);
    if (!target) return;
    const confirmed = window.confirm(`确认删除筛选「${target.name}」？`);
    if (!confirmed) return;

    setSavedFilters((prev) => {
      const nextList = prev.filter((p) => p.id !== selectedPresetId);
      saveSavedFilters(nextList);
      return nextList;
    });
    setSelectedPresetId(undefined);
    message.success('已删除筛选');
  };

  const handleExport = async (format: string) => {
    const params = {
      search: search || '',
      tracks: trackFilter ? trackFilter.split(',') : [],
      min_score: minScore || 0,
      days: days || 0,
      job_stage: jobStage || 'all',
    };
    try {
      const fn = format === 'excel' ? exportExcel : exportCsv;
      const res = await fn(params);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `jobs_export.${format === 'excel' ? 'xlsx' : 'csv'}`;
      a.click();
      window.URL.revokeObjectURL(url);
      message.success('导出成功');
    } catch {
      message.error('导出失败');
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      message.loading({ content: '导入中...', key: 'import' });
      const res = await importCsv(file);
      message.success({
        content: `导入 ${res.data.imported} 条岗位，评分 ${res.data.scored} 条`,
        key: 'import',
      });
      fetchJobs();
      fetchStats();
    } catch {
      message.error({ content: '导入失败', key: 'import' });
    }
    e.target.value = '';
  };

  const handleUpdateApplicationStatus = async (job: JobItem, nextStatus: string) => {
    const currentStatus = job.application_status || '待申请';
    if (nextStatus === currentStatus) return;

    setJobs((prev) => prev.map((item) => (
      item.id === job.id ? { ...item, application_status: nextStatus } : item
    )));

    try {
      await updateJobApplicationStatus(job.id, { application_status: nextStatus });
      message.success('申请状态已更新');
    } catch {
      setJobs((prev) => prev.map((item) => (
        item.id === job.id ? { ...item, application_status: currentStatus } : item
      )));
      message.error('申请状态更新失败');
    }
  };

  const openRecrawlModal = (company: string, department: string) => {
    setRecrawlCompany(company || '');
    setRecrawlDepartment(department || '');
    setRecrawlUrl('');
    setRecrawlModalOpen(true);
  };

  const submitRecrawlTask = async () => {
    const url = recrawlUrl.trim();
    if (!url) {
      message.warning('请填写公司官网招聘链接');
      return;
    }

    setRecrawlSubmitting(true);
    try {
      await addCompanyRecrawlTask({
        company: recrawlCompany,
        department: recrawlDepartment,
        career_url: url,
      });
      message.success('已加入补爬队列，将在下次爬取时执行');
      setRecrawlModalOpen(false);
      setRecrawlUrl('');
    } catch {
      message.error('加入补爬队列失败，请检查链接后重试');
    } finally {
      setRecrawlSubmitting(false);
    }
  };

  const columns: ColumnsType<JobItem> = [
    {
      title: '公司', dataIndex: 'company', width: 130, ellipsis: true,
      render: (v: string, r: JobItem) => (
        <div>
          <div
            style={{ cursor: 'pointer' }}
            onClick={() => handleCompanyClick(v, r.department)}
          >
            <div style={{ fontWeight: 500, color: '#1890ff' }}>{v}</div>
            {r.department && r.department !== v && (
              <div style={{ fontSize: 11, color: '#888' }}>{r.department}</div>
            )}
          </div>
          <Button
            type="link"
            size="small"
            style={{ padding: 0, height: 20 }}
            onClick={(e) => {
              e.stopPropagation();
              openRecrawlModal(v, r.department);
            }}
          >
            重新爬取全量岗位
          </Button>
        </div>
      ),
    },
    { title: '岗位', dataIndex: 'job_title', width: 220, ellipsis: true },
    { title: '地点', dataIndex: 'location', width: 100, ellipsis: true },
    {
      title: '申请状态', dataIndex: 'application_status', width: 110,
      render: (_v: string, r: JobItem) => (
        <Select
          size="small"
          value={r.application_status || '待申请'}
          style={{ width: 100 }}
          options={APPLICATION_STATUS_OPTIONS}
          onChange={(value) => handleUpdateApplicationStatus(r, value)}
        />
      ),
    },
    {
      title: '赛道', key: 'tracks', width: 200,
      render: (_: unknown, r: JobItem) => (
        <Space size={[0, 4]} wrap>
          {r.scores.map(s => (
            <Tag key={s.track_key} color={TRACK_COLORS[s.track_key] || 'default'}>
              {s.track_name} {s.score}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '总分', dataIndex: 'total_score', width: 75, sorter: true,
      render: (v: number) => <span style={{ fontWeight: 700, color: v >= 60 ? '#52c41a' : v >= 30 ? '#1890ff' : '#999' }}>{v}</span>,
    },
    {
      title: '发布', dataIndex: 'publish_date', width: 90,
      render: (v: string | null) => v ? v.slice(0, 10) : '-',
    },
    {
      title: '', dataIndex: 'detail_url', width: 50,
      render: (v: string) => v ? <a href={v} target="_blank" rel="noreferrer">链接</a> : null,
    },
  ];

  const expandedRowRender = (record: JobItem) => (
    <Descriptions column={2} size="small" bordered>
      <Descriptions.Item label="岗位要求" span={2}>
        <div style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
          {record.job_req || '-'}
        </div>
      </Descriptions.Item>
      <Descriptions.Item label="岗位职责" span={2}>
        <div style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto', fontSize: 12 }}>
          {record.job_duty || '-'}
        </div>
      </Descriptions.Item>
      {record.scores.map(s => {
        let keywords: string[] = [];
        try { keywords = JSON.parse(s.matched_keywords || '[]'); } catch { /* ignore */ }
        return (
          <Descriptions.Item key={s.track_key} label={`${s.track_name} 匹配词`} span={2}>
            {keywords.map((kw, i) => <Tag key={i} style={{ marginBottom: 2 }}>{kw}</Tag>)}
          </Descriptions.Item>
        );
      })}
    </Descriptions>
  );

  return (
    <div>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Card size="small"><Statistic title="总岗位" value={stats.total_jobs} /></Card>
        </Col>
        <Col flex="auto">
          <Card size="small"><Statistic title="今日新增" value={stats.today_new} valueStyle={{ color: '#52c41a' }} /></Card>
        </Col>
        <Col flex="auto">
          <Card size="small"><Statistic title="校招岗位" value={stats.by_stage?.campus || 0} valueStyle={{ color: '#1677ff' }} /></Card>
        </Col>
        <Col flex="auto">
          <Card size="small"><Statistic title="实习岗位" value={stats.by_stage?.internship || 0} valueStyle={{ color: '#13c2c2' }} /></Card>
        </Col>
        {trackOptions.map(t => (
          <Col flex="auto" key={t.key}>
            <Card size="small"><Statistic title={t.name} value={stats.by_track?.[t.key] || 0} /></Card>
          </Col>
        ))}
      </Row>

      <Space style={{ marginBottom: 12 }} wrap>
        <Segmented
          value={jobStage}
          options={[
            { label: '校招岗位', value: 'campus' },
            { label: '实习岗位', value: 'internship' },
            { label: '全部岗位', value: 'all' },
          ]}
          onChange={(v) => { setJobStage(String(v)); setPage(1); }}
        />
        <Input
          prefix={<SearchOutlined />}
          placeholder="搜索公司/岗位/地点..."
          value={search}
          onChange={e => { setSearch(e.target.value); setPage(1); }}
          style={{ width: 220 }}
          allowClear
        />
        <Select
          placeholder="赛道筛选"
          value={trackFilter}
          onChange={v => { setTrackFilter(v); setPage(1); }}
          style={{ width: 150 }}
          allowClear
          options={trackOptions.map(t => ({ value: t.key, label: t.name }))}
        />
        <Select
          placeholder="时间范围"
          value={days}
          onChange={v => { setDays(v); setPage(1); }}
          style={{ width: 110 }}
          allowClear
          options={[
            { value: 1, label: '1 天' },
            { value: 3, label: '3 天' },
            { value: 7, label: '7 天' },
            { value: 14, label: '14 天' },
            { value: 30, label: '30 天' },
          ]}
        />
        <InputNumber
          placeholder="最低分"
          value={minScore}
          onChange={v => { setMinScore(v ?? undefined); setPage(1); }}
          style={{ width: 100 }}
          min={0}
        />
        <Select
          placeholder="已保存筛选"
          value={selectedPresetId}
          onChange={applyPreset}
          style={{ width: 180 }}
          allowClear
          onClear={() => setSelectedPresetId(undefined)}
          options={savedFilters.map((p) => ({ value: p.id, label: p.name }))}
        />
        <Button icon={<SaveOutlined />} onClick={openSaveModal}>
          保存筛选
        </Button>
        <Button icon={<DeleteOutlined />} onClick={handleDeletePreset} disabled={!selectedPresetId}>
          删除筛选
        </Button>
        <Button icon={<ReloadOutlined />} onClick={() => { fetchJobs(); fetchStats(); }}>
          刷新
        </Button>
        <Dropdown menu={{
          items: [
            { key: 'csv', label: '导出 CSV', onClick: () => handleExport('csv') },
            { key: 'excel', label: '导出 Excel', onClick: () => handleExport('excel') },
          ],
        }}>
          <Button icon={<DownloadOutlined />}>导出</Button>
        </Dropdown>
        <Button icon={<UploadOutlined />} onClick={() => document.getElementById('csv-upload')?.click()}>
          导入 CSV
        </Button>
        <input id="csv-upload" type="file" accept=".csv" hidden onChange={handleImport} />
      </Space>

      <Table<JobItem>
        rowKey="id"
        columns={columns}
        dataSource={jobs}
        loading={loading}
        expandable={{ expandedRowRender }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: t => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        size="small"
        scroll={{ x: 900 }}
      />

      <Modal
        title="保存筛选"
        open={saveModalOpen}
        onOk={handleSavePreset}
        onCancel={() => setSaveModalOpen(false)}
        okText="保存"
        cancelText="取消"
      >
        <Input
          placeholder="例如：高分数据分析(7天)"
          value={presetName}
          onChange={(e) => setPresetName(e.target.value)}
          onPressEnter={handleSavePreset}
          maxLength={40}
        />
      </Modal>

      <Modal
        title="补爬公司自有官网"
        open={recrawlModalOpen}
        onOk={submitRecrawlTask}
        onCancel={() => setRecrawlModalOpen(false)}
        okText="加入下次爬取"
        cancelText="取消"
        confirmLoading={recrawlSubmitting}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            公司：<b>{recrawlCompany || '-'}</b>
            {recrawlDepartment && recrawlDepartment !== recrawlCompany ? `（${recrawlDepartment}）` : ''}
          </div>
          <Input
            placeholder="请输入公司招聘官网链接，例如 https://careers.example.com/jobs"
            value={recrawlUrl}
            onChange={(e) => setRecrawlUrl(e.target.value)}
            onPressEnter={submitRecrawlTask}
          />
        </Space>
      </Modal>
    </div>
  );
}
