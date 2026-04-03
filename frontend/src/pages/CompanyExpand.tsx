import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Table, Card, Space, Tag, Button, Descriptions, Select, Empty, Spin, Alert, Modal, Input, InputNumber, Segmented, message,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { addCompanyRecrawlTask, getCompanyJobs, getTracks, updateJobApplicationStatus } from '../api';

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
  { value: '一面', label: '一面' },
  { value: '二面', label: '二面' },
  { value: '三面', label: '三面' },
];

export default function CompanyExpand() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  const company = searchParams.get('company') || '';
  const department = searchParams.get('department') || '';
  const initialScope = searchParams.get('scope') || 'current';
  const initialSearch = searchParams.get('search') || '';
  const initialTracks = searchParams.get('tracks') || '';
  const initialDays = searchParams.get('days') || '';
  const initialMinScore = searchParams.get('min_score') || '';
  const initialJobStage = searchParams.get('job_stage') || 'campus';

  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [scope, setScope] = useState<string>(initialScope);
  const [inheritMainFilters, setInheritMainFilters] = useState<boolean>(initialScope === 'current');
  const [search, setSearch] = useState<string>(initialSearch);
  const [trackFilter, setTrackFilter] = useState<string | undefined>(initialTracks || undefined);
  const [days, setDays] = useState<number | undefined>(initialDays ? parseInt(initialDays, 10) : undefined);
  const [minScore, setMinScore] = useState<number | undefined>(initialMinScore ? parseInt(initialMinScore, 10) : undefined);
  const [jobStage, setJobStage] = useState<string>(initialJobStage || 'campus');
  const [trackOptions, setTrackOptions] = useState<TrackOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recrawlModalOpen, setRecrawlModalOpen] = useState(false);
  const [recrawlUrl, setRecrawlUrl] = useState('');
  const [recrawlSubmitting, setRecrawlSubmitting] = useState(false);

  const fetchJobs = useCallback(async () => {
    if (!company) {
      setError('缺少公司参数');
      return;
    }

    const effectiveSearch = inheritMainFilters ? initialSearch : search;
    const effectiveTracks = inheritMainFilters ? initialTracks : (trackFilter || '');
    const effectiveDays = inheritMainFilters ? (initialDays ? parseInt(initialDays, 10) : undefined) : days;
    const effectiveMinScore = inheritMainFilters ? (initialMinScore ? parseInt(initialMinScore, 10) : undefined) : minScore;
    const effectiveJobStage = inheritMainFilters ? initialJobStage : jobStage;

    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        company,
        scope,
        page,
        page_size: pageSize,
      };
      if (department) params.department = department;

      if (effectiveSearch) params.search = effectiveSearch;
      if (effectiveTracks) params.tracks = effectiveTracks;
      if (effectiveDays) params.days = effectiveDays;
      if (effectiveMinScore) params.min_score = effectiveMinScore;
      if (effectiveJobStage) params.job_stage = effectiveJobStage;

      const res = await getCompanyJobs(params);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      setError('加载失败，请重试');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [
    company,
    department,
    scope,
    page,
    pageSize,
    inheritMainFilters,
    initialSearch,
    initialTracks,
    initialDays,
    initialMinScore,
    initialJobStage,
    search,
    trackFilter,
    days,
    minScore,
    jobStage,
  ]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    const loadTracks = async () => {
      try {
        const res = await getTracks();
        setTrackOptions(res.data.map((t: TrackOption) => ({ key: t.key, name: t.name })));
      } catch {
        // ignore
      }
    };
    loadTracks();
  }, []);

  const handleScopeChange = (newScope: string) => {
    setScope(newScope);
    setPage(1);
  };

  const handleBack = () => {
    navigate('/');
  };

  const handleUpdateApplicationStatus = async (job: JobItem, nextStatus: string) => {
    const currentStatus = job.application_status || '待申请';
    if (nextStatus === currentStatus) return;

    setJobs((prev) => prev.map((item) => (
      item.id === job.id ? { ...item, application_status: nextStatus } : item
    )));

    try {
      await updateJobApplicationStatus(job.id, { application_status: nextStatus });
    } catch {
      setJobs((prev) => prev.map((item) => (
        item.id === job.id ? { ...item, application_status: currentStatus } : item
      )));
    }
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
        company,
        department,
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
    { title: '分行/部门', dataIndex: 'department', width: 180, ellipsis: true, render: (v: string) => v || '-' },
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

  const effectiveSearch = inheritMainFilters ? initialSearch : search;
  const effectiveTracks = inheritMainFilters ? initialTracks : (trackFilter || '');
  const effectiveDays = inheritMainFilters ? initialDays : (days ? String(days) : '');
  const effectiveMinScore = inheritMainFilters ? initialMinScore : (minScore ? String(minScore) : '');
  const effectiveJobStage = inheritMainFilters ? initialJobStage : jobStage;

  if (!company) {
    return (
      <Empty
        description="缺少公司参数"
        image={Empty.PRESENTED_IMAGE_SIMPLE}
      >
        <Button type="primary" onClick={handleBack}>返回岗位总览</Button>
      </Empty>
    );
  }

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space>
            <Button icon={<ArrowLeftOutlined />} onClick={handleBack}>
              返回
            </Button>
            <Button onClick={() => setRecrawlModalOpen(true)}>
              重新爬取全量岗位
            </Button>
            <span style={{ fontSize: 16, fontWeight: 600 }}>
              {company}{department ? ` - ${department}` : ''}
            </span>
          </Space>
          <Space wrap>
            <span>数据范围：</span>
            <Select
              value={scope}
              onChange={handleScopeChange}
              style={{ width: 150 }}
              options={[
                { value: 'current', label: '当前筛选条件' },
                { value: 'all', label: '全部数据' },
              ]}
            />
            <Button
              type={inheritMainFilters ? 'primary' : 'default'}
              onClick={() => {
                setInheritMainFilters((v) => !v);
                setPage(1);
              }}
            >
              {inheritMainFilters ? '已继承主页面筛选（点击关闭）' : '未继承主页面筛选（点击开启）'}
            </Button>
          </Space>

          <Space wrap>
            <Segmented
              value={jobStage}
              options={[
                { label: '校招', value: 'campus' },
                { label: '实习', value: 'internship' },
                { label: '全部', value: 'all' },
              ]}
              onChange={(v) => { setJobStage(String(v)); setPage(1); }}
              disabled={inheritMainFilters}
            />
            <Input
              placeholder="搜索岗位/地点/要求"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              style={{ width: 220 }}
              allowClear
              disabled={inheritMainFilters}
            />
            <Select
              placeholder="赛道筛选"
              value={trackFilter}
              onChange={(v) => { setTrackFilter(v); setPage(1); }}
              style={{ width: 160 }}
              allowClear
              disabled={inheritMainFilters}
              options={trackOptions.map(t => ({ value: t.key, label: t.name }))}
            />
            <Select
              placeholder="时间范围"
              value={days}
              onChange={(v) => { setDays(v); setPage(1); }}
              style={{ width: 120 }}
              allowClear
              disabled={inheritMainFilters}
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
              onChange={(v) => { setMinScore(v ?? undefined); setPage(1); }}
              style={{ width: 110 }}
              min={0}
              disabled={inheritMainFilters}
            />
          </Space>

          <Space wrap>
            <Tag color="blue">搜索: {effectiveSearch || '-'}</Tag>
            <Tag color="purple">赛道: {effectiveTracks || '-'}</Tag>
            <Tag color="green">{effectiveDays ? `${effectiveDays}天内` : '不限时间'}</Tag>
            <Tag color="orange">最低分: {effectiveMinScore || 0}</Tag>
            <Tag color="geekblue">类型: {effectiveJobStage === 'campus' ? '校招' : effectiveJobStage === 'internship' ? '实习' : '全部'}</Tag>
          </Space>
        </Space>
      </Card>

      {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}

      <Spin spinning={loading}>
        <Table<JobItem>
          rowKey="id"
          columns={columns}
          dataSource={jobs}
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
          scroll={{ x: 700 }}
        />
      </Spin>

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
            公司：<b>{company || '-'}</b>
            {department && department !== company ? `（${department}）` : ''}
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
