import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Row, Col, Button, Tag, Space, Spin, message, Alert, Checkbox } from 'antd';
import { SearchOutlined, ReloadOutlined, InfoCircleOutlined } from '@ant-design/icons';
import {
  searchJobIntel,
  refreshJobIntel,
  getJobIntelSummary,
  getJobIntelRecords,
  getJobIntelTasks,
  getJob,
} from '../api';

interface Snapshot {
  id: number;
  snapshot_type: string;
  summary_text: string;
  evidence_count: number;
  source_platforms_json: string;
  confidence_score: number;
}

interface IntelRecord {
  id: number;
  platform: string;
  content_type: string;
  title: string;
  author_name: string;
  publish_time: string | null;
  url: string;
  summary: string;
  relevance_score: number;
}

interface Task {
  id: number;
  status: string;
  search_level: string;
  platform_scope_json: string;
  query_bundle_json: string;
  started_at: string | null;
  finished_at: string | null;
  result_count: number;
  error_message: string;
}

const PLATFORM_COLORS: Record<string, string> = {
  xiaohongshu: 'red',
  maimai: 'orange',
  nowcoder: 'blue',
  boss: 'cyan',
  zhihu: 'purple',
};

export default function JobIntel() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<any>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [records, setRecords] = useState<IntelRecord[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(['xiaohongshu', 'maimai', 'nowcoder', 'boss', 'zhihu']);
  const [forceRefresh] = useState(false);

  const reloadIntelData = async (targetJobId: number) => {
    const [summaryRes, recordsRes, tasksRes] = await Promise.all([
      getJobIntelSummary(targetJobId),
      getJobIntelRecords(targetJobId, {}),
      getJobIntelTasks(targetJobId),
    ]);
    setSnapshots(summaryRes.data.snapshots || []);
    setRecords(recordsRes.data.items || []);
    setTasks(tasksRes.data.tasks || []);
  };

  useEffect(() => {
    if (!jobId) return;
    getJob(parseInt(jobId))
      .then((res) => setJob(res.data))
      .catch((e) => {
        message.error('获取岗位信息失败');
        console.error(e);
      });
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    reloadIntelData(parseInt(jobId)).catch((e) => console.error('获取 Job Intel 数据失败', e));
  }, [jobId]);

  const handleSearch = async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      await searchJobIntel(parseInt(jobId), {
        trigger_mode: 'manual',
        platforms: selectedPlatforms,
        force: forceRefresh,
      });
      await reloadIntelData(parseInt(jobId));
      message.success('情报搜索任务已执行并已刷新页面');
    } catch (e: any) {
      message.error('创建搜索任务失败');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      await refreshJobIntel(parseInt(jobId), { force: forceRefresh });
      await reloadIntelData(parseInt(jobId));
      message.success('情报刷新已完成并已刷新页面');
    } catch (e: any) {
      message.error('刷新情报失败');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const latestTask = tasks[0];
  const isRunning = latestTask?.status === 'running';

  if (!job) return <Spin tip="加载中..." />;

  return (
    <div style={{ padding: '20px' }}>
      <Card title="岗位信息" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}><div><strong>公司:</strong> {job.company}</div></Col>
          <Col span={6}><div><strong>岗位:</strong> {job.job_title}</div></Col>
          <Col span={6}><div><strong>地点:</strong> {job.location}</div></Col>
          <Col span={6}><div><strong>发布:</strong> {job.publish_date?.slice(0, 10) || '-'}</div></Col>
        </Row>
      </Card>

      <Card title="搜索控制" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <strong>选择平台:</strong>
            <Space style={{ marginTop: 8 }} wrap>
              {['xiaohongshu', 'maimai', 'nowcoder', 'boss', 'zhihu'].map((platform) => (
                <Checkbox
                  key={platform}
                  checked={selectedPlatforms.includes(platform)}
                  onChange={(e) => {
                    if (e.target.checked) setSelectedPlatforms((prev) => [...prev, platform]);
                    else setSelectedPlatforms((prev) => prev.filter((p) => p !== platform));
                  }}
                >
                  {platform}
                </Checkbox>
              ))}
            </Space>
          </div>
          <div style={{ marginTop: 12, display: 'flex', gap: 8 }}>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch} loading={loading} disabled={isRunning}>搜索相关情报</Button>
            <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading} disabled={isRunning}>刷新情报</Button>
          </div>
        </Space>
      </Card>

      <Card title="任务状态" style={{ marginBottom: 16 }}>
        {latestTask ? (
          <div>
            <div style={{ marginBottom: 8 }}><strong>最新任务:</strong> {latestTask.id}</div>
            <div style={{ marginBottom: 8 }}><strong>状态:</strong> <Tag color={isRunning ? 'processing' : 'success'}>{latestTask.status}</Tag></div>
            <div style={{ marginBottom: 8 }}><strong>搜索级别:</strong> {latestTask.search_level}</div>
            <div style={{ marginBottom: 8 }}><strong>结果数:</strong> {latestTask.result_count}</div>
            {latestTask.error_message && <Alert message={`错误: ${latestTask.error_message}`} type="error" style={{ marginTop: 8 }} />}
          </div>
        ) : (
          <div style={{ color: '#999', textAlign: 'center', padding: 20 }}>暂无任务</div>
        )}
      </Card>

      {snapshots.length > 0 && (
        <Card title="情报摘要" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            {snapshots.map((snap) => (
              <Col span={12} key={snap.id} style={{ marginBottom: 16 }}>
                <Card type="inner" title={<Space>{snap.snapshot_type}<InfoCircleOutlined style={{ marginLeft: 4 }} /></Space>} size="small">
                  <div>{snap.summary_text}</div>
                  <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>证据数: {snap.evidence_count} | 置信度: {(snap.confidence_score * 100).toFixed(0)}%</div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      {records.length > 0 && (
        <Card title="情报记录" style={{ marginBottom: 16 }}>
          <div>
            {records.map((record) => (
              <div key={record.id} style={{ border: '1px solid #f0f0f0', borderRadius: 4, padding: 12, marginBottom: 12 }}>
                <Row gutter={12}>
                  <Col span={4}><Tag color={PLATFORM_COLORS[record.platform] || 'default'}>{record.platform}</Tag></Col>
                  <Col span={16}>
                    <div style={{ fontWeight: 600 }}>{record.title}</div>
                    <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>{record.author_name} · {record.publish_time?.slice(0, 10) || '未知'}</div>
                    <div style={{ fontSize: 13, marginTop: 8, lineHeight: 1.6 }}>{record.summary}</div>
                    <a href={record.url} target="_blank" rel="noreferrer">原文链接</a>
                  </Col>
                  <Col span={4}><div style={{ fontSize: 12, color: '#888' }}>相关度: {(record.relevance_score * 100).toFixed(1)}%</div></Col>
                </Row>
              </div>
            ))}
          </div>
        </Card>
      )}

      {snapshots.length === 0 && records.length === 0 && (
        <Card>
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
            <InfoCircleOutlined style={{ fontSize: 32, marginBottom: 16 }} />
            <div>暂无情报数据</div>
            <div style={{ fontSize: 12, marginTop: 8 }}>点击“搜索相关情报”按钮开始搜索</div>
          </div>
        </Card>
      )}
    </div>
  );
}
