import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  Table, Card, Space, Tag, Button, Descriptions, Select, Empty, Spin, Alert, Modal, Input, message,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { addCompanyRecrawlTask, getCompanyJobs, updateJobApplicationStatus } from '../api';

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
  const initialJobStage = searchParams.get('job_stage') || 'all';

  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [scope, setScope] = useState<string>(initialScope);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recrawlModalOpen, setRecrawlModalOpen] = useState(false);
  const [recrawlUrl, setRecrawlUrl] = useState('');
  const [recrawlSubmitting, setRecrawlSubmitting] = useState(false);

  const fetchJobs = useCallback(async () => {
    if (!company || !department) {
      setError('缺少公司或部门参数');
      return;
    }
    
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, unknown> = {
        company,
        department,
        scope,
        page,
        page_size: pageSize,
      };
      
      if (scope === 'current') {
        if (initialSearch) params.search = initialSearch;
        if (initialTracks) params.tracks = initialTracks;
        if (initialDays) params.days = parseInt(initialDays, 10);
        if (initialMinScore) params.min_score = parseInt(initialMinScore, 10);
        if (initialJobStage) params.job_stage = initialJobStage;
      }
      
      const res = await getCompanyJobs(params);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } catch (err) {
      setError('加载失败，请重试');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [company, department, scope, page, pageSize, initialSearch, initialTracks, initialDays, initialMinScore, initialJobStage]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

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

  if (!company || !department) {
    return (
      <Empty
        description="缺少公司或部门参数"
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
              {company} - {department}
            </span>
          </Space>
          <Space>
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
            {scope === 'current' && (initialSearch || initialTracks || initialDays || initialMinScore) && (
              <Space>
                <Tag color="blue">搜索: {initialSearch || '-'}</Tag>
                <Tag color="purple">赛道: {initialTracks || '-'}</Tag>
                <Tag color="green">{initialDays ? `${initialDays}天内` : '不限时间'}</Tag>
                <Tag color="orange">最低分: {initialMinScore || 0}</Tag>
                <Tag color="geekblue">类型: {initialJobStage === 'campus' ? '校招' : initialJobStage === 'internship' ? '实习' : '全部'}</Tag>
              </Space>
            )}
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
