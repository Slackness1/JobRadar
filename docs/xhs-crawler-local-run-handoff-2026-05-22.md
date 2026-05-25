# 小红书爬取 — 本机运行 handoff(2026-05-22)

> 这份文档是 2026-05-22 一次会话的全量交接。覆盖三件事:
>
> 1. **输入** — 用户给的 2026-05 外网共识(Twitter / X 上"小红书爬取最佳实践"汇总)
> 2. **过程** — 我们对照清单逐项核了现在 `xhs_post_comment_crawler` 缺哪几块、又踩过哪些坑
> 3. **结论 + 落地计划** — 实际怎么跑、为什么这么跑、不跑哪些
>
> 看这份文档前不需要看 `opencode_handoff_20260329.md`,该文档是早期版本;本文是最新口径。

---

## 0. TL;DR(30 秒)

| 项 | 决定 |
|---|---|
| **跑在哪台机器上** | 用户本机(中国大陆,大陆家宽 WiFi) |
| **用哪个浏览器** | **CDP attach 到用户日常用的真 Chrome**,**不**用 Playwright bundled Chromium |
| **用哪个 XHS 账号** | **新号或日常使用的另一个老号** — **不**再用已经被警告/封过的那个(它已经被打了 risk tag) |
| **加什么补丁** | `playwright-stealth`(补 WebRTC / Notification / plugins 几个 Playwright 残留漏) |
| **抓多少** | **首周 ≤ 30 篇/天**,跑 1-2 周观察账号是否被警告再考虑提速 |
| **代码改动** | crawler 加一个 `--cdp-url` 选项,把 `launch_persistent_context` 切换成 `connect_over_cdp`,~20 行 |
| **不做什么** | 不接住宅代理 / 不接 XCrawl / 不上 Multilogin — 现阶段不值 |

---

## 1. 输入:外网共识清单(用户 2026-05-22 提供,原文压缩)

### 1.1 当前主流路线(讨论热度)

| 路线 | 代表项目 | 适用 |
|---|---|---|
| CDP 浏览器自动化 + Skill | `white0dew/XiaohongshuSkills` | 全流程 Agent(抓+发+互动) |
| MCP for AI Agents | `xpzouying/xiaohongshu-mcp` | Claude Code / Cursor 等直接调 |
| 多平台成熟爬虫 | `NanmiCoder/MediaCrawler`(已支持 CDP 模式) | 批量数据采集 |
| AI 专用爬虫服务 | XCrawl(`xcrawl.com`) | 给 Agent 喂干净结构化数据(SaaS) |
| 云手机 + 视觉 Agent | 扣子 / EVE 类 | 高成功率数据调研 |

### 1.2 清单最佳实践

**代理与指纹(清单认为最关键)**
- 必须用住宅代理 / 移动代理,数据中心 IP 秒封
- 浏览器指纹伪装:canvas / WebGL / 字体 / 时区 / 语言 / 硬件并发
- 按请求/会话轮换

**浏览器自动化优先(CDP > 普通 Playwright)**
- CDP 模式(连接本地真实 Chrome)是 SOTA — 复用已登录 cookie / 扩展,检测风险大幅降低
- DOM 频繁改版 → 用 API 响应监听而非 DOM selector
- Headless 生产用,可视化用于首次登录/调试

**账号与行为模拟**
- 多账号隔离(不同 Chrome Profile / Cookie 存储)
- 扫码登录(App)+ 本地缓存
- 行为像真人:随机延迟、滚动加载、不要高并发、~50 条/日
- **养号** — 先慢慢刷、点赞、收藏再大规模操作

**数据 / Agent 集成**
- 输出干净 Markdown / JSON 喂 LLM
- 包装成 Skill / MCP
- workflow: Agent 规划 → scrape/crawl → LLM 分析

**维护与容错**
- 工具持续维护(2026-02/03 XHS 大改版)
- 重试 + 降级(切代理 / 账号 / 策略)
- 监控封禁率,及时轮换

---

## 2. 现状:`xhs_post_comment_crawler` 对账

`tools/xhs_post_comment_crawler/`(editable install,CLI `xhs-crawler`)

