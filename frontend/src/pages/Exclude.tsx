import { useEffect, useState, useMemo } from 'react';
import { Table, Button, Input, Space, Tag, message, Popconfirm, Card, Select, Row, Col, Switch } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getExcludeRules,
  addExcludeRule,
  deleteExcludeRule,
  getSpringDisplayConfig,
  updateSpringDisplayConfig,
} from '../api';

interface Rule { id: number; category: string; keyword: string }

const CATEGORY_COLORS: Record<string, string> = {
  sales: 'red', support: 'orange', logistics: 'volcano',
  design: 'purple', ops: 'blue', game: 'cyan',
  hardware: 'geekblue', construction: 'lime',
};

export default function Exclude() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [newCat, setNewCat] = useState('');
  const [newKw, setNewKw] = useState('');
  const [filterCat, setFilterCat] = useState<string | undefined>();
  const [springEnabled, setSpringEnabled] = useState(true);
  const [springCutoffDate, setSpringCutoffDate] = useState('2026-02-01');
  const [updatingSpring, setUpdatingSpring] = useState(false);

  const load = async () => {
    try {
      const res = await getExcludeRules();
      setRules(res.data);

      const springRes = await getSpringDisplayConfig();
      setSpringEnabled(Boolean(springRes.data.enabled));
      setSpringCutoffDate(springRes.data.cutoff_date || '2026-02-01');
    } catch {
      message.error('加载排除规则失败');
    }
  };

  useEffect(() => { load(); }, []);

  const categories = useMemo(() => [...new Set(rules.map(r => r.category))].sort(), [rules]);

  const filteredRules = useMemo(() => {
    if (!filterCat) return rules;
    return rules.filter(r => r.category === filterCat);
  }, [rules, filterCat]);

  const handleAdd = async () => {
    if (!newCat || !newKw) { message.warning('请填写分类和关键词'); return; }
    // Support comma-separated
    const words = newKw.split(/[,，]/).map(w => w.trim()).filter(Boolean);
    for (const word of words) {
      await addExcludeRule({ category: newCat, keyword: word });
    }
    setNewKw('');
    message.success(`添加 ${words.length} 条规则`);
    load();
  };

  const handleDelete = async (id: number) => {
    await deleteExcludeRule(id);
    load();
  };

  const handleToggleSpring = async (checked: boolean) => {
    const previous = springEnabled;
    setSpringEnabled(checked);
    setUpdatingSpring(true);
    try {
      await updateSpringDisplayConfig({ enabled: checked, cutoff_date: springCutoffDate });
      message.success(checked ? '已开启：仅展示 2026 春招岗位' : '已关闭：展示全部岗位');
    } catch {
      setSpringEnabled(previous);
      message.error('更新春招展示开关失败');
    } finally {
      setUpdatingSpring(false);
    }
  };

  const columns: ColumnsType<Rule> = [
    {
      title: '分类', dataIndex: 'category', width: 120,
      render: (v: string) => <Tag color={CATEGORY_COLORS[v] || 'default'}>{v}</Tag>,
    },
    { title: '排除关键词', dataIndex: 'keyword' },
    {
      title: '操作', key: 'action', width: 80,
      render: (_: unknown, r: Rule) => (
        <Popconfirm title="确定删除？" onConfirm={() => handleDelete(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Switch checked={springEnabled} loading={updatingSpring} onChange={handleToggleSpring} />
          <span>仅展示 2026 春招岗位（全部来源）</span>
          <Tag color={springEnabled ? 'blue' : 'default'}>起始日期：{springCutoffDate}</Tag>
        </Space>
      </Card>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={8} align="middle">
          <Col>
            <Select
              placeholder="选择分类"
              value={newCat || undefined}
              onChange={setNewCat}
              style={{ width: 150 }}
              allowClear
              options={categories.map(c => ({ value: c, label: c }))}
            />
          </Col>
          <Col>
            <Input
              placeholder="或输入新分类"
              value={newCat}
              onChange={e => setNewCat(e.target.value)}
              style={{ width: 140 }}
            />
          </Col>
          <Col flex="auto">
            <Input
              placeholder="排除关键词，逗号分隔可批量添加"
              value={newKw}
              onChange={e => setNewKw(e.target.value)}
              onPressEnter={handleAdd}
            />
          </Col>
          <Col>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>添加</Button>
          </Col>
        </Row>
      </Card>

      <Space style={{ marginBottom: 12 }}>
        <span>筛选分类：</span>
        <Select
          placeholder="全部"
          value={filterCat}
          onChange={setFilterCat}
          style={{ width: 150 }}
          allowClear
          options={categories.map(c => ({ value: c, label: `${c} (${rules.filter(r => r.category === c).length})` }))}
        />
      </Space>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={filteredRules}
        size="small"
        pagination={{ pageSize: 50, showTotal: t => `共 ${t} 条` }}
      />
    </div>
  );
}
