# Frontend (admin app)

JobRadar 内部 admin —— Vite + React 19 + TS + AntD 6 + axios + react-router-dom 7 + vitest。**不是用户向公开站**（那是 `resume-copilot-web/` 的 Next.js:3001）。两个前端**不同时跑**，共享 backend:8000 proxy。

## 启动
- `npm run dev` — vite 0.0.0.0:5173，`/api` → `http://localhost:8000`（`VITE_API_PROXY_TARGET` 可覆盖）
- `npm run lint` — eslint flat config（`eslint.config.js`）
- `npm run build` — `tsc -b && vite build`，改动必须过
- `npm test` — vitest + jsdom，setup `src/test/setup.ts`

## 路由 / 页面（全在 `AppLayout` 内；未登录走 `/login`，session 在 `auth/mockSession.ts`）
- `/` `Jobs.tsx` — 岗位主表 + stats + CSV import/export（AntD 重度）
- `/company-expand` `CompanyExpand.tsx` — 单公司岗位铺开 + 手动 recrawl
- `/job-intel/:jobId` `JobIntel.tsx` — 单岗 LLM intel 详情
- `/tracks` `Tracks.tsx` — track / group / 关键词 CRUD
- `/scoring` `Scoring.tsx` — 评分配置；`/exclude` `Exclude.tsx` — 排除规则
- `/crawl` `Crawl.tsx` — 手动触发爬虫；`/scheduler` `Scheduler.tsx` — APScheduler 状态
- `/sites` `Sites.tsx` *(HiFi)* — 站点健康 + teacher-entry 草稿
- `/coverage` `Coverage.tsx` *(HiFi)* — track 覆盖星图（`CoverageStarmap`）
- `/review-queue` `ReviewQueue.tsx` *(HiFi)*；`/system-health` `SystemHealth.tsx` *(HiFi)*
- `/login` `Login.tsx` — mock session 登录

## 目录
`src/api/index.ts` 统一 axios · `src/components/{sites,intel}/` + `CoverageStarmap.tsx` · `src/pages/` · `src/styles/{hifi-tokens,sites,coverage,review,health}-theme.css` · `src/auth/mockSession.ts` · `src/utils/time.ts` · `src/test/setup.ts`

## 硬契约
- **HTTP 全走 `src/api/index.ts`** 的 `api` 实例（baseURL `/api`，timeout 60s；teacher-entry admin 写口自动注入 `X-Admin-Token`）。禁止页面裸 `fetch`/裸 `axios`。
- **HiFi 页（`/sites` `/coverage` `/review-queue` `/system-health`）一律 `[data-theme="<page>"]` scope，不用 AntD**。新 HiFi 页照 `sites-theme.css` / `coverage-theme.css` 抄。
- 普通 admin 页**可以**用 AntD —— `main.tsx` 已套 `ConfigProvider locale=zhCN`。
- **`.border-beam` 必须是 `position: relative` 父元素的最后一个 child**（详见 root CLAUDE.md），不然 paint order 错。
- `frontend` 和 `resume-copilot-web` 共享 backend:8000，**别同时 `npm run dev`**。

## 测试
vitest + `@testing-library/react`，文件名 `*.test.tsx` / `*.test.ts`，紧挨被测文件（`Jobs.test.tsx` / `AppRoutes.test.tsx` / `auth/mockSession.test.ts`）。

## Footguns
- `AppRoutes` 用 `RequirePreviewSession` 包住除 `/login` 外所有路由；新页**别绕过** `AppLayout`，否则没 session 守卫也没侧栏。
- `/api/teacher-entry/admin/*` 必须带 admin token —— interceptor 自动注入，但前提是 `getAdminToken()` 有值（走完 `Login` admin 流程后才有）。
