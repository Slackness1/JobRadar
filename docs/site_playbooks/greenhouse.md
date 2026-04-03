# Greenhouse Playbook

## 适用范围
适用于采用 Greenhouse 托管的官方招聘页。

## 识别信号
- URL 中出现 `greenhouse.io`
- 页面或接口中出现 `greenhouse`, `boards`, `jobs`
- 常见是公司 board 页 + 职位详情页结构

## 推荐复用路径
- 优先复用：`JobRadar/backend/app/services/crawler.py`
- 若是同类 board 站点，优先以 config 或小分支支持

## 推荐提取顺序
1. board 页公开 JSON / API
2. 页面内嵌 structured payload
3. 稳定 HTML
4. Playwright 仅在前面都不足时使用

## 常见字段映射
- company
- title
- location
- department / team
- employment type
- updated_at / posted_at
- detail URL / application URL
- job id

## 常见失败点
- board 页和详情页字段粒度不同
- location 可能是 remote / multi-location / office 混合
- 某些公司自定义嵌入样式，DOM 不稳定
- 同一公司多个 board（校园 / 社招 / 子品牌）并存

## 安全回退策略
- 不绕过鉴权或站点保护
- 先确认 board 入口是否为官方入口
- 先抓列表，再决定是否补详情抓取
- 对多 board 场景保留 board 标识

## 文档沉淀要求
新增 Greenhouse 目标时，记录：
- board URL
- 是否存在多个 board
- 列表与详情字段差异
- location 和 department 的映射策略
