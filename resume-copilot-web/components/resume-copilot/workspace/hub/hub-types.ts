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
      /**
       * 已定格(落库回放态): 直接渲染完成折叠态, 不播动画、不触发 onComplete。
       * 思考路径是交付物的一部分 —— 落库时打上此标, 重放能看到当时的轨迹。
       */
      settled?: boolean;
    }
  | { id: string; kind: 'result'; module: HubModule; data: ResultCardData }
  | { id: string; kind: 'trace'; trace: RecommendTrace }
  | { id: string; kind: 'memory'; text: string }
  | { id: string; kind: 'intel'; text: string };

export type { WorkingQuery, RecommendFeedItem };
