import { useEffect, useState } from 'react';
import {
  Collapse, Tag, Input, InputNumber, Button, Space, message, Popconfirm,
  Card, Slider, Row, Col, Typography, Divider,
} from 'antd';
import { PlusOutlined, DeleteOutlined, ThunderboltOutlined } from '@ant-design/icons';
import {
  getTracks, updateTrack, deleteTrack, createTrack,
  addGroup, deleteGroup, batchAddKeywords, deleteKeyword, rescore, importTracksJson,
} from '../api';

const { Text } = Typography;

interface Keyword { id: number; word: string }
interface Group { id: number; group_name: string; sort_order: number; keywords: Keyword[] }
interface Track {
  id: number; key: string; name: string;
  weight: number; min_score: number; sort_order: number;
  groups: Group[];
}

export default function Tracks() {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [newTrackKey, setNewTrackKey] = useState('');
  const [newTrackName, setNewTrackName] = useState('');
  const [newGroupName, setNewGroupName] = useState<Record<number, string>>({});
  const [newKeyword, setNewKeyword] = useState<Record<number, string>>({});
  const [rescoring, setRescoring] = useState(false);
  const [trackImportJson, setTrackImportJson] = useState('');
  const [importingJson, setImportingJson] = useState(false);

  const load = async () => {
    try {
      const res = await getTracks();
      setTracks(res.data);
    } catch {
      message.error('加载赛道配置失败');
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpdateTrack = async (t: Track, field: string, value: unknown) => {
    await updateTrack(t.id, { [field]: value });
    message.success('已更新');
    load();
  };

  const handleDeleteTrack = async (id: number) => {
    await deleteTrack(id);
    message.success('赛道已删除');
    load();
  };

  const handleCreateTrack = async () => {
    if (!newTrackKey || !newTrackName) { message.warning('请填写 key 和名称'); return; }
    try {
      await createTrack({ key: newTrackKey, name: newTrackName });
      setNewTrackKey('');
      setNewTrackName('');
      message.success('赛道已创建');
      load();
    } catch {
      message.error('创建失败（key 可能重复）');
    }
  };

  const handleAddGroup = async (trackId: number) => {
    const name = newGroupName[trackId];
    if (!name) return;
    await addGroup(trackId, { group_name: name });
    setNewGroupName({ ...newGroupName, [trackId]: '' });
    load();
  };

  const handleDeleteGroup = async (trackId: number, groupId: number) => {
    await deleteGroup(trackId, groupId);
    load();
  };

  const handleAddKeyword = async (groupId: number) => {
    const word = newKeyword[groupId];
    if (!word) return;
    // Support comma-separated batch input
    const words = word.split(/[,，]/).map(w => w.trim()).filter(Boolean);
    await batchAddKeywords({ group_id: groupId, words });
    setNewKeyword({ ...newKeyword, [groupId]: '' });
    load();
  };

  const handleDeleteKeyword = async (kwId: number) => {
    await deleteKeyword(kwId);
    load();
  };

  const handleRescore = async () => {
    setRescoring(true);
    try {
      const res = await rescore();
      message.success(res.data.message);
    } finally {
      setRescoring(false);
    }
  };

  const handleImportTracksJson = async () => {
    const raw = trackImportJson.trim();
    if (!raw) {
      message.warning('请先粘贴 JSON 配置');
      return;
    }

    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      message.error('JSON 格式错误，请检查后重试');
      return;
    }

    const confirmed = window.confirm('将全量覆盖现有赛道/关键词配置，是否继续？');
    if (!confirmed) {
      return;
    }

    setImportingJson(true);
    try {
      const res = await importTracksJson(payload);
      message.success(
        `导入完成：${res.data.track_count} 个赛道，${res.data.group_count} 个分组，${res.data.keyword_count} 个关键词`,
      );
      setTrackImportJson('');
      load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      message.error(detail || '导入失败');
    } finally {
      setImportingJson(false);
    }
  };

  const collapseItems = tracks.map(track => ({
    key: track.id,
    label: (
      <Space>
        <Text strong>{track.name}</Text>
        <Tag color="blue">{track.key}</Tag>
        <Text type="secondary">权重 {track.weight} / 阈值 {track.min_score}</Text>
      </Space>
    ),
    extra: (
      <Popconfirm title="确定删除此赛道？" onConfirm={() => handleDeleteTrack(track.id)}>
        <Button size="small" danger icon={<DeleteOutlined />} onClick={e => e.stopPropagation()} />
      </Popconfirm>
    ),
    children: (
      <div>
        <Row gutter={24} style={{ marginBottom: 16 }}>
          <Col span={8}>
            <Text type="secondary">名称</Text>
            <Input
              defaultValue={track.name}
              onBlur={e => { if (e.target.value !== track.name) handleUpdateTrack(track, 'name', e.target.value); }}
            />
          </Col>
          <Col span={8}>
            <Text type="secondary">权重 ({track.weight})</Text>
            <Slider
              min={0} max={2} step={0.05}
              defaultValue={track.weight}
              onChangeComplete={(v: number) => handleUpdateTrack(track, 'weight', v)}
            />
          </Col>
          <Col span={8}>
            <Text type="secondary">最低分</Text>
            <InputNumber
              defaultValue={track.min_score}
              style={{ width: '100%' }}
              onBlur={e => {
                const v = parseInt(e.target.value);
                if (!isNaN(v) && v !== track.min_score) handleUpdateTrack(track, 'min_score', v);
              }}
            />
          </Col>
        </Row>

        <Divider style={{ margin: '8px 0' }} />

        {track.groups.map(group => (
          <Card
            key={group.id}
            size="small"
            title={<Text strong>{group.group_name}</Text>}
            style={{ marginBottom: 8 }}
            extra={
              <Popconfirm title="删除此关键词组？" onConfirm={() => handleDeleteGroup(track.id, group.id)}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            }
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
              {group.keywords.map(kw => (
                <Tag
                  key={kw.id}
                  closable
                  onClose={() => handleDeleteKeyword(kw.id)}
                >
                  {kw.word}
                </Tag>
              ))}
            </div>
            <Input
              size="small"
              placeholder="输入关键词，逗号分隔可批量添加"
              value={newKeyword[group.id] || ''}
              onChange={e => setNewKeyword({ ...newKeyword, [group.id]: e.target.value })}
              onPressEnter={() => handleAddKeyword(group.id)}
              style={{ width: 300 }}
              suffix={<Text type="secondary">Enter</Text>}
            />
          </Card>
        ))}

        <Space style={{ marginTop: 8 }}>
          <Input
            placeholder="新关键词组名称"
            value={newGroupName[track.id] || ''}
            onChange={e => setNewGroupName({ ...newGroupName, [track.id]: e.target.value })}
            onPressEnter={() => handleAddGroup(track.id)}
            style={{ width: 180 }}
          />
          <Button size="small" icon={<PlusOutlined />} onClick={() => handleAddGroup(track.id)}>
            添加分组
          </Button>
        </Space>
      </div>
    ),
  }));

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input placeholder="赛道 key（英文）" value={newTrackKey} onChange={e => setNewTrackKey(e.target.value)} style={{ width: 160 }} />
          <Input placeholder="赛道名称" value={newTrackName} onChange={e => setNewTrackName(e.target.value)} style={{ width: 180 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateTrack}>新建赛道</Button>
          <Divider type="vertical" />
          <Button icon={<ThunderboltOutlined />} loading={rescoring} onClick={handleRescore}>
            重新评分
          </Button>
        </Space>
      </Card>

      <Card size="small" style={{ marginBottom: 16 }} title="赛道配置粘贴导入（JSON，全量覆盖）">
        <Input.TextArea
          value={trackImportJson}
          onChange={(e) => setTrackImportJson(e.target.value)}
          rows={8}
          placeholder='示例：{"tracks":[{"key":"data_analysis","name":"数据分析","weight":1,"min_score":10,"groups":[{"group_name":"核心技能","keywords":["Python","SQL"]}]}]}'
          style={{ marginBottom: 8 }}
        />
        <Button type="primary" onClick={handleImportTracksJson} loading={importingJson}>
          一键导入并覆盖
        </Button>
      </Card>

      <Collapse items={collapseItems} defaultActiveKey={tracks.length > 0 ? [tracks[0].id] : []} />
    </div>
  );
}
