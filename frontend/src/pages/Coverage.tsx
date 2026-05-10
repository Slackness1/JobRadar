import { useEffect, useMemo, useState } from 'react';
import {
  Card, Progress, Tag, Space, Typography, Empty, Tooltip, Spin,
  Row, Col, Statistic, Divider,
} from 'antd';
import {
  CheckCircleFilled, MinusCircleFilled, WarningFilled, ClockCircleOutlined,
} from '@ant-design/icons';
import { fetchCoverage } from '../api';

const { Title, Text, Paragraph } = Typography;

interface CompanyEntry {
  name: string;
  status: 'active' | 'deferred' | 'missing' | 'seasonal';
  fetched_7d: number;
  deferred_reason?: string | null;
}

interface ExtraEntry {
  name: string;
  fetched_7d: number;
}

interface TrackEnumerate {
  id: string;
  name: string;
  mode: 'enumerate';
  sources: string[];
  t1_total: number;
  active_count: number;
  deferred_count: number;
  missing_count: number;
  rate: number;
  companies: CompanyEntry[];
  extras: ExtraEntry[];
}

interface TrackAbsolute {
  id: string;
  name: string;
  mode: 'absolute';
  sources: string[];
  active_company_count: number;
  active_total_fetched: number;
  note: string;
  active_companies: ExtraEntry[];
}

type Track = TrackEnumerate | TrackAbsolute;

interface CoverageResp {
  tracks: Track[];
  overall: {
    grand_t1: number;
    grand_active: number;
    rate: number;
    generated_at: string;
  };
}

function rateColor(rate: number): string {
  if (rate >= 0.7) return '#52c41a';   // green
  if (rate >= 0.5) return '#faad14';   // amber
  return '#f5222d';                    // red
}

function statusIcon(status: CompanyEntry['status']) {
  if (status === 'active')
    return <CheckCircleFilled style={{ color: '#52c41a' }} />;
  if (status === 'seasonal')
    return <ClockCircleOutlined style={{ color: '#faad14' }} />;
  if (status === 'deferred')
    return <MinusCircleFilled style={{ color: '#bfbfbf' }} />;
  return <WarningFilled style={{ color: '#f5222d' }} />;
}

function statusLabel(status: CompanyEntry['status']) {
  if (status === 'active') return '已覆盖';
  if (status === 'seasonal') return '季节空';
  if (status === 'deferred') return '不爬';
  return '缺失';
}

function CompanyRow({ c }: { c: CompanyEntry }) {
  const reason = c.deferred_reason || '';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '6px 0',
        borderBottom: '1px solid #fafafa',
        opacity: c.status === 'deferred' ? 0.65 : 1,
      }}
    >
      <span style={{ width: 16 }}>{statusIcon(c.status)}</span>
      <span style={{ fontWeight: c.status === 'active' ? 600 : 400, minWidth: 90 }}>
        {c.name}
      </span>
      {c.status === 'active' && (
        <Tag color="green" style={{ marginLeft: 'auto' }}>
          {c.fetched_7d.toLocaleString()} 岗位/7d
        </Tag>
      )}
      {c.status !== 'active' && (
        <Text type="secondary" style={{ marginLeft: 'auto', fontSize: 12 }}>
          {statusLabel(c.status)}
        </Text>
      )}
      {reason && (
        <Tooltip title={reason}>
          <Text type="secondary" style={{
            fontSize: 12, marginLeft: 8, maxWidth: 320,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            原因: {reason}
          </Text>
        </Tooltip>
      )}
    </div>
  );
}

function EnumerateCard({ t }: { t: TrackEnumerate }) {
  const ratePct = Math.round(t.rate * 100);
  // Sort: active first (by fetched desc), then deferred, then missing
  const sortedCompanies = useMemo(() => {
    const order: Record<CompanyEntry['status'], number> = {
      active: 0, missing: 1, seasonal: 2, deferred: 3,
    };
    return [...t.companies].sort((a, b) => {
      if (a.status !== b.status) return order[a.status] - order[b.status];
      return b.fetched_7d - a.fetched_7d;
    });
  }, [t.companies]);

  return (
    <Card
      title={
        <Space size={12}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>{t.name}</span>
          <Tag color={rateColor(t.rate)} style={{ fontSize: 14, padding: '2px 10px' }}>
            {t.active_count}/{t.t1_total} = {ratePct}%
          </Tag>
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
      extra={
        <Space size={6}>
          {t.deferred_count > 0 && (
            <Tag color="default">不爬 {t.deferred_count}</Tag>
          )}
          {t.missing_count > 0 && (
            <Tag color="red">缺失 {t.missing_count}</Tag>
          )}
        </Space>
      }
    >
      <Progress
        percent={ratePct}
        strokeColor={rateColor(t.rate)}
        showInfo={false}
        style={{ marginBottom: 12 }}
      />
      <div>
        {sortedCompanies.map((c) => (
          <CompanyRow key={c.name} c={c} />
        ))}
      </div>
      {t.extras.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
            非 T1 但已 active 的额外公司（top {t.extras.length}）：
          </Paragraph>
          <Space size={[4, 4]} wrap>
            {t.extras.map((e) => (
              <Tag key={e.name} color="blue">
                {e.name} · {e.fetched_7d}
              </Tag>
            ))}
          </Space>
        </>
      )}
    </Card>
  );
}

