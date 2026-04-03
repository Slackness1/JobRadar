# Custom Sites Playbook

## 适用范围
适用于不属于已知 ATS 家族、但属于公司官方招聘站的自定义站点。

## 适用前提
在确认目标不明显属于 MOKA、Workday、Greenhouse、Lever、zhiye 或现有银行 / 券商家族后，再归入 custom sites。

## 推荐方法
1. 先看页面源码是否含内嵌 JSON / hydration payload
2. 再看网络请求中是否有公开列表接口与详情接口
3. 再看是否可用稳定 HTML 解析
4. 只有前面都不稳定时才使用 Playwright

## 复用优先级
- 先看 `JobRadar/backend/app/services/crawler.py`
- 若只是小变体，优先加 config 或小分支
- 不要轻易创建新的单站独占 crawler

## 常见识别信号
- 公司官网 careers / jobs / join-us 栏目
- React / Vue / Next SPA
- 页面内出现初始化状态对象
- 列表页与详情页通过同一公共接口供数

## 常见失败点
- 入口页存在，但岗位接口已下线
- 站点只暴露前端页，不暴露可稳定抓取的数据
- 字段命名不统一，标题与详情分离严重
- 页面结构频繁变化，静态 DOM 选择器脆弱
- 官网招聘页先落到 WAF / JS challenge（例如仅返回阿里云验证码脚本 `AliyunCaptcha.js`），此时不要把页面可打开误判成可提取；应标记 `BLOCKED_OR_EMPTY_RESPONSE`，并保留挑战页证据

## 输出要求
处理 custom site 时，在结果或报告里明确写出：
- 是否为官方站
- 是否识别出框架或前端家族
- 最终使用的提取方式
- 是否需要新增 config
- 是否建议沉淀为新的 site playbook

## 文档沉淀要求
当 custom site 具有可复用模式时，不要只保留在本文件；应新增独立文档，例如：
- `workday.md`
- `greenhouse.md`
- `lever.md`
- `custom_<family>.md`
