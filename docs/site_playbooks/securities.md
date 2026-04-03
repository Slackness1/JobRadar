# Securities Playbook

## 适用范围
适用于券商、证券研究所、券商子公司及其校园招聘 / 实习招聘站点。

## 当前项目已有路径
- `JobRadar/backend/app/services/securities_crawler.py`
- `JobRadar/backend/app/services/securities_playwright_crawler.py`
- `JobRadar/backend/config/securities_campus.yaml`

## 站点家族
券商招聘常见为：
- 官方自研招聘站
- `zhiye.com` 体系
- 独立前端站点 + JSON 接口
- 招聘栏目页跳转至外部 ATS

## 推荐提取顺序
1. 先验证是否有公开职位 JSON / API
2. 再检查 hydration payload、内嵌初始化数据
3. 再做稳定 HTML 解析
4. 最后才用 Playwright

## 当前经验
- 券商官网常出现入口可见、实际响应为空、或代理 / TLS / 浏览器兼容异常
- 某些官方入口更像导航页，不直接承载职位数据
- 海投 / 聚合页可作发现线索，但官方站仍应优先作为主数据源

## 环境配置要求
⚠️ **Playwright 必须带代理才可访问 HTTPS 站点**

券商官网普遍使用 HTTPS，且很多页面依赖 JS 渲染。如果 Playwright 启动时未配置代理，会导致：
- `ERR_EMPTY_RESPONSE`
- HTTP 403/404
- 页面内容为空或只有框架

**正确配置示例** (`securities_playwright_crawler.py`):
```python
PROXY_SERVER = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or "http://127.0.0.1:7890"

browser = p.chromium.launch(
    headless=True,
    proxy={"server": PROXY_SERVER}
)
```

**代理验证**:
```bash
# 测试代理是否可用
python3 scripts/test_proxy.py

# curl 测试
curl -x http://127.0.0.1:7890 https://www.baidu.com
```

## 推荐工作流
1. 先看 `securities_campus.yaml` 是否已有目标
2. 优先复用 `securities_crawler.py` 或 `securities_playwright_crawler.py`
3. 明确当前使用的是聚合源、官网 HTML、官网结构化接口还是 Playwright
4. 对结果保留 source identifier、detail_url、crawl timestamp

## 常见失败点
- 招聘站仅有壳页面，无公开数据
- 页面需要 JS 渲染，但 Playwright / 代理链不稳定
- 券商合并或品牌调整导致旧入口失效
- 校招和社招混在同一站点，筛选规则不明确

## 文档沉淀要求
每新增一类券商站点时，记录：
- 公司 / 品牌 / 合并口径
- 站点家族
- 入口 URL
- 列表来源
- 分页逻辑
- 校招识别条件
- 已知失败模式
- 推荐 crawler 路径

## 2026-03-22 第三轮重试新增经验

### 已确认可复用 ATS 家族

#### 1) zhiye / 北森（公开 JSON 可优先）
**已验证公司**：
- 中金公司：`https://cicc.zhiye.com/custom/campus?&hideMenu=1`
- 国金证券：`http://career.gjzq.com.cn/custom/campus`

**优先抓取接口**：
- `POST {base}/api/Jobad/GetJobAdPageList`

**最小请求样例**：
```json
{
  "PageIndex": 0,
  "PageSize": 20,
  "KeyWords": "",
  "SpecialType": 0,
  "PortalId": "",
  "DisplayFields": ["Category", "Kind", "LocId", "ClassificationOne"]
}
```

**字段要点**：
- 标题：`JobAdName`
- 地点：`LocNames`
- 职责：`Duty`
- 要求：`Require`
- 分类：`Category`
- 明细 ID：`Id`

**本轮经验**：
- 同一 zhiye 站可能混出 `社会招聘 / 校园招聘 / 实习生招聘 / 项目实习`
- 不要只因 referer 是 `/custom/campus` 就默认全是 campus；应按 `Category` 二次过滤
- 国金证券公开 API 同时包含 campus / intern / social，需保守过滤后再入库
- 中金公司当前公开数据以 `项目实习` 为主，可按 internship 入库

#### 2) Hotjob / 北森（公开 JSON 可优先）
**已验证公司**：
- 安信证券：`https://wecruit.hotjob.cn/SU625d4a0b2f9d24287db127c8/pb/school.html`
- 中泰证券：`https://zts.hotjob.cn/` → `SU62bd501c0dcad406d143caea`

**优先抓取接口**：
- `POST https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}`

**关键参数**：
- `recruitType=1`：campus
- `recruitType=2`：social
- `recruitType=3`：intern

**表单体**：
```x-www-form-urlencoded
isFrompb=true
recruitType=1
pageSize=15
currentPage=1
```

