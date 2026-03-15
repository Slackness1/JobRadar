import { List, Tag } from 'antd';


interface IntelRecord {
  id: number;
  platform: string;
  title: string;
  author_name: string;
  publish_time: string | null;
  url: string;
  summary: string;
  relevance_score: number;
}

interface IntelRecordListProps {
  records: IntelRecord[];
}

const PLATFORM_COLORS: Record<string, string> = {
  xiaohongshu: 'red',
  maimai: 'orange',
  nowcoder: 'blue',
  boss: 'cyan',
  zhihu: 'purple',
};

export default function IntelRecordList({ records }: IntelRecordListProps) {
  return (
    <List
      dataSource={records}
      renderItem={record => (
        <List.Item key={record.id}>
          <div style={{ border: '1px solid #f0f0f0', borderRadius: 4, padding: 12, marginBottom: 12 }}>
            <div style={{ marginBottom: 8 }}>
              <Tag color={PLATFORM_COLORS[record.platform] || 'default'}>
                {record.platform}
              </Tag>
              <span style={{ marginLeft: 8, fontWeight: 600 }}>
                {record.title}
              </span>
            </div>
            <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
              {record.author_name} · {record.publish_time?.slice(0, 10) || '未知'}
            </div>
            <div style={{ fontSize: 13, marginTop: 8, lineHeight: 1.6 }}>
              {record.summary}
            </div>
            <div style={{ marginTop: 8 }}>
              <a href={record.url} target="_blank" rel="noreferrer" style={{ fontSize: 12 }}>
                原文链接
              </a>
            </div>
            <div style={{ marginTop: 8, fontSize: 12, color: '#888' }}>
              相关度: {(record.relevance_score * 100).toFixed(1)}%
            </div>
          </div>
        </List.Item>
      )}
    />
  );
}
