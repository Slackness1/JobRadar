import { Card } from 'antd';


interface Snapshot {
  id: number;
  snapshot_type: string;
  summary_text: string;
  evidence_count: number;
  source_platforms_json: string;
  confidence_score: number;
}


export default function IntelSummaryCard({ snapshots }: { snapshots: Snapshot[] }) {
  return (
    <Card title="情报摘要" style={{ marginBottom: 16 }}>
      {snapshots.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>
          暂无摘要数据
        </div>
      ) : (
        snapshots.map(snap => (
          <Card
            key={snap.id}
            type="inner"
            title={snap.snapshot_type}
            size="small"
            style={{ marginBottom: 12 }}
          >
            <div>{snap.summary_text}</div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
              证据数: {snap.evidence_count} | 置信度: {(snap.confidence_score * 100).toFixed(0)}%
            </div>
          </Card>
        ))
      )}
    </Card>
  );
}
