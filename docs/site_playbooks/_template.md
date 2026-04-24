# <Platform or Site Family> Playbook

## 适用范围
- 说明该 playbook 适用于哪些公司、ATS、站点家族或行业目标。

## 识别信号
- URL / 域名特征
- 页面文本特征
- 初始化数据 / 接口特征
- 前端框架或脚本特征

## 推荐复用路径
- 优先检查的 crawler：
- 优先检查的 config：
- 是否优先 config-first：

## 推荐提取顺序
1. public JSON / API
2. hydration / embedded structured payload
3. stable HTML
4. Playwright fallback

## 常见字段映射
- company
- job_title
- location
- job_stage / employment type
- publish_date
- deadline
- detail_url / apply_url
- source identifier

## 常见失败点
- 
- 
- 

## 安全回退策略
- 不绕过登录 / CAPTCHA / 风控 / 封禁
- 先小样本验证
- 明确失败阶段

## 项目落点
- playbook 文档：`JobRadar/docs/site_playbooks/`
- config：`JobRadar/backend/config/`
- crawler：`JobRadar/backend/app/services/`
- 报告：`data/`
- 临时抓取：`data/tmp/`

## 需要补充到 memory 的场景
- 该家族成为长期重点目标
- 路径规范发生变化
- 需要长期保留的稳定策略或决策