**字段要点**：
- 标题：`postName`
- 地点：`workPlaceStr`
- 发布时间：`publishDate` / `publishFirstDate`
- 截止时间：`endDate`
- 分类：`postTypeName`
- 明细 ID：`postId`

**本轮经验**：
- 官网不一定直接给出职位，但常会公开挂出 `school.html / interns.html / social.html`
- 中泰证券已确认真实 ATS 为 Hotjob，但当前 `recruitType=1/3` 为空，仅 `recruitType=2` 非空
- 若任务口径是 campus/intern，就不要把 social 混入

### 本轮失败模式更新
- **旧官网入口 404/400**：中信证券、中信建投、兴业证券
- **旧 zhiye 根入口失效**：国泰君安 `gtja.zhiye.com` 跳 404
- **品牌整合导致旧招聘页失效**：海通证券旧招聘页跳国泰海通首页
- **连接关闭或 403**：东方证券、光大证券
- **自研 SPA 只见 bundle 未见列表接口**：华泰证券

### 推荐路径（2026-03-22 之后）
1. 先从 `securities_campus.yaml` 读取 `entry_url + ats_family`
2. `ats_family=zhiye` → 先打 `GetJobAdPageList`
3. `ats_family=hotjob` → 先打 `listPosition/{suite}`
4. `ats_family=custom_site` → 先抓 bundle / 运行时请求，确认 API 后再写逻辑
5. 对已 404/400/403 的旧入口，不要再直接沿旧 URL 批量重跑

## 2026-03-22 第四轮（基于用户新入口）新增经验

### 1) Moka 页面内嵌 payload 可直接抓
**已验证公司**：
- 东方证券：`https://app.mokahr.com/campus_apply/dfzq/4928#/jobs?keyword=`

**提取方式**：
- 不必先等前端请求 API
- 直接解析页面中的 `<input id="init-data" ...>`
- 该 hidden input 内就是完整 JSON payload，含 `jobs / jobStats / org / siteId`

**字段要点**：
- `jobs[].id`：岗位主键
- `jobs[].title`：标题
- `jobs[].department.name`：部门
- `jobs[].zhineng.name`：职类
- `jobs[].locations[].address`：地点
- `jobs[].publishedAt / openedAt / closedAt`：时间

**本轮经验**：
- 东方证券这个新入口可直接拿到 5 条公开岗位
- Moka 站点有时列表页已内嵌好岗位，不需要额外 Playwright
- 仍要保守处理：如果 payload 只有页面配置、没有 `jobs`，不要误判为有公开职位

### 2) Hotjob 新入口优先用来验证，API 可映射到 wecruit
**已验证公司**：
- 中泰证券：`https://wecruit.hotjob.cn/SU62bd501c0dcad406d143caea/pb/school.html`
- 安信证券：`https://sc.hotjob.cn/wt/Essence/mobweb/v8/position/subscriptionPositionList`
- 兴业证券：`https://xyzq.hotjob.cn/`

**本轮经验**：
- 新入口不一定直接等于最终抓取 API 域名
- 安信证券移动页在 `sc.hotjob.cn`，但公开职位仍可通过 `wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}` 稳定拉取
- 中泰证券新 school 入口可直接验证 `recruitType=1/3` 为空，仅 social 非空；因此应明确记 0，而不是混入社招
- 兴业证券新官网虽是 Hotjob，但当前导航仅见社会招聘 / 博士后招聘，未见公开 campus 列表，应记为 `no-public-campus-data boundary`

### 3) zhiye 的 campus 入口要按分类做硬过滤
**已验证公司**：
- 光大证券：`https://ebscn.zhiye.com/campus`
- 国金证券：`https://gjzq.zhiye.com/campus/jobs`

**本轮经验**：
- zhiye campus URL 也可能公开的是 social 列表
- 光大证券当前 API 可访问，但 `Category` 全是 `社会招聘`，因此 campus/intern 应记 0
- 国金证券当前仍是混合池，必须保留 `Category in {校园招聘, 实习生招聘}` 的过滤逻辑

### 4) 国泰海通当前属于 TLS / 链路级边界
**已验证入口**：
- `https://hr.gtht.com/recruitment/main/recruit2`

**本轮经验**：
- requests / curl：报 `unsafe legacy renegotiation disabled`
- 浏览器：`ERR_EMPTY_RESPONSE`
- 这类情况要明确标注为 **真实入口已确认，但当前不可稳定抓取**，不要伪造 0 条列表，也不要混入旧品牌站数据

## 2026-03-22 第五轮（A-档优先）新增经验

