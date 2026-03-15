# JobRadar 岗位情报增强层 — 系统设计文档

## 目标
基于现有 `jobs` 岗位主库，对用户感兴趣的岗位做定向搜索，从小红书/脉脉/牛客/BOSS直聘/知乎获取面试经验、薪资待遇、工作体验等情报信息。

---

## 1. 模块划分

### 1.1 后端模块

#### Intel Orchestrator 层
- **orchestrator.py** - 任务编排与调度
- **query_builder.py** - 搜索 query 生成
- **ranker.py** - 情报相关度打分
- **deduper.py** - 去重
- **normalizer.py** - 数据格式统一
- **extractor.py** - 实体抽取
- **snapshot_builder.py** - 摘要聚合

#### Platform Adapter 层
- **adapters/base.py** - 平台适配器基类
- **adapters/xiaohongshu.py** - 小红书适配器
- **adapters/maimai.py** - 脉脉适配器
- **adapters/nowcoder.py** - 牛客适配器
- **adapters/boss.py** - BOSS直聘适配器
- **adapters/zhihu.py** - 知乎适配器

#### Browser Session 层
- **session_manager.py** - 浏览器会话管理
- **storage_state.py** - 登录态持久化
- **login_bootstrap.py** - 登录引导

### 1.2 前端模块

#### 页面
- **JobIntel.tsx** - 岗位情报主页面

#### 组件
- **IntelSummaryCard.tsx** - 摘要卡片
- **IntelPlatformTabs.tsx** - 平台标签页
- **IntelRecordList.tsx** - 情报记录列表
- **IntelTaskStatus.tsx** - 任务状态显示
- **IntelSearchPanel.tsx** - 搜索控制面板

---

## 2. 数据表设计

### 2.1 job_intel_tasks（任务队列表）
用途：保存情报搜索任务

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| job_id | Integer | 关联 jobs.id |
| trigger_mode | String | manual / auto_follow / refresh |
| search_level | String | strict / expanded / historical / mixed |
| platform_scope_json | Text | 平台范围 JSON |
| query_bundle_json | Text | 搜索 query JSON |
| status | String | queued / running / partial / done / failed / auth_required |
| result_count | Integer | 结果数量 |
| error_message | Text | 错误信息 |
| started_at | DateTime | 开始时间 |
| finished_at | DateTime | 完成时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 2.2 job_intel_records（情报记录表）
用途：保存平台抓取到的主记录（帖子/回答/职位补充）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| job_id | Integer | 关联 jobs.id |
| task_id | Integer | 关联 job_intel_tasks.id |
| platform | String | xiaohongshu / maimai / nowcoder / boss / zhihu |
| content_type | String | post / answer / comment_thread / job_listing |
| platform_item_id | String | 平台内唯一 ID |
| title | Text | 标题 |
| author_name | String | 作者名 |
| author_meta_json | Text | 作者元数据 JSON |
| url | Text | 链接 |
| publish_time | DateTime | 发布时间 |
| raw_text | Text | 原始文本 |
| cleaned_text | Text | 清洗后文本 |
| summary | Text | 摘要 |
| keywords_json | Text | 关键词 JSON |
| tags_json | Text | 标签 JSON |
| metrics_json | Text | 指标 JSON（点赞/评论/收藏） |
| entities_json | Text | 实体抽取结果 JSON |
| relevance_score | Float | 相关度分数 |
| confidence_score | Float | 置信度分数 |
| sentiment | String | 情感倾向 |
| data_version | String | 数据版本 |
| fetched_at | DateTime | 抓取时间 |
| parsed_at | DateTime | 解析时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 2.3 job_intel_comments（评论表）
用途：保存评论明细

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| intel_record_id | Integer | 关联 job_intel_records.id |
| platform_comment_id | String | 平台评论 ID |
| parent_comment_id | String | 父评论 ID |
| author_name | String | 作者名 |
| content | Text | 评论内容 |
| like_count | Integer | 点赞数 |
| publish_time | DateTime | 发布时间 |
| relevance_score | Float | 相关度分数 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

### 2.4 job_intel_snapshots（摘要表）
用途：聚合展示摘要

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| job_id | Integer | 关联 jobs.id |
| snapshot_type | String | salary / interview / wlb / team / written_test |
| summary_text | Text | 摘要文本 |
| evidence_count | Integer | 证据数量 |
| source_platforms_json | Text | 来源平台 JSON |
| confidence_score | Float | 置信度分数 |
| generated_at | DateTime | 生成时间 |
| created_at | DateTime | 创建时间 |
| updated_at | DateTime | 更新时间 |

---

## 3. API 设计

前缀：`/api/job-intel`

### 3.1 创建搜索任务
```
POST /api/job-intel/jobs/{job_id}/search
```

**请求体**：
```json
{
  "trigger_mode": "manual",
  "platforms": ["xiaohongshu", "maimai", "nowcoder", "boss", "zhihu"],
  "force": false
}
```

**响应**：
```json
{
  "task_id": 123,
  "status": "queued",
  "query_bundle": {...}
}
```

