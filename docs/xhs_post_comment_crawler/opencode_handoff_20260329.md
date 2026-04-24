# XHS Post Comment Crawler Handoff

更新时间：2026-03-29  
来源目录：`D:\xhs_post_comment_crawler`

## 1. 项目定位

这是一个本地运行的小红书抓取器，目标不是做大规模匿名爬取，而是：

- 复用用户自己的浏览器登录态
- 尽量走 API-first 的抓取路径
- 在 API 被拦时回退到页面级抓取
- 支持帖子详情、评论、关键词搜帖、作者页采集、CSV/JSON 导出和基础分析

当前它更适合：

- 定向帖子与评论抓取
- 关键词情报采集
- 小规模批量分析
- 基于人工登录态的稳定采集

当前它不适合：

- 高并发、大规模、持续无人值守的集群抓取
- 绕过登录态的大规模匿名采集
- 追求全平台级覆盖和极高吞吐

## 2. 当前架构

### 2.1 代码结构

核心包在 `src/xhs_post_comment_crawler/`：

- `cli.py`
  - CLI 入口
  - 当前命令包括：`login`、`check-profile`、`export-cookies`、`import-cookies`、`smoke-test`、`fetch`、`search-fetch`、`author-fetch`
- `session.py`
  - Playwright 持久化 profile 管理
  - 登录态快照导入导出
  - profile 与 session snapshot 双保险
- `signer.py`
  - 小红书 Web 签名运行时
  - 管理 `a1 / b1 / user-agent / sec-ch-ua / cookie_header`
- `client.py`
  - API-first 请求层
  - 搜索、详情、评论、作者 profile、作者帖子分页
  - 统一错误解析与重试
- `crawler.py`
  - 单帖抓取逻辑
  - API 与页面 fallback 的组合
- `searcher.py`
  - 搜索结果页采集
- `author.py`
  - 作者主页 fallback 采集器
  - 通过监听 `user_posted` 响应和滚动主页收集帖子
- `exporters.py`
  - CSV 导出
  - 兼容 snake_case 和 camelCase 字段
- `analysis.py`
  - 基础信号评分
  - 标签、关键词、互动等统计
- `utils.py`
  - URL 解析
  - note / creator 输入解析
- `paths.py`
  - 项目根路径与输出路径管理

### 2.2 运行链路

当前主链路是：

`持久化浏览器 profile -> session snapshot -> 页面内签名 -> API 请求 -> 页面 fallback -> 导出 / 分析`

具体来说：

1. 用 Playwright 打开持久化 profile
2. 从 cookie 与 localStorage 中恢复关键状态
3. 在页面上下文中生成签名头
4. 优先请求搜索、详情、评论接口
5. 接口失败时回退到真实页面抓取
6. 将结果导出为 JSON / CSV，并输出基础分析

## 3. 项目边界

### 3.1 明确做了什么

- 单帖抓取
- 评论分页抓取
- 关键词搜帖并批量抓评论
- 作者主页采集接口与页面 fallback
- 登录态持久化
- cookie / localStorage 快照导入导出
- API-first 抓取
- 基础情报总结导出

### 3.2 明确没做什么

- GUI
- SQLite 任务系统
- 托盘驻留
- 自动更新
- 授权 / 机器码
- 下载器
- 大规模任务编排
- 远端部署方案

这些是 XHS Spider 一类产品化工具会做的事，但当前项目刻意没有带上。

## 4. 参考与吸收的成熟方案

### 4.1 MediaCrawler

吸收的核心思路：

- 持久化登录态
- 页面内签名
- API-first
- 评论接口分页而非纯 DOM 滚动
- 出错后做 fallback

### 4.2 XHS Spider

吸收的核心思路：

- 登录态双保险
- cookie 持久化
- 签名运行时封装
- 更产品化的会话管理
- 作者接口与搜索接口的使用方式

已单独写过对比文档：

- `docs/xhs_spider_comparison.md`

## 5. 已做的关键优化

### 5.1 登录态稳定性

最初只依赖 Playwright profile，后来升级成：

- `profile` 持久化目录
- `session_snapshot.json`

快照里保存：

- 小红书相关 cookies
- localStorage
- user agent
- 保存时间

打开会话时会优先检查 profile 中关键状态，不足时自动从快照恢复。

