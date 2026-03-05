import { useEffect, useState } from 'react';
import { Card, Input, Button, message, Descriptions, Badge, Space, Alert, Typography } from 'antd';
import { SaveOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { getScheduler, updateScheduler } from '../api';
import { formatBeijingDateTime } from '../utils/time';

const { Text } = Typography;

const CRON_PRESETS = [
  { label: '每天 06:00', value: '0 6 * * *' },
  { label: '每天 08:00', value: '0 8 * * *' },
  { label: '每天 12:00', value: '0 12 * * *' },
  { label: '每天 20:00', value: '0 20 * * *' },
  { label: '每12小时', value: '0 */12 * * *' },
  { label: '工作日 08:00', value: '0 8 * * 1-5' },
];

export default function Scheduler() {
  const [cron, setCron] = useState('');
  const [nextRun, setNextRun] = useState('');
  const [isActive, setIsActive] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const res = await getScheduler();
      setCron(res.data.cron_expression);
      setNextRun(res.data.next_run || '');
      setIsActive(res.data.is_active);
    } catch {
      message.error('加载调度配置失败');
    }
  };

  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateScheduler({ cron_expression: cron });
      message.success('调度时间已更新');
      load();
    } catch {
      message.error('更新失败，请检查 cron 表达式');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Card title={<><ClockCircleOutlined /> 定时爬取配置</>}>
        <Descriptions column={1} bordered size="small" style={{ marginBottom: 24 }}>
          <Descriptions.Item label="调度状态">
            <Badge status={isActive ? 'processing' : 'default'} text={isActive ? '运行中' : '未启动'} />
          </Descriptions.Item>
          <Descriptions.Item label="下次执行">
            {nextRun ? formatBeijingDateTime(nextRun) : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="当前 Cron">
            <Text code>{cron}</Text>
          </Descriptions.Item>
        </Descriptions>

        <div style={{ marginBottom: 16 }}>
          <Text strong>Cron 表达式：</Text>
          <Space style={{ marginTop: 8 }}>
            <Input
              value={cron}
              onChange={e => setCron(e.target.value)}
              style={{ width: 300 }}
              placeholder="分 时 日 月 星期"
            />
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
              保存
            </Button>
          </Space>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">快捷设置：</Text>
          <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {CRON_PRESETS.map(p => (
              <Button
                key={p.value}
                size="small"
                type={cron === p.value ? 'primary' : 'default'}
                onClick={() => setCron(p.value)}
              >
                {p.label}
              </Button>
            ))}
          </div>
        </div>

        <Alert
          message="Cron 格式说明"
          description={
            <div style={{ fontFamily: 'monospace', fontSize: 12 }}>
              <div>格式：分钟 小时 日 月 星期</div>
              <div>* = 每个 | */N = 每隔N | 1-5 = 范围 | 1,3,5 = 列表</div>
              <div>例：0 8 * * * = 每天08:00 | 0 8 * * 1-5 = 工作日08:00</div>
            </div>
          }
          type="info"
        />
      </Card>
    </div>
  );
}
