# 51job Campus Playbook

## 适用范围
适用于 `campus.51job.com/<slug>/` 这类前程无忧校园招聘 microsite。

## 识别方式
- URL 位于 `campus.51job.com`
- 页面标题通常为“XX校园招聘 / XX全球校园招聘”
- 可能直接存在 `jobs.html` 静态职位页
- 职位申请链接常见为 `*.51job.com/external/apply.aspx?...`

## 优先提取路径
1. 先探测 `jobs.html` 是否存在
2. 若 `jobs.html` 可访问，优先静态 HTML 表格提取
3. 若首页只有品牌落地页，再检查是否有 `apply.aspx` / `jobs.html` / 内嵌职位表
4. 若页面源码已注明“是否使用数据接口：否”且未暴露职位表，不要假设仍有公开列表 API

## 推荐复用路径
- 当前优先在 `JobRadar/backend/app/services/energy_crawler.py` 内做小分支复用
- 不要为了单个 microsite 新建平行大爬虫

## 已知变体
- `jolywood`：`jobs.html` 存在，可直接从静态职位表提取
- `gcl-power`：首页可访问，但仅为 2024 校招品牌页；`jobs.html` 返回 missing.php，当前无公开职位列表

## 常见失败点
- 首页可访问，但只是品牌页或过期活动页
- `jobs.html` 已下线，返回 `missing.php`
- 页面没有职位表、没有 `apply.aspx`、没有可跟进 detail 链接

## 失败标签建议
- `NO_JOB_SIGNAL`：页面仅有品牌内容，无职位表或申请链接
- `JOB_SIGNAL_BUT_ZERO_EXTRACTED`：页面写有招聘/职位提示，但抽不到职位
- `DETAIL_LINKS_FOUND_LIST_FAILED`：发现申请链接或详情链接，但列表结构失效
