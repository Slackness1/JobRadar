# jobcopilot.top 域名部署实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 JobRadar 前后端部署到 jobcopilot.top 域名，支持 HTTPS。

**Architecture:** Nginx 反向代理，前端静态文件 + 后端 uvicorn systemd 服务，Let's Encrypt SSL。

**Tech Stack:** Nginx / Certbot / systemd / Vite build / uvicorn

---

### Task 0: 确认前置条件

- [ ] **Step 1: 获取 VPS 公网 IP**

```bash
curl -s ifconfig.me
```

Expected: 一个公网 IP 地址

- [ ] **Step 2: 检查 Nginx 版本**

```bash
nginx -v 2>&1
```

Expected: nginx version 输出

- [ ] **Step 3: 检查 Certbot 是否已安装**

```bash
certbot --version 2>&1
```

Expected: certbot 版本号。如果未安装：`sudo apt update && sudo apt install -y certbot python3-certbot-nginx`

- [ ] **Step 4: 提示用户配置 DNS**

告诉用户：在你的域名 DNS 管理面板添加两条 A 记录：
- `@` → `<VPS IP>`
- `api` → `<VPS IP>`

然后等待用户确认 DNS 已配置。

- [ ] **Step 5: 验证 DNS 解析**

```bash
dig +short jobcopilot.top A
dig +short api.jobcopilot.top A
```

Expected: 两条都返回 VPS 公网 IP。如果未生效，等待 DNS 传播（通常几分钟到几小时）。

---

### Task 1: 构建前端

**Files:**
- Build output: `frontend/dist/`

- [ ] **Step 1: 构建前端**

```bash
cd /home/ubuntu/opencode-worktrees/jobrador-edit/frontend
npm run build
```

Expected: `dist/` 目录生成，无报错

- [ ] **Step 2: 确认产物存在**

```bash
ls /home/ubuntu/opencode-worktrees/jobrador-edit/frontend/dist/index.html
```

Expected: 文件存在

- [ ] **Step 3: 检查前端 API 配置**

读取 `frontend/src/api/index.ts` 或相关文件，确认前端 API 请求的 baseURL 配置方式。如果硬编码了 `localhost:8000`，需要修改为 `https://api.jobcopilot.top`。如果使用环境变量 `VITE_API_BASE_URL`，在 build 前设置。

修改方式取决于实际代码。典型修改：

```typescript
// 查找 baseURL 配置，改为：
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'
```

或者在 vite.config.ts 中确保 proxy 仅用于开发，生产环境通过 Nginx 处理。

- [ ] **Step 4: 重新构建（如果修改了 API 配置）**

```bash
cd /home/ubuntu/opencode-worktrees/jobrador-edit/frontend
VITE_API_BASE_URL=https://api.jobcopilot.top npm run build
```

- [ ] **Step 5: 确认构建成功**

```bash
ls -la /home/ubuntu/opencode-worktrees/jobrador-edit/frontend/dist/
```

Expected: index.html 和 assets/ 目录存在

---

### Task 2: 配置后端 CORS

**Files:**
- Modify: `backend/app/main.py`（或 CORS 配置所在文件）

- [ ] **Step 1: 找到 CORS 配置**

```bash
grep -rn "CORS\|cors\|CORSMiddleware" /home/ubuntu/opencode-worktrees/jobrador-edit/backend/app/ --include="*.py"
```

- [ ] **Step 2: 更新 CORS 允许来源**

确保 CORS 配置包含 `https://jobcopilot.top`。典型修改：

```python
# 找到 add_middleware(CORSMiddleware, ...) 部分
# 确保 allow_origins 包含：
allow_origins=[
    "https://jobcopilot.top",
    "http://localhost:5173",  # 保留开发环境
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "*"  # 或直接用 * 允许所有
]
```

- [ ] **Step 3: 确认 .env 中 DATABASE_URL 使用正确路径**

```bash
cat /home/ubuntu/opencode-worktrees/jobrador-edit/.env | grep DATABASE_URL
```

确保数据库路径是绝对路径或能正确解析。

---

### Task 3: 创建 Nginx 前端配置

**Files:**
- Create: `/etc/nginx/sites-available/jobcopilot.top`

- [ ] **Step 1: 创建配置文件**

```bash
sudo tee /etc/nginx/sites-available/jobcopilot.top > /dev/null << 'EOF'
# Frontend - jobcopilot.top
server {
    listen 80;
    listen [::]:80;
    server_name jobcopilot.top;

    root /home/ubuntu/opencode-worktrees/jobrador-edit/frontend/dist;
    index index.html;

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Static assets caching
    location /assets/ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
}
EOF
```

- [ ] **Step 2: 启用站点**