### 2.1 我们已经做对的(13 项里 11 项 🟢)

| 维度 | 实现 |
|---|---|
| 浏览器形态 | Playwright `launch_persistent_context`(真 Chromium + 持久 profile)+ `--disable-blink-features=AutomationControlled` |
| 登录态复用 | `profiles/<name>/` 持久 user_data_dir + `session_snapshot.json` 单存 cookies + localStorage(含 `b1`,XHS 关键风控字段) |
| 详情/评论采集 | **双引擎**:`XhsPageCrawler` 监听 `/api/sns/web/v1/feed`、`/v2/comment/page`、`/v2/comment/sub/page`;`XhsApiCrawler` 直接调签名 API,fallback 走 HTML `__INITIAL_STATE__` |
| 签名(X-s) | **自带 `signer.py`**,完整实现 CRC + custom-base64 + `XYS_` 前缀算法,从 `navigator.userAgentData` 现取 x3 — **不依赖外部签名服务** |
| 搜索 | `XhsSearchCollector` 监听 `/api/sns/web/v1/search/notes`,异步入库 |
| 行为节奏 | `pause_ms` 可配(默认 1500ms);评论展开 3 轮无新增就停;子评论分页有 `sleep_seconds` |
| 多账号基建 | `profile_dir(profile)` 已支持多 profile |
| 输出 | JSON + CSV 双输出,`notes.csv`/`comments.csv`/`analysis.json`/`report.md` |
| Agent 集成 | 已经是 `/home/ubuntu/.claude/skills/xhs-crawl/` skill 形态 |
| DOM 抗改版 | 采集走 API 响应监听 + `__INITIAL_STATE__` 兜底,只有"展开"按钮用 7 种 selector |
| 评论展开 | 7 种 selector 覆盖"展开 / 查看更多 / 显示更多 / 回复 …" |

### 2.2 缺口(2 项 🔴)

| 维度 | 现状 | 影响 |
|---|---|---|
| **浏览器指纹伪装** | 只有 `disable-blink-features` + `locale=zh-CN` + `timezone=Asia/Shanghai`。canvas / WebGL / 字体 / 音频 / WebRTC / `navigator.plugins` 没动 | **2026-05 这次账号被警告→封号的真凶**,见 §4 |
| **CDP attach 真实 Chrome**(清单第 1 推荐) | 用的是 Playwright bundled Chromium | 跟 §1 缺口同源 — 用 bundled Chromium = 全宇宙 Playwright 共享同一组 canvas 指纹 |

### 2.3 半补就够、不补也行(3 项 🟡)

| 维度 | 现状 | 补不补 |
|---|---|---|
| 行为拟人化 | 固定 `pause_ms`,无随机抖动,`mouse.wheel(0, 1800)` 一次滚 1800px | 用户确认之前已经写过真人模拟,**不是这次事故主因**,优先级降 |
| 多账号池调度 | 基建在,scheduler 未写 | 单账号 + 限速够用,**先不补** |
| 封禁监控 / 降级 | 失败直接 RuntimeError | 现阶段人盯就行,**先不补** |

---

## 3. 路上探索的重要发现(本会话原创信息,值得记)

### 3.1 dev VPS 真实身份(我错认了 3 次才搞清)

| 维度 | 数据 |
|---|---|
| 公网 IP | `117.72.242.70` |
| 城市 | 北京朝阳 |
| ASN | **AS141679 CHINATELECOM-IDC-BTHBD-AP**(中国电信 京津冀大数据产业园 IDC) |
| ISP | **JDCOM**(京东) |
| 性质 | **数据中心 / IDC 机房** — 跑 XHS 会秒封 |

**陷阱:shell env 默认劫到 mihomo**

dev VPS shell 默认 export 了 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY` 全部指向 `http://127.0.0.1:7890`(mihomo)。所有"直连"的 curl 都被 env 偷偷送进 mihomo 当前选中的节点。检测 IP 时必须先 `unset HTTP_PROXY HTTPS_PROXY ALL_PROXY` 才能拿到真公网出口。