### 3.2 获取情报摘要
```
GET /api/job-intel/jobs/{job_id}/summary
```

### 3.3 获取情报记录列表
```
GET /api/job-intel/jobs/{job_id}/records?platform=xiaohongshu&page=1&page_size=20
```

### 3.4 获取任务列表
```
GET /api/job-intel/jobs/{job_id}/tasks
```

### 3.5 获取任务详情
```
GET /api/job-intel/tasks/{task_id}
```

### 3.6 刷新情报
```
POST /api/job-intel/jobs/{job_id}/refresh
```

### 3.7 获取平台状态
```
GET /api/job-intel/platforms/status
```

### 3.8 平台登录引导
```
POST /api/job-intel/platforms/{platform}/bootstrap-login
```

---

## 4. 页面设计

### 4.1 JobIntel 主页面布局

#### A. 岗位基础信息卡
显示：
- 公司
- 岗位名
- 地点
- 发布时间
- intel 状态

#### B. 搜索控制面板
显示：
- 平台多选
- 强制刷新开关
- 搜索按钮

#### C. 任务状态卡
显示：
- 最新任务状态
- 最新错误
- 最近任务 id

#### D. 情报摘要卡区
显示：
- 薪资摘要
- 面试摘要
- 笔试摘要
- 工作体验摘要

#### E. 平台标签页
按平台分类：
- 全部
- 小红书
- 脉脉
- 牛客
- BOSS
- 知乎

#### F. 情报列表区
每条显示：
- 标题
- 平台
- 发布时间
- 相关度
- 摘要
- 原文链接
- 评论折叠区

---

## 5. Phase 1 范围

### 5.1 已完成
- 数据表设计文档
- 后端 model 新增
- 后端 schema 新增
- service 骨架创建
- 平台 adapter stub 创建
- router 创建并注册
- 前端 API 封装
- 前端页面骨架创建
- 前端组件骨架创建
- 前端路由接入
- Jobs 页面增加入口

### 5.2 未完成（后续 Phase）
- 真实平台爬虫接入
- 浏览器登录态管理
- 真实平台调用
- 数据质量优化
- 任务调度系统
- 反爬对抗

---

## 6. 实施计划

### Phase 1：骨架实现（当前）
1. ✅ 文档
2. ⬜ 后端 model
3. ⬜ 后端 schema
4. ⬜ service 骨架
5. ⬜ 平台 adapter stub
6. ⬜ router
7. ⬜ 前端 API
8. ⬜ 前端页面
9. ⬜ 前端组件
10. ⬜ 前端路由
11. ⬜ Jobs 页面入口
12. ⬜ mock 数据跑通

### Phase 2：单平台试点（后续）
- 接入牛客
- 接入小红书

### Phase 3：平台扩展（后续）
- 接入知乎
- 接入脉脉
- 接入 BOSS

### Phase 4：智能增强（后续）
- LLM 摘要
- 多源证据聚合
- 薪资/面试/强度结构化
- 自动刷新

### Phase 5：生产化（后续）
- 失败重试
- 登录失效管理
- 任务监控
- 限流面板
- 审计日志
- 反爬风险控制

---

## 7. 技术要点

### 7.1 依赖关系
```
Jobs (主表)
    ↓ 1:N
JobIntelTasks (任务表)
    ↓ 1:N
JobIntelRecords (记录表)
    ↓ 1:N
JobIntelComments (评论表)
    ↓ 1:1
JobIntelSnapshots (摘要表)
```

### 7.2 搜索策略
- strict：公司 + 岗位 + 年份 + 批次
- expanded：公司 + 岗位
- historical：公司 + 岗位 + 历史年份

### 7.3 平台特性
- 牛客：面经/笔试/offer 选择贴
- 小红书：面经/薪资/感受/内推
- 脉脉：薪资/团队/加班/hc/流程
- BOSS：岗位/JD/薪资/城市
- 知乎：长文经验/值不值得去/职业发展

---

## 8. 验收标准

### 8.1 后端
- [ ] 4 张 Job Intel 表已创建
- [ ] `/api/job-intel/...` 接口可访问
- [ ] 能创建搜索任务
- [ ] 能写入 mock records
- [ ] 能生成 snapshot
- [ ] 不影响原有 jobs/crawl 功能

### 8.2 前端
- [ ] 有 `/job-intel/:jobId` 页面
- [ ] Jobs 页面能跳转到情报页
- [ ] API 函数已封装
- [ ] 组件能渲染 mock 数据
- [ ] 搜索/刷新按钮功能正常
- [ ] 标签页切换正常
- [ ] 列表展示正常

### 8.3 E2E
- [ ] 创建任务 → 写入 records → 生成 snapshot → 前端显示全流程跑通
- [ ] 能看到 mock 的牛客面经记录
- [ ] 能看到 mock 的小红书薪资帖子
- [ ] 能切换平台标签页
- [ ] 能查看任务状态

---

**文档版本**: v1.0
**创建时间**: 2026-03-14
**适用阶段**: Phase 1
