# Lever Playbook

## 适用范围
适用于采用 Lever 托管的官方招聘页。

## 识别信号
- URL 中出现 `lever.co`
- 页面或接口中出现 `lever`, `postings`
- 通常存在公开职位列表接口和详情页

## 推荐复用路径
- 优先复用：`JobRadar/backend/app/services/crawler.py`
- 相同家族优先 config-first，避免单站重复实现

## 推荐提取顺序
1. 公开职位列表 / 详情 JSON
2. 内嵌 structured payload
3. 稳定 HTML
4. Playwright 作为最后 fallback

## 常见字段映射
- text / title
- categories / team / commitment / location
- description / requirement / lists
- hosted URL / apply URL
- id / createdAt / updatedAt

## 常见失败点
- 职位列表字段多但正文需要详情接口
- location 与 commitment 在 categories 中嵌套
- 某些站点只暴露嵌入页，不直接暴露完整 board
- 多语言或多地区岗位混在同一 feed

## 安全回退策略
- 不绕过权限边界
- 先确认是否存在稳定公开 feed
- 先做单页、小样本验证
- 对 categories 字段做保守映射，不强行猜测

## 文档沉淀要求
新增 Lever 目标时，记录：
- board / postings URL
- 列表接口与详情接口关系
- categories 映射方式
- 多地区 / 多语言的筛选策略
