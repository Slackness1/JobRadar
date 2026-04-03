import { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

import {
  Table, Input, Select, InputNumber, Card, Row, Col, Statistic, Button,
  Space, Tag, Dropdown, message, Descriptions, Modal, Segmented,
} from 'antd';
import {
  DownloadOutlined, SearchOutlined, UploadOutlined, ReloadOutlined,
  SaveOutlined, DeleteOutlined, InfoCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getJobs,
  getJobsByCompany,
  getJobStats,
  getTracks,
  exportCsv,
  exportExcel,
  importCsv,
  updateJobApplicationStatus,
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

// 赛道分组：互联网、银行、其他
const TRACK_GROUPS = {
  internet: {
    name: '互联网',
    tracks: ['internet_tier1', 'internet_tier2', 'internet_tier3'],
  },
  bank: {
    name: '银行',
    tracks: ['bank_tier1', 'bank_tier2', 'bank_tier3'],
  },
  other: {
    name: '其他',
    tracks: ['other_fintech', 'other_state', 'other_foreign'],
  },
};

// ==================== 行业梯队分类 ====================

// 互联网梯队分类
const INTERNET_TIERS: Record<string, { name: string; companies: string[] }> = {
  tier1: {
    name: '一线',
    companies: [
      '腾讯', '字节跳动', '阿里巴巴', '蚂蚁集团', '美团', '拼多多',
    ],
  },
  tier2: {
    name: '二线',
    companies: [
      '京东', '百度', '快手', '滴滴', '网易', '携程', '小红书',
      'BOSS直聘', '小米', '哔哩哔哩', 'B站', '米哈游', '得物',
    ],
  },
  tier3: {
    name: '三线',
    companies: [
      // 内容/社区/媒体
      '爱奇艺', '知乎', '新浪微博', '微博', '搜狐', '阅文集团', '虎牙', '斗鱼',
      '欢聚', 'YY', '豆瓣', 'Soul', '喜马拉雅', '蜻蜓FM', '虎扑', '即刻',
      // 电商/消费/本地生活
      '唯品会', '盒马', '饿了么', '叮咚买菜', '名创优品', '苏宁', '泡泡玛特', '元气森林',
      // 出行/旅游/汽车
      '去哪儿', '同程旅行', '哈啰', '货拉拉', '汽车之家', '途虎养车', '贝壳', '链家', '自如',
      // 游戏
      '心动网络', 'TapTap', '莉莉丝', '巨人网络', '完美世界', '三七互娱', '昆仑万维', '西山居', '恺英网络',
      // 工具/企业服务/招聘/金融科技
      '360', '金山办公', '金山云', '同花顺', '东方财富', '陆金所',
      '微盟', '有赞', '七牛云', 'UCloud', 'Moka', '猎聘', '前程无忧', '智联招聘', '收钱吧',
    ],
  },
  tier4: {
    name: '三线以后',
    companies: [
      '雪球', '美图', '当当', '马蜂窝', '咪咕', '唱吧', '微店', '返利网',
      '宝宝树', '珍爱网', '婚礼纪', '花瓣网', '咕咚', '达达', '兑吧',
      '百姓网', '洋码头', '探探', 'WiFi万能钥匙', '神州数码', '格瓦拉',
      '识货', '脉脉',
    ],
  },
};

// 券商梯队分类
const SECURITIES_TIERS: Record<string, { name: string; companies: string[] }> = {
  tier1: {
    name: 'A-头部核心池',
    companies: [
      '中金公司', '中金', '中信证券', '中信建投证券', '华泰证券',
      '国泰海通证券', '国泰君安证券', '海通证券', '申万宏源证券', '申万宏源',
    ],
  },
  tier2: {
    name: 'B-准头部+上腰部',
    companies: [
      '广发证券', '招商证券', '中国银河证券', '银河证券', '东吴证券', '华创证券',
      '国海证券', '兴业证券', '东方证券', '国信证券', '光大证券', '平安证券',
      '国金证券', '国投证券', '浙商证券', '长江证券', '东方财富证券',
    ],
  },
  tier3: {
    name: 'C-标准腰部',
    companies: [
      '天风证券', '中泰证券', '国盛证券', '方正证券', '民生证券',
      '国联证券', '开源证券', '华西证券', '德邦证券', '东北证券',
      '信达证券', '财通证券', '华福证券', '国元证券', '粤开证券',
      '东莞证券', '中银证券',
    ],
  },
};

// 银行梯队分类
const BANK_TIERS: Record<string, { name: string; companies: string[] }> = {
  tier1: {
    name: '第一梯队',
    companies: [
      '浦发银行', '招商银行', '兴业银行', '上海农商银行', '上海银行', '宁波银行', '浙商银行',
    ],
  },
  tier2: {
    name: '第二梯队',
    companies: [
      '中信银行', '中国邮政储蓄银行', '邮储银行', '交通银行', '北京银行',
      '建设银行', '农业银行', '工商银行', '中国银行', '平安银行', '民生银行',
      '光大银行', '华夏银行', '建信金科', '招银网络科技', '浦银金融科技',
    ],
  },
  tier3: {
    name: '第三梯队',
    companies: [
      '杭州银行', '苏州银行', '成都银行', '西安银行', '南洋商业银行', '北京农商',
    ],
  },
};

// 判断公司属于哪个梯队
function getCompanyTier(company: string): { tier: string; tierName: string; category: string } | null {
  const trimmedCompany = company.trim();

  // 检查互联网梯队
  for (const [tierKey, tierInfo] of Object.entries(INTERNET_TIERS)) {
    if (tierInfo.companies.some(c => trimmedCompany.includes(c))) {
      return { tier: tierKey, tierName: tierInfo.name, category: '互联网' };
    }
  }

  // 检查券商梯队
  for (const [tierKey, tierInfo] of Object.entries(SECURITIES_TIERS)) {
    if (tierInfo.companies.some(c => trimmedCompany.includes(c))) {
      return { tier: tierKey, tierName: tierInfo.name, category: '券商' };
    }
  }

  // 检查银行梯队
  for (const [tierKey, tierInfo] of Object.entries(BANK_TIERS)) {
    if (tierInfo.companies.some(c => trimmedCompany.includes(c))) {
      return { tier: tierKey, tierName: tierInfo.name, category: '银行' };
    }
  }

  return null;
}

// 梯队颜色配置
const TIER_COLORS: Record<string, string> = {
  tier1: 'gold',
  tier2: 'blue',
  tier3: 'default',
  tier4: 'volcano',
};

// 梯队排序值：tier1=1, tier2=2, tier3=3, tier4=4, 无梯队=99
function tierSortValue(company: string): number {
  const info = getCompanyTier(company);
  if (!info) return 99;
  return parseInt(info.tier.replace('tier', '')) || 99;
}

// 梯队排序比较器：梯队小→优先，同梯队按总分降序，同分按公司名
function compareByTier(a: JobItem, b: JobItem): number {
  const ta = tierSortValue(a.company);
  const tb = tierSortValue(b.company);
  if (ta !== tb) return ta - tb;                              // 不同梯队：小的排前面
  if (a.total_score !== b.total_score) return b.total_score - a.total_score; // 同梯队：总分高→排前面
  return a.company.localeCompare(b.company, 'zh');            // 同分：按公司名
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
  sectorGroup?: string;
  days?: number;
  minScore?: number;
  jobStage?: string;
  createdAt: string;
}

interface LastFilterState {
  search: string;
  sectorGroup?: string;
  days?: number;
  minScore?: number;
  jobStage?: string;
  excludeAppliedCompanies?: boolean;
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
      sectorGroup: typeof parsed.sectorGroup === 'string' ? parsed.sectorGroup : 'all',
      days: typeof parsed.days === 'number' ? parsed.days : undefined,
      minScore: typeof parsed.minScore === 'number' ? parsed.minScore : undefined,
      jobStage: typeof parsed.jobStage === 'string' ? parsed.jobStage : 'campus',
      excludeAppliedCompanies: Boolean(parsed.excludeAppliedCompanies),
    };
  } catch {
    return { search: '', jobStage: 'campus', excludeAppliedCompanies: false };
  }
}