```bash
sudo ln -sf /etc/nginx/sites-available/jobcopilot.top /etc/nginx/sites-enabled/
```

- [ ] **Step 3: 测试 Nginx 配置**

```bash
sudo nginx -t
```

Expected: `syntax is ok` + `test is successful`

---

### Task 4: 创建 Nginx 后端配置

**Files:**
- Create: `/etc/nginx/sites-available/api.jobcopilot.top`

- [ ] **Step 1: 创建配置文件**

```bash
sudo tee /etc/nginx/sites-available/api.jobcopilot.top > /dev/null << 'EOF'
# Backend API - api.jobcopilot.top
server {
    listen 80;
    listen [::]:80;
    server_name api.jobcopilot.top;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
EOF
```

- [ ] **Step 2: 启用站点**

```bash
sudo ln -sf /etc/nginx/sites-available/api.jobcopilot.top /etc/nginx/sites-enabled/
```

- [ ] **Step 3: 测试并重载 Nginx**

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Expected: `syntax is ok` + `test is successful` + reload 成功

- [ ] **Step 4: 验证 HTTP 可访问**

```bash
curl -s http://jobcopilot.top/ | head -5
curl -s http://api.jobcopilot.top/api/health
```

Expected: 前端返回 HTML，后端返回 `{"status":"ok"}`

---

### Task 5: 创建 systemd 后端服务

**Files:**
- Create: `/etc/systemd/system/jobradar-backend.service`

- [ ] **Step 1: 创建 service 文件**

```bash
sudo tee /etc/systemd/system/jobradar-backend.service > /dev/null << 'EOF'
[Unit]
Description=JobRadar Backend (uvicorn)
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/opencode-worktrees/jobrador-edit/backend
ExecStart=/home/ubuntu/opencode-worktrees/jobrador-edit/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
```

- [ ] **Step 2: 先停掉手动启动的后端进程**

```bash
pkill -f "uvicorn app.main:app.*8010" 2>/dev/null; pkill -f "uvicorn app.main:app.*8000" 2>/dev/null; echo "stopped"
```

- [ ] **Step 3: 启用并启动服务**

```bash
sudo systemctl daemon-reload && sudo systemctl enable jobradar-backend && sudo systemctl start jobradar-backend
```

- [ ] **Step 4: 检查服务状态**

```bash
sudo systemctl status jobradar-backend --no-pager
```

Expected: `active (running)`

- [ ] **Step 5: 验证后端响应**

```bash
curl -s http://127.0.0.1:8000/api/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 6: 验证通过 Nginx 代理访问**

```bash
curl -s http://api.jobcopilot.top/api/health
```

Expected: `{"status":"ok"}`

---

### Task 6: 配置 HTTPS 证书

- [ ] **Step 1: 确认 HTTP 访问正常**

```bash
curl -s http://jobcopilot.top/ | head -3 && curl -s http://api.jobcopilot.top/api/health
```

Expected: 前端 HTML + 后端 health OK

- [ ] **Step 2: 申请 Let's Encrypt 证书**

```bash
sudo certbot --nginx -d jobcopilot.top -d api.jobcopilot.top --non-interactive --agree-tos --email admin@jobcopilot.top
```

Expected: 证书申请成功，Nginx 自动配置 SSL

- [ ] **Step 3: 验证 HTTPS**

```bash
curl -s https://jobcopilot.top/ | head -3 && curl -s https://api.jobcopilot.top/api/health
```

Expected: 前端 HTML + 后端 health OK，且通过 HTTPS

- [ ] **Step 4: 验证 HTTP 重定向到 HTTPS**

```bash
curl -sI http://jobcopilot.top/ | head -5
```

Expected: 301 或 302 重定向到 `https://`

- [ ] **Step 5: 确认自动续期**

```bash
sudo certbot renew --dry-run
```

Expected: 续期模拟成功

---

### Task 7: 最终验证

- [ ] **Step 1: 验证前端页面**

```bash
curl -s https://jobcopilot.top/ | grep "JobRadar"
```

Expected: 包含 JobRadar 标题

- [ ] **Step 2: 验证后端 API**

```bash
curl -s https://api.jobcopilot.top/api/health && curl -s https://api.jobcopilot.top/docs | head -3
```

Expected: health OK + Swagger 文档页面

- [ ] **Step 3: 验证系统服务状态**

```bash
sudo systemctl status jobradar-backend --no-pager -l | head -15
```

Expected: active (running)

- [ ] **Step 4: 保存部署信息到项目**

创建 `docs/superpowers/specs/2026-03-30-domain-deployment-design.md` 中记录实际部署结果，或更新 OPENCODE_START.md 添加生产 URL。
