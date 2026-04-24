# Banks Playbook

## 适用范围
适用于国有银行、股份制银行、城商行、农商行及其科技子公司招聘站。

## 现有家族线索
当前项目中已存在银行相关路径：
- `JobRadar/backend/app/services/backfill_bankcomm.py`
- `scripts/run_bank_crawl.py`
- `JobRadar/backend/config/targets_v3.yaml`
- 根目录 `docs/` 下的银行爬虫说明文档

## 常见站点形态
- 官方自研招聘站
- `zhiye.com` 体系
- 独立前端 SPA + 后端 JSON 接口
- 银行官网栏目页跳转到招聘系统

## 推荐流程
1. 先判断是否已在 `targets_v3.yaml` 中
2. 再判断是否属于已有银行家族实现
3. 优先找公开 JSON / API
4. 再看 hydration / 初始化 payload
5. 最后再考虑 Playwright

## 重点字段
- company
- job_title
- location
- job_stage（campus / internship）
- publish_date
- deadline
- detail_url
- source_config_id

## 常见问题
- 招聘页可访问，但校招尚未开放
- TLS / SSL / 代理兼容问题
- 分行 / 总行入口分裂
- 校招与社招字段不一致
- 列表接口正常但详情接口字段缺失

## 处理原则
- 银行家族优先走 config-first
- 若只是入口变化，先改 config 或站点文档
- 若只有个别银行特殊，再做小型定制逻辑
- 补爬与恢复逻辑应尽量单独隔离，不污染通用路径

## 文档沉淀要求
新增银行规则时，记录：
- 是否已有 config entry
- 站点家族
- 列表发现方式
- 分页方式
- 校招 / 实习识别条件
- 详情字段缺口
- 是否需要专用 backfill 路径
