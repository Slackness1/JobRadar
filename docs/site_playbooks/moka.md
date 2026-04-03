# MOKA Playbook

## 适用范围
适用于使用 MOKA 承载的招聘站点，常见域名或路径特征包括：
- `app.mokahr.com`
- 页面中出现 `mokahr`、`moka`、`recruitment` 等标记

## 识别方式
- URL 明显属于 `mokahr.com`
- 页面请求中存在稳定的职位列表接口或 JSON 返回
- 页面公司 slug / tenant id 可从 URL 或初始化数据中识别

## 优先提取路径
1. 先找公开职位列表 API / XHR
2. 再找页面初始化 payload
3. 再退到稳定 HTML
4. 仅在必要时使用 Playwright 补充

## 推荐复用路径
- 首先检查：`JobRadar/backend/app/services/moka_crawler.py`
- 如果只是新增公司 tenant 或配置，优先做 config / 小分支，不新建并行 crawler

## 常见字段映射
- 公司名：tenant / 页面标题 / payload company 字段
- 岗位名：job title / name
- 地点：city / location / addresses
- 岗位类型：campus / internship / social
- 岗位详情：description / requirement / responsibility
- 来源标识：job id / post id / detail url

## 常见失败点
- tenant slug 错误
- 列表接口需要额外 query 参数
- 校招 / 实习 / 社招分类入口不同
- 页面能开但岗位接口返回空数组
- 站点未开放招聘但入口页仍存在
- 某些公司先用自定义域名承接（如 `jobs.sungrowpower.com`），首页再跳到真正的 Moka `campus-recruitment/<slug>/<siteId>#/`；Discovery 时不要只停留在官网域名
- 也存在“bare tenant 可访问、历史 siteId 已失效”的情况；例如正泰可从 `https://app.mokahr.com/campus-recruitment/chint/` 命中真实入口并跳到 `chint/40745`，不要把旧 siteId 404 误判成整站失效
- 也存在“看起来像有效 Moka slug，但实际返回错误页”的情况；例如 `ningdeshidai/40951` 会返回 HTTP 400、title `-1`、`init-data` 只有 error payload，这类不能当成有效岗位入口

## 安全回退策略
- 不绕过登录、验证码、封禁
- 先缩小 target 范围验证单页、单分类
- 记录 tenant、接口、分页参数到配置或文档

## 文档沉淀要求
每新增一个稳定可复用的 MOKA 变体时，补充：
- 公司标识方式
- 列表接口样式
- 分页方式
- 校招筛选条件
- 失败特征