function AbsoluteCard({ t }: { t: TrackAbsolute }) {
  return (
    <Card
      title={
        <Space size={12}>
          <span style={{ fontSize: 16, fontWeight: 600 }}>{t.name}</span>
          <Tag color="green" style={{ fontSize: 14, padding: '2px 10px' }}>
            {t.active_company_count} 家 active
          </Tag>
        </Space>
      }
      size="small"
      style={{ marginBottom: 16 }}
    >
      {t.note && (
        <Paragraph type="secondary" style={{ fontSize: 12, whiteSpace: 'pre-wrap' }}>
          {t.note}
        </Paragraph>
      )}
      <Statistic
        title="最近 7 天 fetched 累计"
        value={t.active_total_fetched}
        valueStyle={{ fontSize: 24 }}
      />
      <Divider style={{ margin: '12px 0' }} />
      <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
        Top {Math.min(t.active_companies.length, 50)} 家（按 7d fetched 降序）：
      </Paragraph>
      <Space size={[4, 4]} wrap>
        {t.active_companies.map((c) => (
          <Tag key={c.name} color="blue">
            {c.name} · {c.fetched_7d}
          </Tag>
        ))}
      </Space>
    </Card>
  );
}

export default function Coverage() {
  const [data, setData] = useState<CoverageResp | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetchCoverage();
        if (!cancelled) setData(res.data as CoverageResp);
      } catch (e) {
        if (!cancelled) setError((e as Error).message || '加载失败');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    const tid = window.setInterval(load, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(tid);
    };
  }, []);

  if (loading && !data) {
    return <Spin size="large" style={{ display: 'block', margin: '60px auto' }} />;
  }
  if (error) {
    return <Empty description={`加载失败: ${error}`} />;
  }
  if (!data) {
    return <Empty />;
  }

  const overallPct = Math.round(data.overall.rate * 100);
  const enumerated = data.tracks.filter(
    (t): t is TrackEnumerate => t.mode === 'enumerate'
  );
  const absolutes = data.tracks.filter(
    (t): t is TrackAbsolute => t.mode === 'absolute'
  );

  return (
    <div>
      <div style={{
        background: 'linear-gradient(135deg, #fff7e6 0%, #fff 100%)',
        padding: '20px 24px',
        borderRadius: 8,
        marginBottom: 16,
        border: '1px solid #ffe7ba',
      }}>
        <Title level={3} style={{ margin: 0 }}>
          顶级平台覆盖看板
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 12 }}>
          按 8 个赛道统计 T1 公司覆盖率（最近 7 天 fetched ≥ 1 即算 active）。
          数据每 60s 自动刷新。
        </Paragraph>
        <Row gutter={24}>
          <Col span={6}>
            <Statistic
              title="综合覆盖率"
              value={overallPct}
              suffix="%"
              valueStyle={{
                color: rateColor(data.overall.rate),
                fontSize: 36,
                fontWeight: 700,
              }}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="T1 active / total"
              value={`${data.overall.grand_active} / ${data.overall.grand_t1}`}
            />
          </Col>
          <Col span={6}>
            <Statistic
              title="赛道覆盖（含国央企）"
              value={data.tracks.length}
              suffix="个"
            />
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              生成时间<br />
              {new Date(data.overall.generated_at).toLocaleString('zh-CN')}
            </Text>
          </Col>
        </Row>
      </div>

      <Title level={5} style={{ marginBottom: 8 }}>赛道 KPI</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 24 }}>
        {enumerated.map((t) => {
          const pct = Math.round(t.rate * 100);
          return (
            <Col key={t.id} xs={12} sm={8} md={6} lg={6} xl={4}>
              <Card
                size="small"
                hoverable
                style={{
                  textAlign: 'center',
                  borderColor: rateColor(t.rate),
                  borderWidth: 2,
                }}
                onClick={() => {
                  document.getElementById(`track-${t.id}`)?.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start',
                  });
                }}
              >
                <div style={{
                  fontSize: 24, fontWeight: 700,
                  color: rateColor(t.rate),
                }}>
                  {pct}%
                </div>
                <div style={{ fontSize: 13, marginTop: 4 }}>{t.name}</div>
                <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                  {t.active_count}/{t.t1_total}
                </div>
              </Card>
            </Col>
          );
        })}
        {absolutes.map((t) => (
          <Col key={t.id} xs={12} sm={8} md={6} lg={6} xl={4}>
            <Card
              size="small"
              hoverable
              style={{ textAlign: 'center', borderColor: '#1890ff', borderWidth: 2 }}
              onClick={() => {
                document.getElementById(`track-${t.id}`)?.scrollIntoView({
                  behavior: 'smooth',
                  block: 'start',
                });
              }}
            >
              <div style={{ fontSize: 24, fontWeight: 700, color: '#1890ff' }}>
                {t.active_company_count}
              </div>
              <div style={{ fontSize: 13, marginTop: 4 }}>{t.name}</div>
              <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>家 active</div>
            </Card>
          </Col>
        ))}
      </Row>

      <Title level={5} style={{ marginBottom: 8 }}>赛道详细</Title>
      {enumerated.map((t) => (
        <div key={t.id} id={`track-${t.id}`}>
          <EnumerateCard t={t} />
        </div>
      ))}
      {absolutes.map((t) => (
        <div key={t.id} id={`track-${t.id}`}>
          <AbsoluteCard t={t} />
        </div>
      ))}
    </div>
  );
}
