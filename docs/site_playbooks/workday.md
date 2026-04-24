# Workday Playbook

## 适用范围
适用于使用 Workday 承载的官方招聘站。

## 识别信号
- URL 中出现 `myworkdayjobs.com`
- 页面或接口中出现 `workday`、`wday`、`jobs` 等标记
- 职位列表和详情通常由公开 JSON 接口供数

## 推荐复用路径
- 优先复用：`JobRadar/backend/app/services/crawler.py`
- 若只是新增目标，优先补 config，不优先新建单独 crawler

## 推荐提取顺序
1. 公开职位 JSON / API
2. 初始化 payload / 内嵌 structured data
3. 稳定 HTML
4. Playwright 仅作补充或调试

## 常见字段映射
- title / job title
- locations / primary location
- posted date
- requisition id / external job id
- worker subtype / employment type
- detail URL / apply URL

## 常见失败点
- 不同租户的 URL 结构不同
- 校招 / 实习 / 社招分类在 query 参数里
- 列表页字段完整，但详情字段要二次请求
- 页面能开但部分接口受地区或代理影响

## 安全回退策略
- 不绕过登录、验证码、权限边界
- 先验证单个 tenant、单个 query、单页数据
- 记录租户命名、分页参数、详情接口路径

## 文档沉淀要求
新增 Workday 变体时，记录：
- tenant 识别方式
- 列表接口样式
- 分页方式
- 校招筛选条件
- 详情接口依赖
