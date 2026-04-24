# 招聘爬虫任务计划

## 角色分工
| 角色 | 模型 | 职责 |
|------|------|------|
| 主计划 | GPT-5.4 | 任务拆分、故障排查、协调 |
| 审核 | Claude Sonnet 4.6 | 验证方案合理性、风险评估 |
| 执行 | GLM-4.7-flashx | 实际爬取、数据处理 |

## 强制模型规则
- 重负载爬虫执行任务 **只允许** 使用 `zai/glm-4.7-flashx`
- **禁止** 使用 `zai/glm-5` 执行此类爬虫任务
- GPT-5.4 仅负责规划、排障、调度
- Sonnet 4.6 仅负责审核，不直接执行爬取

> ⚠️ 严禁使用 glm-5，所有执行子任务只允许 zai/glm-4.7-flashx

---

## 目标站点清单

| # | 公司 | URL | 上次状态 | 爬取策略 |
|---|------|-----|---------|---------|
| 1 | NIO蔚来 | https://nio.jobs.feishu.cn/campus/ | ❌ failed | Playwright + 等待 networkidle |
| 2 | 滴滴 | https://campus.didiglobal.com/campus_apply/didiglobal/96064#/jobs | ❌ failed | Playwright + hash路由等待 |
| 3 | 携程 | https://job.ctrip.com/#/campus/jobList | ✅ completed | Playwright（已有数据，增量） |
| 4 | 美团 | https://zhaopin.meituan.com/web/campus | ❌ failed | Playwright + scroll触发加载 |
| 5 | 小红书(校招) | https://job.xiaohongshu.com/campus/position | ❌ failed | Playwright + 拦截XHR |
| 6 | 中国平安 | https://campus.pingan.com/freshGraduates | ❌ failed | Playwright + 等待列表 |
| 7 | 腾讯 | https://careers.tencent.com/search.html?query=co_1&sc=1 | ❌ failed | REST API直接调用 |
| 8 | 字节跳动(分析) | https://jobs.bytedance.com/campus/position?keywords=... | ❌ failed | 拦截API response |
| 9 | 字节跳动(全量) | https://jobs.bytedance.com/campus/position | ❌ failed | 拦截API response |
| 10 | 小红书(社招) | https://job.xiaohongshu.com/social/position | ❌ failed | Playwright + 拦截XHR |
| 11 | 腾讯(join.qq.com) | https://join.qq.com/post.html?query=p_2 | ❌ failed | Playwright |
| 12 | 阿里巴巴 | https://talent.alibaba.com/campus/position-list | ❌ failed | Playwright + 等待React渲染 |
| 13 | 百度 | https://talent.baidu.com/jobs/list | ❌ failed | Playwright |
| 14 | 阿里Holding | https://talent-holding.alibaba.com/campus/position-list | ❌ failed | Playwright |
| 15 | 京东 | https://campus.jd.com/home#/jobs | ❌ failed | Playwright + hash路由 |
| 16 | 拼多多 | https://careers.pddglobalhr.com/campus/grad | ❌ failed | Playwright（超时，需增加等待） |
| 17 | 哔哩哔哩 | https://jobs.bilibili.com/campus/positions | ❌ failed | Playwright（超时，需增加等待） |
| 18 | 华为 | https://career.huawei.com/reccampportal/portal5/campus-recruitment.html | ✅ completed | 增量更新 |
| 19 | 招商银行 | https://career.cmbchina.com/positionlist/... | ❌ failed | Playwright + 修复NoneType错误 |
| 20 | 字节(list) | https://jobs.bytedance.com/campus/position/list | ❌ failed | 拦截API response |

---

## 技术方案

### 环境
- 浏览器: Chrome headless (已安装 /usr/bin/google-chrome-stable)
- 自动化: Playwright 1.58.0 (.venv)
- 代理: http://127.0.0.1:7890

### 核心改进策略

#### 1. 网络请求拦截（最可靠）
对字节跳动、腾讯等有明确后端API的站点：
```python
# 拦截 XHR/fetch 响应，直接抓 JSON
page.on('response', lambda r: capture(r) if 'api' in r.url else None)
```

#### 2. 增加等待时间（拼多多、哔哩哔哩超时修复）
- 超时从 15s 增加到 30s
- networkidle 后额外 sleep(3)

#### 3. 滚动加载（美团、小红书）
```python
page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
time.sleep(2)  # 重复直到无新内容
```

#### 4. 分页翻页（全量数据）
- 检测"下一页"按钮
- 循环爬取直到最后一页

### 输出
- 文件: `/home/ubuntu/workspace/job-crawler/data/jobs.csv`
- 字段: id, company, title, location, department, job_type, url, publish_date, deadline, description, crawled_at
- 去重: 基于 md5(company+title+url)

---

## 执行顺序（按成功率排序）
1. 腾讯 API（直接HTTP，最可靠）
2. 字节跳动（网络拦截）
3. 华为/携程（已成功，增量）
4. 其余 SPA 站点（Playwright + 改进选择器）

---

## 故障排查记录
| 问题 | 原因 | 修复 |
|------|------|------|
| 拼多多/哔哩哔哩超时 | 反爬慢加载 | 超时改30s + 额外sleep |
| 招商银行 NoneType | href为None时startswith崩溃 | 加 `if href and href.startswith(...)` |
| 字节跳动空响应 | API需要cookie/token | 改用网络拦截页面渲染后的请求 |
| 阿里巴巴404 | API路径不对 | 改走Playwright渲染 |


## 当前收敛结果
- 百度：已修复并成功入库（新增 10）
- 哔哩哔哩：已修复并成功入库（新增 19）
- 拼多多：已稳定复验，当前可抓取（本轮新增 0）
- 当前 CSV 路径：`/home/ubuntu/workspace/job-crawler/data/jobs.csv`
- 当前总行数（不含表头）：4785
- 当前已无硬 blocker；后续重点转为字段补全与详情页抓取。

---

## 本轮总结（2026-03-11）

### 三站详情补全完成情况
| 公司 | 详情补全状态 | 补到字段 | blocker |
|------|------------|---------|--------|
| 百度 | ✅ 完成 | desc / req / deadline | salary 未见 |
| 拼多多 | ✅ 完成 | desc / req | deadline / salary 未见 |
| 哔哩哔哩 | ✅ 完成 | desc / req / url / location / dept / date | ajSessionId 绕过（走列表接口）|

### 关键经验
- 哔哩哔哩：直接打开详情接口需要 ajSessionId，但列表页 positionList API 已含完整正文
- 拼多多：详情页短链不稳定，改用 `/api/recruit/position/detail` 接口替代
- 百度：DOM 句柄在页面重绘后失效，改用 `eval_on_selector_all` 一次性提取

---