### 5.2 API-first 改造

原始页面滚动抓评论太慢，所以做了：

- 搜索优先走 API
- 评论优先走 API
- 详情尽量走 API
- API 不稳定时回退到 HTML / 页面响应

### 5.3 签名运行时

把签名从散乱调用改成运行时对象：

- 缓存 `a1 / b1 / ua / sec-ch-ua / cookie_header`
- 遇到 `406 / 419 / 非 JSON / 签名失效` 时自动刷新并重试

### 5.4 导出与分析兼容性

因为作者页和搜索页返回的字段命名不一致，后面做了兼容：

- `snake_case`
- `camelCase`

现在 `exporters.py` 和 `analysis.py` 已经兼容两种命名。

### 5.5 作者页采集能力

新增了：

- `author-fetch`
- 作者 API 分页抓帖
- 作者页滚动 fallback

这条链路在代码上已经打通。

## 6. 当前遇到过的问题

### 6.1 profile 路径错误

一开始 `PROJECT_ROOT` 算错，导致 profile 被写到了错误目录。后来已修复。

### 6.2 Chromium profile 不稳定

持久化 profile 迁移后，Chromium 可能直接退出，表现为 `TargetClosedError` 或进程异常退出。后来通过：

- 清理锁文件
- session snapshot 补偿
- fallback 到旧 profile

降低了影响。

### 6.3 CLI 的人工输入阻塞

最早版本里 `login` 和部分抓取流程依赖 `input()` 手工确认，不适合并行自动化。后面做过一定收敛，但整体仍属于“半自动工具”。

### 6.4 PowerShell 中文编码污染

通过终端参数传中文关键词时，出现过乱码、emoji 打断输出等问题。后面主要通过：

- UTF-8 输出
- 少打印，多落盘

规避。

### 6.5 搜索与详情数据字段不一致

搜索结果常见 `display_title`、`interactInfo`

详情或其他接口常见：

- `title`
- `interact_info`

已经在导出和分析层做兼容。

### 6.6 作者页风控

这是当前最明显的未彻底解决问题。

现象：

- 作者帖子 API 经常返回 `HTTP 406`
- 作者页 fallback 会直接显示“请求太频繁，请稍后再试”

结论：

- 作者级批量采集能力已经在代码里有了
- 但在当前网络 / 会话下，作者页风控仍然是主要瓶颈

## 7. 已验证过的能力

本地已验证成功的命令包括：

- `xhs-crawler check-profile --profile default`
- `xhs-crawler export-cookies ...`
- `xhs-crawler import-cookies ...`
- `xhs-crawler smoke-test --profile default`
- `xhs-crawler fetch "<完整帖子 URL>"`
- `xhs-crawler search-fetch "<关键词>"`
- `xhs-crawler author-fetch ...`
  - 代码路径已成功验证过
  - 但近期批量抓作者时被平台风控限制

## 8. 当前适合迁移到远端的内容

建议迁移：

- `src/`
- `pyproject.toml`
- `README.md`
- `docs/xhs_spider_comparison.md`
- 本文档
- 输出中的总结性 markdown

不建议直接迁移：

- `.venv`
- `.venv_local`
- `profiles`
- 大体量原始输出

原因：

- 虚拟环境不可移植
- 登录态不应直接复制到远端长期保存
- 原始输出体积大且有时效性

## 9. 建议的远端落地方式

远端建议以子模块方式落地，例如：

- `tools/xhs_post_comment_crawler/`
- `docs/xhs_post_comment_crawler_handoff.md`

而不是直接覆盖现有项目根目录。

## 10. 后续优化建议

优先级最高：

- 作者页风控分类与重试策略
- 高频失败类型统计
- `1.1万` 这种中文数字缩写兼容
- 中文关键词编码统一

第二优先级：

- 行业级预设搜索模板
- 分析报告模板化
- 远端运行脚本

第三优先级：

- GUI 或 Web 控制台
- SQLite 任务库
- 调度系统

## 11. 当前结论

这个项目当前已经从“页面滚动抓评论的小脚本”进化到了：

`登录态管理 + 签名运行时 + API-first + 页面 fallback + 搜索 / 作者 / 评论 / 分析`

它已经具备继续工程化的基础，但还没有走到完整产品态。
