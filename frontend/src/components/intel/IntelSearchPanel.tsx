import { Space, Button, Checkbox } from 'antd';
import type { CheckboxChangeEvent } from 'antd/es/checkbox';
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons';


interface IntelSearchPanelProps {
  selectedPlatforms: string[];
  onPlatformsChange: (platforms: string[]) => void;
  onSearch: () => void;
  onRefresh: () => void;
  loading?: boolean;
  disabled?: boolean;
}

const ALL_PLATFORMS = [
  'xiaohongshu',
  'maimai',
  'nowcoder',
  'boss',
  'zhihu',
];

const PLATFORM_NAMES: Record<string, string> = {
  xiaohongshu: '小红书',
  maimai: '脉脉',
  nowcoder: '牛客',
  boss: 'BOSS',
  zhihu: '知乎',
};

export default function IntelSearchPanel({
  selectedPlatforms,
  onPlatformsChange,
  onSearch,
  onRefresh,
  loading = false,
  disabled = false,
}: IntelSearchPanelProps) {
  const handleToggleAll = (e: CheckboxChangeEvent) => {
    if (e.target.checked) {
      onPlatformsChange(ALL_PLATFORMS);
    } else {
      onPlatformsChange([]);
    }
  };

  const handleTogglePlatform = (platform: string, checked: boolean) => {
    if (checked) {
      if (!selectedPlatforms.includes(platform)) {
        onPlatformsChange([...selectedPlatforms, platform]);
      }
    } else {
      onPlatformsChange(selectedPlatforms.filter(p => p !== platform));
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div style={{ marginBottom: 12 }}>
        <strong>选择搜索平台:</strong>
      </div>
      <div style={{ marginBottom: 16 }}>
        <Checkbox
          checked={selectedPlatforms.length === ALL_PLATFORMS.length}
          onChange={handleToggleAll}
          disabled={disabled}
        >
          全选
        </Checkbox>
        <div style={{ marginLeft: 24 }}>
          {ALL_PLATFORMS.map(platform => (
            <Checkbox
              key={platform}
              checked={selectedPlatforms.includes(platform)}
              onChange={(e) => handleTogglePlatform(platform, e.target.checked)}
              disabled={disabled}
            >
              {PLATFORM_NAMES[platform]}
            </Checkbox>
          ))}
        </div>
      </div>
      <div style={{ marginBottom: 12 }}>
        <strong>操作:</strong>
      </div>
      <div>
        <Button
          type="primary"
          icon={<SearchOutlined />}
          onClick={onSearch}
          loading={loading}
          disabled={disabled}
          style={{ marginRight: 8 }}
        >
          搜索相关情报
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={onRefresh}
          loading={loading}
          disabled={disabled}
        >
          刷新情报
        </Button>
      </div>
    </Space>
  );
}