function saveLastFilterState(state: LastFilterState) {
  try {
    localStorage.setItem(LAST_FILTER_KEY, JSON.stringify(state));
  } catch {
    // ignore localStorage write errors
  }
}

// 根据赛道分组计算应该筛选的赛道
const getTracksByGroup = (group: string, tracks: TrackOption[]): string[] => {
  if (group === 'all') {
    return tracks.map(t => t.key);
  }
  const groupTracks = TRACK_GROUPS[group as keyof typeof TRACK_GROUPS]?.tracks || [];
  const otherTracks = tracks.map(t => t.key).filter(key => !Object.values(TRACK_GROUPS).flatMap(g => g.tracks).includes(key));
  if (group === 'other') {
    return otherTracks;
  }
  return groupTracks;
};

const APPLICATION_STATUS_OPTIONS = [
  { value: '待申请', label: '待申请' },
  { value: '已申请', label: '已申请' },
  { value: '已网测', label: '已网测' },
  { value: '一面', label: '一面' },
  { value: '二面', label: '二面' },
  { value: '三面', label: '三面' },
];

const APPLIED_FLOW_STATUSES = ['已申请', '已网测', '一面', '二面', '三面'];

export default function Jobs() {
  const initialFilterState = useMemo(() => loadLastFilterState(), []);
  const navigate = useNavigate();
  const location = useLocation();
  const isAppliedFlowView = location.pathname === '/applied-flow';

  const [viewMode, setViewMode] = useState<'jobs' | 'companies'>('jobs'); // 视图模式：岗位列表 | 公司聚合
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState(initialFilterState.search);
  const [sectorGroup, setSectorGroup] = useState<string>(initialFilterState.sectorGroup || 'all'); // 'all' | 'internet' | 'bank' | 'other'
  const [days, setDays] = useState<number | undefined>(initialFilterState.days);
  const [minScore, setMinScore] = useState<number | undefined>(initialFilterState.minScore);
  const [jobStage, setJobStage] = useState<string>(initialFilterState.jobStage || 'campus');
  const [excludeAppliedCompanies, setExcludeAppliedCompanies] = useState<boolean>(Boolean(initialFilterState.excludeAppliedCompanies));
  const [stats, setStats] = useState<StatsData>({ total_jobs: 0, today_new: 0, by_track: {}, by_stage: {} });
  const [trackOptions, setTrackOptions] = useState<TrackOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [savedFilters, setSavedFilters] = useState<SavedFilterPreset[]>(() => loadSavedFilters());
  const [selectedPresetId, setSelectedPresetId] = useState<string>();
  const [saveModalOpen, setSaveModalOpen] = useState(false);
  const [presetName, setPresetName] = useState('');

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        page, page_size: pageSize, sort_by: 'total_score', sort_order: 'desc',
      };
      if (search) params.search = search;
      if (sectorGroup !== 'all') {
        const filteredTracks = getTracksByGroup(sectorGroup, trackOptions);
        if (filteredTracks.length > 0) {
          params.tracks = filteredTracks.join(',');
        }
      }
      if (days) params.days = days;
      if (minScore) params.min_score = minScore;
      if (jobStage) params.job_stage = jobStage;
      if (excludeAppliedCompanies) params.exclude_applied_companies = true;
      if (isAppliedFlowView) params.application_statuses = APPLIED_FLOW_STATUSES.join(',');

      // 根据视图模式调用不同的 API
      const apiCall = viewMode === 'companies' ? getJobsByCompany : getJobs;
      const res = await apiCall(params);
      setJobs(res.data.items);
      setTotal(res.data.total);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, search, sectorGroup, days, minScore, jobStage, excludeAppliedCompanies, isAppliedFlowView, trackOptions, viewMode]);
  const handleCompanyClick = (company: string) => {
    const params = new URLSearchParams({
      company,
      scope: 'current',
    });
    if (search) params.set('search', search);
    if (sectorGroup !== 'all' && sectorGroup) {
      const filteredTracks = getTracksByGroup(sectorGroup, trackOptions);
      if (filteredTracks.length > 0) params.set('tracks', filteredTracks.join(','));
    }
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
    saveLastFilterState({ search, sectorGroup, days, minScore, jobStage, excludeAppliedCompanies });
  }, [search, sectorGroup, days, minScore, jobStage, excludeAppliedCompanies]);

  const applyPreset = (presetId: string) => {
    const preset = savedFilters.find((p) => p.id === presetId);
    if (!preset) return;
    setSelectedPresetId(preset.id);
    setSearch(preset.search);
    setSectorGroup(preset.sectorGroup || 'all');
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
        sectorGroup,
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
      tracks: sectorGroup !== 'all' ? getTracksByGroup(sectorGroup, trackOptions) : [],
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

  const columns: ColumnsType<JobItem> = useMemo(() => {
    const baseColumns: ColumnsType<JobItem> = [
      {
        title: '公司', dataIndex: 'company', width: viewMode === 'companies' ? 130 : 180, ellipsis: true,
        render: (v: string, r: JobItem) => (
          <div style={{ cursor: 'pointer' }} onClick={() => handleCompanyClick(v)}>
            <span style={{ fontWeight: 500, color: '#1890ff' }}>{v}</span>
            {r.department && r.department !== v && (
              <div style={{ fontSize: 11, color: '#888' }}>{r.department}</div>
            )}
          </div>
        ),
      },
    ];

    // 在公司聚合模式下，添加"代表岗位"列；否则添加常规列
    if (viewMode === 'companies') {
      baseColumns.push(
        { title: '代表岗位', dataIndex: 'job_title', width: 220, ellipsis: true },
        { title: '地点', dataIndex: 'location', width: 100, ellipsis: true },
        {
          title: '赛道', key: 'tracks', width: 200, sorter: compareByTier,
          render: (_: unknown, r: JobItem) => {
            const tierInfo = getCompanyTier(r.company);
            return tierInfo ? (
              <Tag color={TIER_COLORS[tierInfo.tier] || 'default'}>
                {tierInfo.category}-{tierInfo.tierName}
              </Tag>
            ) : <span style={{ color: '#999' }}>-</span>;
          },
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
      );
    } else {
      baseColumns.push(
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
          title: '赛道', key: 'tracks', width: 240, sorter: compareByTier,
          render: (_: unknown, r: JobItem) => {
            const tierInfo = getCompanyTier(r.company);
            return tierInfo ? (
              <Tag color={TIER_COLORS[tierInfo.tier] || 'default'}>
                {tierInfo.category}-{tierInfo.tierName}
              </Tag>
            ) : <span style={{ color: '#999' }}>-</span>;
          },
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
          title: '情报', dataIndex: 'id', width: 70,
          render: (_: unknown, r: JobItem) => (
            <Button
              type="link"
              size="small"
              icon={<InfoCircleOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/job-intel/${r.id}`);
              }}
            >
              查看情报
            </Button>
          ),
        },
        {
          title: '', dataIndex: 'detail_url', width: 50,
          render: (v: string) => v ? <a href={v} target="_blank" rel="noreferrer">链接</a> : null,
        },
      );
    }

    return baseColumns;
  }, [viewMode, trackOptions]);

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
        {isAppliedFlowView && (
          <Tag color="blue">仅显示：已申请 / 已网测 / 一面 / 二面 / 三面</Tag>
        )}
        <Segmented
          value={viewMode}
          options={[
            { label: '岗位列表', value: 'jobs' },
            { label: '公司聚合', value: 'companies' },
          ]}
          onChange={(v) => { setViewMode(v as 'jobs' | 'companies'); setPage(1); }}
        />
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
        <Segmented
          value={sectorGroup}
          options={[
            { label: '全量', value: 'all' },
            { label: '互联网', value: 'internet' },
            { label: '银行', value: 'bank' },
            { label: '其他', value: 'other' },
          ]}
          onChange={(v) => { setSectorGroup(String(v)); setPage(1); }}
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
        <Button
          type={excludeAppliedCompanies ? 'primary' : 'default'}
          onClick={() => { setExcludeAppliedCompanies((v) => !v); setPage(1); }}
        >
          {excludeAppliedCompanies ? '已去掉已申请公司（点击关闭）' : '去掉已申请公司'}
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
    </div>
  );
}
