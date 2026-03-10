import { useEffect, useState, useRef } from 'react';
import { Button, Table, Tag, Card, message, Statistic, Row, Col, Alert, Space, Popconfirm } from 'antd';
import { PlayCircleOutlined, SyncOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  triggerCrawl,
  getCrawlStatus,
  getCrawlLogs,
  listCompanyRecrawlTasks,
  retryCompanyRecrawlTask,
  deleteCompanyRecrawlTask,
} from '../api';
import api from '../api';
import { formatBeijingDateTime } from '../utils/time';

interface CrawlLog {
  id: number;
  source: string;
  started_at: string | null;
  finished_at: string | null;
  status: string;
  new_count: number;
  total_count: number;
  error_message: string;
}

interface CompanyRecrawlTaskItem {
  id: number;
  company: string;
  department: string;
  career_url: string;
  status: string;
  attempt_count: number;
  fetched_count: number;
  new_count: number;
  last_error: string;
  updated_at: string | null;
}

export default function Crawl() {
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<CrawlLog[]>([]);
  const [recrawlTasks, setRecrawlTasks] = useState<CompanyRecrawlTaskItem[]>([]);
  const [recrawlBatchRunning, setRecrawlBatchRunning] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  const loadLogs = async () => {
    const res = await getCrawlLogs();
    setLogs(res.data);
  };

  const loadRecrawlTasks = async () => {
    const res = await listCompanyRecrawlTasks({ limit: 100 });
    setRecrawlTasks(res.data.items || []);
  };

  const checkStatus = async () => {
    const res = await getCrawlStatus();
    setIsRunning(res.data.is_running);
    if (!res.data.is_running && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = undefined;
      loadLogs();
      loadRecrawlTasks();
    }
  };

  useEffect(() => {
    loadLogs();
    loadRecrawlTasks();
    checkStatus();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleTrigger = async () => {
    try {
      const res = await triggerCrawl();
      if (res.data.log_id === 0) {
        message.warning('爬取正在进行中');
        return;
      }
      message.info('爬取已启动');
      setIsRunning(true);
      pollRef.current = setInterval(checkStatus, 3000);
      loadRecrawlTasks();
    } catch {
      message.error('启动爬取失败');
    }
  };

  const handleRetryTask = async (taskId: number) => {
    try {
      await retryCompanyRecrawlTask(taskId);
      message.success('任务已重试，将在下次爬取时执行');
      loadRecrawlTasks();
    } catch {
      message.error('重试失败');
    }
  };

  const handleDeleteTask = async (taskId: number) => {
    try {
      await deleteCompanyRecrawlTask(taskId);
      message.success('队列任务已删除');
      loadRecrawlTasks();
    } catch {
      message.error('删除失败');
    }
  };

  const handleRunPendingRecrawl = async () => {
    try {
      setRecrawlBatchRunning(true);
      const res = await api.post('/recrawl-queue/run-pending', null, { params: { batch_size: 50 } });
      const summary = res.data;
      message.success(
        `补爬完成：处理 ${summary.processed} 条，新增 ${summary.total_new} 条岗位，失败 ${summary.failed} 条`,
        6,
      );
      if (Array.isArray(summary.notes) && summary.notes.length > 0) {
        message.info(summary.notes.slice(0, 2).join('；'), 6);
      }
      await loadRecrawlTasks();
      await loadLogs();
    } catch {
      message.error('一键全量补爬失败');
    } finally {
      setRecrawlBatchRunning(false);
    }
  };

  const statusColor = (s: string) => {
    if (s === 'success') return 'green';
    if (s === 'running') return 'blue';
    return 'red';
  };

  const recrawlStatusColor = (s: string) => {
    if (s === 'completed') return 'green';
    if (s === 'running') return 'blue';
    if (s === 'pending') return 'gold';
    return 'red';
  };

  const columns: ColumnsType<CrawlLog> = [
    {
      title: '开始时间', dataIndex: 'started_at', width: 180,
      render: (v: string | null) => formatBeijingDateTime(v),
    },
    {
      title: '状态', dataIndex: 'status', width: 90,
      render: (v: string) => <Tag color={statusColor(v)}>{v === 'success' ? '成功' : v === 'running' ? '运行中' : '失败'}</Tag>,
    },
    { title: '新增', dataIndex: 'new_count', width: 80 },
    { title: '总数', dataIndex: 'total_count', width: 80 },
    {
      title: '耗时', key: 'duration', width: 100,
      render: (_: unknown, r: CrawlLog) => {
        if (!r.started_at || !r.finished_at) return '-';
        const sec = Math.round((new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000);
        return sec < 60 ? `${sec}s` : `${Math.floor(sec / 60)}m${sec % 60}s`;
      },
    },
    {
      title: '错误信息', dataIndex: 'error_message', ellipsis: true,
      render: (v: string) => v ? <span style={{ color: '#ff4d4f' }}>{v}</span> : '-',
    },
  ];

  const recrawlColumns: ColumnsType<CompanyRecrawlTaskItem> = [
    {
      title: '公司',
      key: 'company',
      width: 220,
      render: (_: unknown, row: CompanyRecrawlTaskItem) => (
        <div>
          <div style={{ fontWeight: 500 }}>{row.company}</div>
          {row.department && row.department !== row.company ? (
            <div style={{ fontSize: 12, color: '#666' }}>{row.department}</div>
          ) : null}
        </div>
      ),
    },
    {
      title: '官网链接',
      dataIndex: 'career_url',
      width: 260,
      ellipsis: true,
      render: (value: string) => <a href={value} target="_blank" rel="noreferrer">{value}</a>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (value: string) => <Tag color={recrawlStatusColor(value)}>{value}</Tag>,
    },
    { title: '尝试次数', dataIndex: 'attempt_count', width: 90 },
    { title: '抓取条数', dataIndex: 'fetched_count', width: 90 },
    { title: '新增条数', dataIndex: 'new_count', width: 90 },
    {
      title: '错误信息',
      dataIndex: 'last_error',
      ellipsis: true,
      render: (value: string) => value ? <span style={{ color: '#ff4d4f' }}>{value}</span> : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 170,
      render: (_: unknown, row: CompanyRecrawlTaskItem) => (
        <Space>
          <Button size="small" disabled={row.status !== 'failed'} onClick={() => handleRetryTask(row.id)}>
            重试
          </Button>
          <Popconfirm title="确认删除该队列任务？" onConfirm={() => handleDeleteTask(row.id)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const pendingCount = recrawlTasks.filter((item) => item.status === 'pending').length;

  return (
    <div>
      <Alert
        message="爬取说明"
        description="点击「立即爬取」会执行双源抓取：1) Tata（自动登录后抓取）；2) 鱼泡直聘校招（无需登录，自动进入详情页抓职位信息）。可配置 TATA_EXPORT_CONFIG_ID / TATA_EXPORT_CONFIG_IDS，以及 TATA_EXPORT_SHEET_INDEXES（如 0,1,2,3）；可选 TATA_INTERNSHIP_SHEET_INDEXES（如 2,3）标记实习分支。爬取完成后自动评分。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Card style={{ marginBottom: 16 }}>
        <Row gutter={24} align="middle">
          <Col>
            <Button
              type="primary"
              size="large"
              icon={isRunning ? <SyncOutlined spin /> : <PlayCircleOutlined />}
              onClick={handleTrigger}
              disabled={isRunning}
            >
              {isRunning ? '爬取中...' : '立即爬取'}
            </Button>
          </Col>
          <Col>
            <Statistic
              title="当前状态"
              value={isRunning ? '运行中' : '空闲'}
              valueStyle={{ color: isRunning ? '#1890ff' : '#52c41a' }}
            />
          </Col>
          {logs.length > 0 && logs[0].status === 'success' && (
            <>
              <Col>
                <Statistic title="上次新增" value={logs[0].new_count} suffix="条" />
              </Col>
              <Col>
                <Statistic title="上次总计" value={logs[0].total_count} suffix="条" />
              </Col>
            </>
          )}
        </Row>
      </Card>

      <Card title="爬取历史">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={logs}
          size="small"
          pagination={{ pageSize: 20, showTotal: t => `共 ${t} 条` }}
        />
      </Card>

      <Card
        title="公司官网补爬队列"
        style={{ marginTop: 16 }}
        extra={(
          <Space>
            <Button onClick={loadRecrawlTasks}>刷新队列</Button>
            <Button
              type="primary"
              loading={recrawlBatchRunning}
              disabled={recrawlBatchRunning || pendingCount === 0}
              onClick={handleRunPendingRecrawl}
            >
              一键全量补爬待爬公司（{pendingCount}）
            </Button>
          </Space>
        )}
      >
        <Table
          rowKey="id"
          columns={recrawlColumns}
          dataSource={recrawlTasks}
          size="small"
          pagination={{ pageSize: 10, showTotal: t => `共 ${t} 条` }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </div>
  );
}
