# Site Playbooks Index

## 目的
这个目录用于沉淀 JobRadar 的站点家族、ATS 平台、行业站点规则。

## 使用顺序
1. 先判断目标属于哪个家族或 ATS
2. 再打开对应 playbook
3. 若现有 playbook 不覆盖，再新建或扩展文档
4. 新规律落地时，优先补文档，再决定是否批量重跑

## 当前文档地图
- `moka.md`：MOKA 平台站点
- `51job_campus.md`：前程无忧校园招聘 microsite
- `banks.md`：银行招聘站家族
- `securities.md`：券商招聘站家族
- `custom_sites.md`：未知 ATS 的自定义官网
- `workday.md`：Workday 平台
- `greenhouse.md`：Greenhouse 平台
- `lever.md`：Lever 平台
- `_template.md`：新增 playbook 的模板

## 推荐分类方法
优先把目标归为以下之一：
- 现有 crawler 家族
- 现有 config 家族
- 已知 ATS（MOKA / Workday / Greenhouse / Lever）
- 银行 / 券商行业家族
- 自定义官方站点

## 更新规则
当发现新规律时：
- 小变体 → 更新现有 playbook
- 新 ATS 家族 → 新建单独 playbook
- 仅为某一家公司的特殊性 → 记入对应家族文档，并标出公司名
- 若会影响执行路径、命令或产物位置，同时同步 `TOOLS.md`

## 最小记录要求
每篇 playbook 至少应记录：
- 识别信号
- 推荐 crawler 路径
- 推荐 extraction method
- 字段映射提示
- 常见失败点
- 安全回退策略