### 3.2 mihomo 台湾1 节点

| 维度 | 数据 |
|---|---|
| 入口 | `y2.wowodekuku.com` → `183.60.217.224`(深圳腾讯云) |
| 出口 IP | `1.161.52.206` |
| PTR | `1-161-52-206.dynamic-ip.hinet.net` |
| ASN | AS3462 HiNet 中华电信 — **真正的台湾家宽 ASN** |
| 用法 | 这个 IP 是机场出口,**跟其他付费用户共享**(不能跑量) |

**结论:走 mihomo 台湾1 → XHS 看到的就是"台湾家宽用户"。dev VPS 是不是 IDC XHS 看不见 — 它只看最后一跳 source IP。**

### 3.3 用户的前一次事故诊断

| 已知事实 | 排除 |
|---|---|
| 大陆家宽 IP 本机跑 | 不是 IP / 地理问题 |
| 已做人类行为模拟 | 不是滚动速度 / 间隔过短 |
| **账号被警告 → 封号** | 不是简单频次限流(否则只会 412 / 滑块) |
| **现在还能浏览** | 不是 IP 黑名单 → 账号 read-only 软封 |

**剩 1 个嫌疑**:**XHS 已经把当时的 Playwright Chromium 指纹关联到了这个 user_id**。再用同一账号 + 同一指纹刷 → 升级到警告 → 封号。

### 3.4 Playwright bundled Chromium 跟真 Chrome 的指纹差距

XHS 二层风控不看行为、看设备指纹。Playwright 即使关了 AutomationControlled 仍有 6-8 个细节:

| 指纹维度 | 真实 Chrome | Playwright Chromium | XHS 判断 |
|---|---|---|---|
| `navigator.plugins.length` | 通常 3-5 个 | 0 | 直接判 headless |
| Canvas toDataURL 哈希 | 跟 GPU 强相关,机器间各异 | **全宇宙 Playwright 同一哈希** | 致命 — 所有 Playwright 用户共享同一指纹 |
| `WebGLRenderingContext.getParameter(UNMASKED_RENDERER_WEBGL)` | "ANGLE (Intel UHD …)" | "Google Inc. (Google)" 或空 | 判机器 |
| Audio context fingerprint | 真实 GPU 加密 noise | 默认无 noise | 判 |
| `Notification.permission` vs `Permissions.query()` 一致性 | 一致 | 不一致 | 经典 headless tell |
| Function.toString 痕迹 | 完美 native | Playwright 注入痕迹 | timing 扫得到 |
| WebRTC STUN | 真实用户开着 | Playwright 默认关 / "0 candidates" | 间接判 |

### 3.5 账号一旦被警告就"中毒"

XHS 给账号打高风险标的逻辑是**单向递增**的:
- 警告后即使技术全修,**账号 risk_score 不会自动降回**
- "还能浏览" = read-only soft restriction,可能持续数周到数月
- 用这个号继续跑 → 第三次直接永封

→ **被警告的账号必须退役,不能继续用任何技术修补救**。

---

## 4. 落地计划(实际怎么做)

### 4.1 总体策略

**用户本机跑 + CDP attach 真 Chrome + playwright-stealth 兜底漏 + 新账号 + 限速。**

不做:
- ~~买住宅代理~~ — 用户本机大陆家宽 = 比任何商用住宅代理都好
- ~~XCrawl / Bright Data~~ — 数据要走第三方,合规 + 经济双不划算
- ~~Multilogin / AdsPower 指纹浏览器~~ — overkill,playwright-stealth 够用
- ~~恢复被警告的账号~~ — 救不了,换号

### 4.2 网络层 — 用户本机 + 大陆家宽

| 项 | 说明 |
|---|---|
| 出口 IP | 用户家里 WiFi 直连,中国三大运营商家宽 ASN(电信 / 联通 / 移动) |
| 地理 | 大陆,跟 XHS 主流用户分布吻合 |
| 关代理 / VPN | **完全关掉** — 跑爬虫期间不要挂任何 VPN / 加速器,确保 WebRTC IP = TCP 源 IP |
| 注意点 | 抓得太凶会牵连用户自己刷 XHS 的账号(同 IP) → 必须限速 |

