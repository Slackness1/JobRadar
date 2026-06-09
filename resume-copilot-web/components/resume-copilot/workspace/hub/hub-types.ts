import type { WorkingQuery, RecommendFeedItem, RecommendTrace } from '../../types';
import type { DeepUnderstand } from './deep-think-meta';

export type HubModule = 'feed' | 'skeleton' | 'resume' | 'interview' | 'profile';

// 画布槽当前视图（profile 直接开，不跑技能）
export type HubSlot = 'none' | 'feed' | 'skeleton' | 'resume' | 'profile';

export interface ResultCardData {
  title: string;
  body: string;   // 允许内联 <b>，dangerouslySetInnerHTML 渲染
  cta: string;
}

export type HubMessage =
  | { id: string; kind: 'turn'; who: 'me' | 'ai'; html: string }
  | {
      id: string;
      kind: 'skillrun';
      module: HubModule;
      /** 真实赛道 / 记忆 —— 注入 DeepThinkCard 的「我的理解」 */
      understandOverride?: Partial<DeepUnderstand>;
      /** 节点序号 → 真实计数 output(done 态优先) */
      outputOverride?: Record<number, string>;
    }
  | { id: string; kind: 'result'; module: HubModule; data: ResultCardData }
  | { id: string; kind: 'trace'; trace: RecommendTrace }
  | { id: string; kind: 'memory'; text: string }
  | { id: string; kind: 'intel'; text: string };

export type { WorkingQuery, RecommendFeedItem };
