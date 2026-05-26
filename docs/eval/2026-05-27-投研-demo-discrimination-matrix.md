# 投研 + AI 跨域 Demo 区分力矩阵评估 (2026-05-27)

**总分**: 4/6 维通过 (66.7%)

## (a) P1 公募基本面 vs P6 量化私募 — strategy 主轴
- P1 strategy: 基本面权益
- P6 strategy: 量化
- top 5 公司 cross-leak: []
- **✅ pass**

## (b) P1 公募 vs P3 私募 — institution_tier overlap
- overlap: 0.0%
- **✅ pass (期望 ≤ 40%)**

## (c) P1 买方 vs P2 卖方 — strategy 内部区分
- separated_count: 3
- **❌ fail (期望 ≥ 4)**

## (d) P3 跨专业友好度
- 跨专业关键词命中: False
- **❌ fail**

## (e) 隐藏亮点挖掘
| Persona | hidden_highlight invoked |
|---|---|
| P1 | 1 |
| P2 | 2 |
| P3 | 4 |
| P6 | 4 |
| P_self | 10 |
- **✅ pass (期望每 persona ≥ 1)**

## (f) 跨域 P_self (AI) vs P1-P6 (投研) leak
- P_self top 8 公司: ['阿里巴巴达摩院（杭州）科技有限公司', '蚂蚁集团', '九坤投资', '灵均投资', '深圳市腾讯计算机系统有限公司', '华夏基金管理有限公司', 'AI 应用初创 (头部创业)', '字节跳动']
- 投研 persona top 公司: ['中信建投证券股份有限公司', '高瓴资本', '中金公司', '富国基金管理有限公司', '中再资产管理股份有限公司', '易方达基金管理有限公司', '华泰证券', '华夏基金', '九坤投资（北京）有限公司']
- cross-domain leak: []
- **✅ pass**