### 4.3 浏览器层 — CDP attach 真 Chrome

**改造 crawler:**

`session.py` 里 `open_browser_session` 加一个分支 — 如果指定了 `--cdp-url`,走 `connect_over_cdp` 而不是 `launch_persistent_context`:

```python
# session.py 修改后大致样子
async def open_browser_session(
    profile: str = "default",
    headless: bool = False,
    cdp_url: str | None = None,   # 新参数
) -> BrowserSession:
    playwright = await async_playwright().start()
    if cdp_url:
        # CDP 模式 — 接已运行的真 Chrome
        browser = await playwright.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        return BrowserSession(...)
    # 否则走原来的 launch_persistent_context
    ...
```

`cli.py` 加 `--cdp-url` 透传选项,默认 `http://127.0.0.1:9222`。

**用户启 Chrome 方式(Windows 例):**

```powershell
# 关掉所有 Chrome 窗口
# PowerShell 起一个调试端口开着的 Chrome,User Data Dir 仍用日常的
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir="C:\Users\<your_name>\AppData\Local\Google\Chrome\User Data"
```

Mac:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/Library/Application Support/Google/Chrome"
```

启动后**正常用你的 Chrome 浏览 XHS、登录账号**。然后另开 terminal 跑:

```bash
xhs-crawler fetch "<note_url>" --cdp-url http://127.0.0.1:9222
```

Playwright 就接管这个 Chrome,canvas / WebGL / 字体 / `navigator.plugins` 全部是真的。

### 4.4 指纹补丁 — playwright-stealth

```bash
pip install playwright-stealth
```

在 `session.py` 拿到 `context` / `page` 后:

```python
from playwright_stealth import stealth_async
await stealth_async(page)   # 补 WebRTC / Notification / plugins / WebDriver / Function.toString
```

CDP 接真 Chrome 已经修好 90% 的洞,stealth 补的是即使真 Chrome 启用 remote-debugging 后泄的几个细节(`navigator.webdriver=true` 一类)。

### 4.5 账号层 — 退老号 / 用新号 / 长期养号

**短期(本周想继续跑):**

| 步骤 | 说明 |
|---|---|
| 1 | **被警告那个号永久退役** — 不再用于自动化任何操作。日常刷帖仍可,但用代码碰一次就完 |
| 2 | 用**你日常用的另一个 XHS 账号**(没碰过自动化的),先在 App 里**正常刷帖 1-2 天 +点赞 / 收藏 5-10 篇 / 评论 1-2 条**,让 XHS 把它当 "新设备登录的活跃老号" |
| 3 | 该号扫码登进新启的 Chrome(`--remote-debugging-port=9222` 那个),登录态留下来,然后才跑 crawler |

**长期(SAIF 试点持续跑):**

| 步骤 | 说明 |
|---|---|
| 1 | 注册 1-2 个新号专门当"爬虫账号" |
| 2 | **手动用 App 刷 2 周** — 浏览首页、点赞 30+ 篇、收藏 10+、关注 5 个用户、发 1-2 条评论 |
| 3 | 累计够 trust score 后再开自动化,从 ≤30 篇/天 起步 |

### 4.6 节奏控制

| 项 | 数值 |
|---|---|
| **首周日上限** | **≤ 30 篇**(诱导 XHS 把账号当低频用户) |
| 单次连续抓取量 | ≤ 10 篇,然后停 30 分钟 |
| 请求间隔 | 5-15 秒随机(crawler `--pause-ms` 改成接受 range,或者前端把 1500ms 改 base + jitter) |
| 评论展开 max_scroll_rounds | 默认 40 太多,实测改 15-20 已够 |
| 子评论 | 第一周**不抓**子评论(reduce request rate),只抓一级 |
| 错峰 | **不要凌晨 3-5 点跑** — 真人不在这时段刷,XHS 异常检测会盯;建议白天 10-12 / 14-18 时段 |

### 4.7 风险信号识别

跑期间**每次抓完检查这些**:

| 信号 | 严重度 | 应对 |
|---|---|---|
| API 返回 `success=false` + code=10000 ~ 10004 | 🔴 账号已被限流 | 立刻停 24h,换账号 |
| 抓到帖子但 `note_card` 缺关键字段(`title=""`、`desc=""`) | 🟡 内容降级返回(部分风控) | 降低频率 |
| 弹滑块 / 验证码页面(`captcha` 字样) | 🔴 IP / 设备风控 | 当天停 |
| App 端账号收到"异常登录"通知 | 🟡 设备级监控触发 | 检查 Chrome 是否 cookie 异常 |
| App 端账号收到警告私信 | 🔴 已被打 risk tag | **永久退役该号**,不再修补 |

---

## 5. Step-by-step setup(用户本机)

### 5.1 一次性环境

| 步骤 | Windows | Mac |
|---|---|---|
| 1. Python | Python 3.11+(`python --version` 验) | 同 |
| 2. clone repo + crawler 包 | `git clone <repo>` → `cd tools/xhs_post_comment_crawler` → `pip install -e .` | 同 |
| 3. Playwright Chromium(**不会真用,只为 stealth 兼容**) | `python -m playwright install chromium` | 同 |
| 4. stealth 补丁 | `pip install playwright-stealth` | 同 |
| 5. 找日常 Chrome 路径 | `C:\Program Files\Google\Chrome\Application\chrome.exe` | `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome` |
| 6. 找日常 user-data-dir | `C:\Users\<you>\AppData\Local\Google\Chrome\User Data` | `~/Library/Application Support/Google/Chrome` |

### 5.2 每次跑爬虫之前

1. **关掉所有 Chrome 窗口**(必须 — `--remote-debugging-port` 只能在新启时设)
2. PowerShell / Terminal 启 Chrome:
   ```powershell
   & "C:\Program Files\Google\Chrome\Application\chrome.exe" `
     --remote-debugging-port=9222 `
     --user-data-dir="C:\Users\<your_name>\AppData\Local\Google\Chrome\User Data"
   ```
3. 在这个 Chrome 里正常浏览 1-2 分钟(给 cookie / 行为信号热身)
4. 确认登录的是 **目标 XHS 账号**(不是被警告那个)
5. 另开 terminal 跑 crawler:
   ```bash
   xhs-crawler search-fetch "求职 高金" \
     --cdp-url http://127.0.0.1:9222 \
     --max-notes 20 \
     --min-likes 50 \
     --pause-ms 8000
   ```

### 5.3 输出处理

抓完默认落 `D:\xhs_post_comment_crawler\output\<...>\` 或 `~/xhs_post_comment_crawler/output/<...>/`:
- `notes.csv` / `comments.csv` — 清洗后表格
- `analysis.json` / `report.md` — 摘要
- `notes/<note_id>/` — 每帖原始 JSON

**上传到 dev VPS**(给 backend 的 pass1/2/3 处理):

```bash
scp -r output/<this_run_dir> myvps:/home/ubuntu/opencode-worktrees/jobrador-edit/backend/data/xhs/raw/
```

或者 git 提交结构化输出,VPS pull(数据小的话)。

dev VPS 上的 backend **不直接爬**,只跑 LLM pipeline:
- `pass1_consolidate.py`
- `pass2_extract.py`
- `pass3_dedup.py`

---

## 6. 还没解决的问题(open questions)

| # | 问题 | 影响 | 怎么处理 |
|---|---|---|---|
| 1 | 现有 crawler 的 `client.py` / `signer.py` 是在 `launch_persistent_context` 模式下逆出的签名,**CDP attach 真 Chrome 后签名算法是否仍 work 未实测** | 可能 X-s 拒签 | 第一次跑时优先用 `XhsPageCrawler`(监听响应)路径,**不走 `XhsApiCrawler`** 路径,等验证再迁 |
| 2 | playwright-stealth 跟 CDP attach 真 Chrome 是否有冲突 | 不确定 | 先无 stealth 跑一次看是否触发风控,再叠加 stealth 看是否变好 |
| 3 | "中毒账号"具体状态(只是 read-only,还是更严) | 决定是否完全弃用 | 用户自查:能不能正常发评论 / 发帖 / 私信 — 不行 = 完全弃用 |
| 4 | XHS 反爬是否能跨账号关联同设备指纹 | 决定换账号是否真的有用 | 假设能(保守),所以**换账号 + 换浏览器(从 Playwright Chromium 切到真 Chrome)同时做** |
| 5 | 大陆三大运营商家宽 IP 跟 SAIF 试点学生用的 IP 重叠度 | 影响是否会拉黑 SAIF 学生用户 | 跑爬虫的家宽线 ≠ SAIF 学生宿舍 / 学校 IP,理论无关 |

---

## 7. 文件 / 代码改动清单(交接前 to-do)

待 ship(本会话还**没**写代码,只产出本文档):

| 文件 | 改动 | 估时 |
|---|---|---|
| `tools/xhs_post_comment_crawler/src/xhs_post_comment_crawler/session.py` | `open_browser_session` 加 `cdp_url` 参数分支 | 15 min |
| `tools/xhs_post_comment_crawler/src/xhs_post_comment_crawler/cli.py` | 各命令 `--cdp-url` 透传 | 10 min |
| 同上 | `from playwright_stealth import stealth_async` + 在 page 创建后 `await stealth_async(page)` | 10 min |
| `tools/xhs_post_comment_crawler/pyproject.toml` | 加 `playwright-stealth` 到 dependencies | 2 min |
| `tools/xhs_post_comment_crawler/README.md` | 加一节"CDP attach 模式使用步骤"(链回本文档) | 10 min |
| `tools/xhs_post_comment_crawler/src/xhs_post_comment_crawler/crawler.py` | `--pause-ms` 支持 range(e.g. `5000-15000` 随机) | 20 min |

**估总:**~1.5 小时代码改动。

---

## 8. 决策表(以后再有人问起,直接看这里)

| 问题 | 决定 | 时间 | 依据 |
|---|---|---|---|
| 跑哪台机器 | 用户本机 | 2026-05-22 | 大陆家宽 IP > dev VPS 京东云 IDC > mihomo 共享台湾家宽 |
| 用什么浏览器 | CDP attach 真 Chrome | 2026-05-22 | Playwright bundled Chromium canvas 哈希全宇宙共享,XHS 二层风控直接识别 |
| 是否买住宅代理 | 否 | 2026-05-22 | 用户本机大陆家宽天然就是住宅;dev VPS 上不直接爬 |
| 是否上 XCrawl | 否 | 2026-05-22 | 数据合规风险 + 经济不划算(签名 / 登录态我们自有);仅作为 fallback 留档 |
| 是否上 Multilogin / AdsPower | 否 | 2026-05-22 | overkill;playwright-stealth + CDP attach 真 Chrome 已覆盖 |
| 被警告账号怎么办 | 永久退役 | 2026-05-22 | XHS risk_score 单向递增,救不了 |
| 多账号池 | 暂不做 | 2026-05-22 | 单账号 ≤30 篇/天够 SAIF 试点用量,基建已在 |
| 子评论抓不抓 | 首周不抓 | 2026-05-22 | 降 request rate,等账号稳定后再开 |

---

## 9. 给下一会话 Claude / 接手人

读这份文档前**不需要**读:
- ~~`opencode_handoff_20260329.md`~~ — 早期,已过时
- ~~`xhs-knowledge-supplement-plan-2026-05-19.md`~~ — 计划阶段文档,不含本会话发现

读这份文档后,如果用户提到:
- "再跑一次 xhs" → 按本文 §5.2 流程
- "账号又被警告了" → 按本文 §4.7 风险信号 + §4.5 退役流程
- "想接住宅代理 / XCrawl" → 看 §8 决策表,我们已经讨论过否掉的理由
- "改 crawler 代码" → 看 §7 to-do 还有哪些没改

> 本会话有 3 次错误推断的纠正过程(我之前以为 dev VPS 是 HiNet 家宽 → 共享 NAT → 京东云 IDC),最终结论以 §3.1 为准。

