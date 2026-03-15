import { Tabs } from 'antd';


interface IntelPlatformTabsProps {
  selectedPlatforms: string[];
  onPlatformsChange: (platforms: string[]) => void;
  disabled?: boolean;
}

const PLATFORM_COLORS: Record<string, string> = {
  xiaohongshu: 'red',
  maimai: 'orange',
  nowcoder: 'blue',
  boss: 'cyan',
  zhihu: 'purple',
};

const PLATFORM_NAMES: Record<string, string> = {
  xiaohongshu: '小红书',
  maimai: '脉脉',
  nowcoder: '牛客',
  boss: 'BOSS',
  zhihu: '知乎',
};

export default function IntelPlatformTabs({
  selectedPlatforms: _selectedPlatforms,
  onPlatformsChange,
  disabled = false,
}: IntelPlatformTabsProps) {
  return (
    <Tabs
      defaultActiveKey="all"
      items={[
        {
          key: 'all',
          label: '全部',
        },
        {
          key: 'xiaohongshu',
          label: (
            <span style={{ color: PLATFORM_COLORS.xiaohongshu }}>
              {PLATFORM_NAMES.xiaohongshu}
            </span>
          ),
        },
        {
          key: 'maimai',
          label: (
            <span style={{ color: PLATFORM_COLORS.maimai }}>
              {PLATFORM_NAMES.maimai}
            </span>
          ),
        },
        {
          key: 'nowcoder',
          label: (
            <span style={{ color: PLATFORM_COLORS.nowcoder }}>
              {PLATFORM_NAMES.nowcoder}
            </span>
          ),
        },
        {
          key: 'boss',
          label: (
            <span style={{ color: PLATFORM_COLORS.boss }}>
              {PLATFORM_NAMES.boss}
            </span>
          ),
        },
        {
          key: 'zhihu',
          label: (
            <span style={{ color: PLATFORM_COLORS.zhihu }}>
              {PLATFORM_NAMES.zhihu}
            </span>
          ),
        },
      ]}
      onChange={disabled ? undefined : (key) => {
        if (key === 'all') {
          onPlatformsChange(['xiaohongshu', 'maimai', 'nowcoder', 'boss', 'zhihu']);
        } else {
          onPlatformsChange([key]);
        }
      }}
    />
  );
}
