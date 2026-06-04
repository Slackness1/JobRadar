import type { ReactNode } from 'react';

import { I } from '@/components/hifi/hifi-primitives';

export interface GuideStep {
  no: number;
  icon: ReactNode;
  title: string;
  what: string;   // 做什么
  value: string;  // 对学生的价值
  detail: string; // hover / 点击展开的补充说明
}

export const GUIDE_TITLE = 'JobRadar 怎么用 · 四步看懂';
export const GUIDE_SUBTITLE = '第一次用?跟着这四步走一遍就懂了。';
export const GUIDE_CTA_LABEL = '立即开始 →';
export const GUIDE_DISMISS_LABEL = '不再提示';

export const GUIDE_STEPS: GuideStep[] = [
  {
    no: 1,
    icon: I.upload(20),
    title: '上传简历',
    what: '传一份简历(PDF / Word),AI 自动读出教育、实习、项目、技能。',
    value: '不用填表,传完就开始。',
    detail: '支持 PDF / Word;解析不全也能手动补,AI 不会编造你没写过的经历。',
  },
  {
    no: 2,
    icon: I.radar(20),
    title: '选赛道 + 细分方向',
    what: '挑想去的金融赛道,再勾二级细分方向(如"公募权益研究员"),AI 帮你预勾最像的。',
    value: '选得越准,后面推荐和打分越贴你。',
    detail: '细分方向会影响岗位推荐排序和简历打分口径;勾错了随时回来改。',
  },
  {
    no: 3,
    icon: I.sparkle(20),
    title: '进工作台(核心)',
    what: '左:梯队骨架(目标公司按稳/匹配/冲刺分档 + 情报)· 中:AI 简历助手(按目标岗诊断 + 改写,不编数字)· 右:简历预览。',
    value: '一屏看清"我能去哪 + 简历差在哪"。',
    detail: '梯队骨架给你目标公司的档次与在招;AI 助手只做诚实诊断,绝不替你编造数字刷分。',
  },
  {
    no: 4,
    icon: I.send(20),
    title: '模拟面试 + 反馈',
    what: '针对某个岗位做模拟面试,AI 逐轮追问 + 给反馈。',
    value: '面试前先练一遍,拿到具体可改点。',
    detail: '可语音可文字;结束后出一份逐维度打分 + 改进建议的面试报告。',
  },
];
