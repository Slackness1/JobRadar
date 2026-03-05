import { useEffect, useState } from 'react';
import { Card, Button, message, Space, Typography, Alert } from 'antd';
import { SaveOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { getScoringConfig, updateScoringConfig, rescore } from '../api';

const { Text } = Typography;

export default function Scoring() {
  const [configJson, setConfigJson] = useState('');
  const [saving, setSaving] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [jsonError, setJsonError] = useState('');

  const load = async () => {
    try {
      const res = await getScoringConfig();
      setConfigJson(JSON.stringify(JSON.parse(res.data.config_json), null, 2));
    } catch {
      message.error('加载配置失败');
    }
  };

  useEffect(() => { load(); }, []);

  const handleChange = (value: string) => {
    setConfigJson(value);
    try {
      JSON.parse(value);
      setJsonError('');
    } catch (e) {
      setJsonError(String(e));
    }
  };

  const handleSave = async () => {
    if (jsonError) { message.error('JSON 格式错误，请修正后再保存'); return; }
    setSaving(true);
    try {
      await updateScoringConfig({ config_json: configJson });
      message.success('配置已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleRescore = async () => {
    setRescoring(true);
    try {
      const res = await rescore();
      message.success(res.data.message);
    } catch {
      message.error('评分失败');
    } finally {
      setRescoring(false);
    }
  };

  return (
    <div>
      <Card
        title="评分权重配置"
        extra={
          <Space>
            <Button icon={<SaveOutlined />} loading={saving} onClick={handleSave} disabled={!!jsonError}>
              保存配置
            </Button>
            <Button type="primary" icon={<ThunderboltOutlined />} loading={rescoring} onClick={handleRescore}>
              重新评分
            </Button>
          </Space>
        }
      >
        <Alert
          message="配置说明"
          description="此处编辑评分权重、技能同义词、公司分级等配置。修改后需点击「保存配置」再「重新评分」生效。"
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
        />

        {jsonError && (
          <Alert message="JSON 格式错误" description={jsonError} type="error" style={{ marginBottom: 12 }} />
        )}

        <textarea
          value={configJson}
          onChange={e => handleChange(e.target.value)}
          style={{
            width: '100%',
            minHeight: 600,
            fontFamily: 'Consolas, "Courier New", monospace',
            fontSize: 13,
            lineHeight: 1.5,
            padding: 12,
            border: jsonError ? '1px solid #ff4d4f' : '1px solid #d9d9d9',
            borderRadius: 6,
            resize: 'vertical',
            outline: 'none',
          }}
          spellCheck={false}
        />

        <div style={{ marginTop: 8 }}>
          <Text type="secondary">包含字段：scoring（评分权重）、thresholds（阈值）、skill_synonyms（技能同义词）、hard_filters（硬性过滤）</Text>
        </div>
      </Card>
    </div>
  );
}
