import { Card, Tag, Alert } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';


interface Task {
  id: number;
  status: string;
  search_level: string;
  started_at: string | null;
  finished_at: string | null;
  result_count: number;
  error_message: string;
}

interface IntelTaskStatusProps {
  task: Task | null;
}

const STATUS_COLORS: Record<string, string> = {
  queued: 'default',
  running: 'processing',
  done: 'success',
  failed: 'error',
  auth_required: 'warning',
};

export default function IntelTaskStatus({ task }: IntelTaskStatusProps) {
  if (!task) {
    return (
      <Card title="任务状态">
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          <InfoCircleOutlined style={{ fontSize: 32, marginBottom: 16 }} />
          <div>暂无任务</div>
        </div>
      </Card>
    );
  }

  const isRunning = task.status === 'running';

  return (
    <Card title="任务状态">
      <div style={{ marginBottom: 8 }}>
        <strong>任务 ID:</strong> {task.id}
      </div>
      <div style={{ marginBottom: 8 }}>
        <strong>状态:</strong>
        <Tag color={STATUS_COLORS[task.status] || 'default'}>
          {task.status}
        </Tag>
        {isRunning && <span style={{ marginLeft: 8, fontSize: 12, color: '#888' }}>运行中...</span>}
      </div>
      <div style={{ marginBottom: 8 }}>
        <strong>搜索级别:</strong> {task.search_level}
      </div>
      <div style={{ marginBottom: 8 }}>
        <strong>结果数:</strong> {task.result_count}
      </div>
      {task.started_at && (
        <div style={{ marginBottom: 8 }}>
          <strong>开始时间:</strong> {task.started_at.slice(0, 19)}
        </div>
      )}
      {task.finished_at && (
        <div style={{ marginBottom: 8 }}>
          <strong>完成时间:</strong> {task.finished_at.slice(0, 19)}
        </div>
      )}
      {task.error_message && (
        <Alert
          message={`错误: ${task.error_message}`}
          type="error"
          style={{ marginTop: 12 }}
        />
      )}
    </Card>
  );
}