### 1) Hotjob 可直接从公开 detail_url 反推 school 入口
**已验证公司**：
- 招商证券：`https://wecruit.hotjob.cn/SU629dbc0c0dcad452299bc0f7/pb/school.html`
- 广发证券：`https://wecruit.hotjob.cn/SU652e4d276202cc264477df09/pb/school.html`

**提取方式**：
- 先从库内公开详情链接或页面跳转识别 `SU...` suite
- 再直接调用 `POST https://wecruit.hotjob.cn/wecruit/positionInfo/listPosition/{suite}`
- 只跑 `recruitType in {1(campus), 3(intern)}`，不要混 `2(social)`

**本轮经验**：
- 招商证券当前公开校招列表稳定，`recruitType=3` 为空，新增 19 条 campus
- 广发证券主 suite `SU652e4d276202cc264477df09` 当前公开校招列表稳定，新增 47 条 campus/intern
- 同一家券商可能存在多个 Hotjob suite；若多个 suite 仅表现为同岗位重复镜像，优先保守选主 suite，不做横向混并

### 2) Moka `campus-recruitment` 也能直接吃 `#init-data`
**已验证公司**：
- 申万宏源：`https://app.mokahr.com/campus-recruitment/swhysc-job/140752#/jobs`

**提取方式**：
- 直接解析页面 `<input id="init-data" ...>`
- 不限于 `campus_apply/{org}/{site}`；`campus-recruitment/{org}/{site}` 同样可用
- 详情 URL 需要按站点路径模板拼接，不能硬编码成 `campus_apply`

**本轮经验**：
- 申万宏源 `init-data` 当前内嵌 15 条公开 jobs
- payload 同时给出 `org.id=swhysc-job`、`siteId=140752`、`jobs[]`
- 页面公告明确春季校园招聘窗口存在，因此可按 campus 口径稳定入库

### 3) A-档失败模式补充
- **中国银河**：第五轮仅做到官网主页；第六轮已从 `newsite/join-us.html` 反查到独立 zhiye 入口 `https://chinastock.zhiye.com/custom/campus`，但当前公开 API 列表全部为 `内部交流 / 社会招聘（外部招聘）/ 社会招聘（内部招聘）`，过滤后 campus/intern = 0，因此失败阶段从 `entry discovery` 更新为 `listing filtering / no-public-campus-data boundary`
- **国信证券**：第六轮确认无需继续硬顶官网根域，存在独立 zhiye 招聘站 `https://guosen.zhiye.com/custom/campus`；公开 API 稳定可抓，已脱离 TLS 边界

## 2026-03-22 第六轮（突破中国银河 / 国信证券）新增经验

### 1) 中国银河官网 `join-us` 已显式跳转到独立 zhiye
**已验证入口**：
- 官网：`https://www.chinastock.com.cn/newsite/join-us.html`
- 校招：`https://chinastock.zhiye.com/custom/campus`
- 实习：`https://chinastock.zhiye.com/custom/intern`

**提取方式**：
- 先从官网 HTML 导航发现真实入口
- 再直接调用 `POST https://chinastock.zhiye.com/api/Jobad/GetJobAdPageList`

**本轮经验**：
- 官网主页本身只是 JS 跳转壳页，不要停在根域首页判断“没入口”
- 中国银河的真实 ATS 已确认是 `zhiye`
- 但当前公开 146 条列表全部落在 `内部交流 / 社会招聘（外部招聘）/ 社会招聘（内部招聘）`
- 因此本轮应明确记为 **真实入口已发现，但当前无公开 campus/intern 数据**，而不是继续记为入口未发现

### 2) 国信证券存在独立 zhiye 招聘站，可绕开官网 legacy TLS
**已验证入口**：
- 校招：`https://guosen.zhiye.com/custom/campus`
- 实习：`https://guosen.zhiye.com/custom/intern`

**提取方式**：
- 直接调用 `POST https://guosen.zhiye.com/api/Jobad/GetJobAdPageList`
- 过滤 `Category in {校园招聘, 实习生招聘}`
- 额外排除标题含 `博士后` 的记录，避免把博士后混入 campus 口径

**本轮结果**：
- 公开列表：`校园招聘 25 + 实习生招聘 30 + 社会招聘 38`
- 过滤后实际入库：`校园招聘 24 + 实习 30 = 54`
- 说明前期“国信证券卡在官网 TLS 边界”的结论只适用于根域入口，不适用于真实 ATS

### 3) zhiye 过滤规则需要支持“类别通过、标题再排除”
**适用场景**：
- 某些站会把 `博士后` 挂在 `校园招聘` 分类下

**本轮经验**：
- 仅按 `Category` 过滤还不够
- 对国信证券这类情况，需要在 config 中补 `exclude_title_keywords: ["博士后"]`
- crawler 应保留通用的标题排除能力，避免为了单个站点硬编码
