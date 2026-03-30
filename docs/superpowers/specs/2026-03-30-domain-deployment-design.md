# jobcopilot.top 域名部署设计

## 目标
将 JobRadar 前后端从本地开发端口迁移到自定义域名，支持 HTTPS，生产级部署。

## 域名规划
| 域名 | 用途 | 后端 |
|------|------|------|
| `jobcopilot.top` | 前端静态文件 | Nginx serve `frontend/dist/` |
| `api.jobcopilot.top` | 后端 API | Nginx proxy → `127.0.0.1:8000` |

## 前置条件
- DNS：`@` 和 `api` 两条 A 记录指向 VPS 公网 IP（用户手动操作）
- Nginx 已安装
- 前后端代码在 `/home/ubuntu/opencode-worktrees/jobrador-edit/`

## 架构
```
用户 → Nginx (443 SSL)
        ├── jobcopilot.top       → frontend/dist/ (静态文件)
        └── api.jobcopilot.top   → proxy_pass 127.0.0.1:8000 (uvicorn)
```

## 组件

### 1. 前端构建
- 命令：`cd frontend && npm run build`
- 产物：`frontend/dist/`
- Nginx 直接 serve 静态文件
- SPA 路由：所有非文件请求回退到 `index.html`

### 2. 后端服务
- 运行方式：systemd 管理 uvicorn
- 监听：`127.0.0.1:8000`
- Service 文件：`/etc/systemd/system/jobradar-backend.service`
- 工作目录：`/home/ubuntu/opencode-worktrees/jobrador-edit/backend`
- venv：`backend/.venv`

### 3. Nginx 配置
- 前端：`/etc/nginx/sites-available/jobcopilot.top`
- 后端：`/etc/nginx/sites-available/api.jobcopilot.top`
- 两个站点启用 symlink 到 `sites-enabled/`
- HTTP 80 自动重定向到 HTTPS 443

### 4. HTTPS 证书
- 工具：Certbot + Let's Encrypt
- 命令：`sudo certbot --nginx -d jobcopilot.top -d api.jobcopilot.top`
- 自动续期：certbot.timer

### 5. systemd 后端服务
- 服务名：`jobradar-backend`
- 用户：ubuntu
- 自动重启：on-failure
- 日志：journalctl -u jobradar-backend

## 实施步骤概要
1. DNS 添加 A 记录（用户操作）
2. 前端 build
3. 创建 Nginx 配置文件（前端 + 后端）
4. 测试 Nginx 配置并 reload
5. 创建 systemd service 文件
6. 启动后端服务
7. Certbot 申请 SSL 证书
8. 验证全链路

## 验证
- `https://jobcopilot.top` → 前端页面正常渲染
- `https://api.jobcopilot.top/docs` → Swagger 文档正常
- `https://api.jobcopilot.top/api/health` → `{"status":"ok"}`
- 前端页面的 API 调用正常（CORS 配置）

## 注意事项
- CORS：后端需允许 `https://jobcopilot.top` 来源
- 前端 API 基础 URL 需改为 `https://api.jobcopilot.top`
- 数据库路径使用绝对路径或相对于 backend/ 的路径
- 代理设置：后端不再需要代理（除非爬虫需要）
