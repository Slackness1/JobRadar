# tata_jobs_export - tatawangshen.com 岗位爬虫

爬取 https://www.tatawangshen.com 的 VIP/专属岗位表格，导出为 CSV。

## Web 管理界面（Docker）

### 默认模式（热更新）

```bash
docker compose up --build -d
```

- 前端地址：`http://localhost:5173`
- 后端 API 地址：`http://localhost:8001`
- 修改 `frontend/src` 或 `backend/app` 代码会自动生效（HMR / reload）

### 仅在需要时创建新容器（隔离一套）

```bash
DB_VOLUME_NAME=jobscraper_alt_db docker compose -p jobscraper-alt up --build -d
```

PowerShell:

```powershell
$env:DB_VOLUME_NAME = "jobscraper_alt_db"
docker compose -p jobscraper-alt up --build -d
```

- 不写 `-p` 时默认复用当前这套容器
- 默认数据库卷名是 `jobscraper_db-data`

### 说明

- 岗位总览的筛选保存是浏览器本地存储（localStorage），不会自动跨设备同步。

## 安装依赖

```bash
pip install requests
pip install playwright
playwright install chromium
```

## 运行方式

### 方式一：自动登录（推荐）

使用 Playwright 自动登录并抓取，无需手动获取 Token。

**1. 设置账号密码环境变量**

PowerShell:
```powershell
$env:TATA_USERNAME = "你的账号"
$env:TATA_PASSWORD = "你的密码"
```

**2. 运行脚本**
```bash
python auto_login_scraper.py
```

**3. 调试模式（如登录失败）**
```bash
python auto_login_scraper.py --show-browser
```

### 方式二：手动获取 Token

**1. 获取 Token**
1. 打开 Chrome，访问 https://www.tatawangshen.com 并登录
2. 按 `F12` 打开开发者工具
3. 切换到 **Application** 标签页
4. 左侧展开 **Local Storage** → 点击 `https://www.tatawangshen.com`
5. 找到 `token` 这一行，复制其值（一长串 JWT）

**2. 获取 position_export_config_id**
1. 在页面上打开 **VIP/专属岗位** 表格
2. 按 `F12` 打开开发者工具 → **Network** 标签页
3. 刷新页面，找到 `exclusive` 请求
4. 右键 → **Copy** → **Copy as cURL**
5. 在复制的内容里找到 `"position_export_config_id": "xxx"`，复制那个 ID 值

**3. 运行**

PowerShell:
```powershell
$env:TATA_TOKEN = "你的token值"
$env:TATA_EXPORT_CONFIG_ID = "你的config_id"
python tata_jobs_export.py --out jobs.csv --max-pages 20
```

同一个 config 下抓取 4 个分支（你的场景）：

```powershell
$env:TATA_EXPORT_CONFIG_ID = "687d079c70ccc5e36315f4ba"
$env:TATA_EXPORT_SHEET_INDEXES = "0,1,2,3"
$env:TATA_INTERNSHIP_SHEET_INDEXES = "2,3"
$env:HAITOU_MAX_PAGES = "16"
python tata_jobs_export.py --out jobs.csv --max-pages 20
```

- 你复制的 `export_config` 里 `sheet_index` 为 0/1/2/3，就填到 `TATA_EXPORT_SHEET_INDEXES`。
- `TATA_INTERNSHIP_SHEET_INDEXES=2,3` 表示第 3/4 个 sheet 归为实习。
- Web 管理端 `立即爬取` 现在会同时抓取 Tata + 鱼泡直聘校招（Haitou）。
- 前端可在「排除规则」页控制“仅展示 2026-02-01 后岗位”开关（默认开启）。

## 命令行参数

### auto_login_scraper.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--show-browser` | False | 显示浏览器窗口（调试登录问题） |
| `--max-pages` | 100 | 最大抓取页数 |
| `--page-size` | 50 | 每页记录数 |
| `--config-id` | 默认 | position_export_config_id |
| `--config-ids` | "" | 多个 position_export_config_id（逗号分隔） |
| `--sheet-indexes` | "" | 多个 sheet_index（逗号分隔） |

### tata_jobs_export.py

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--out` | jobs.csv | 输出 CSV 文件 |
| `--page-size` | 50 | 每页记录数 |
| `--max-pages` | 100 | 最大抓取页数 |
| `--sleep-min` | 0.5 | 请求间隔最小秒数 |
| `--sleep-max` | 1.5 | 请求间隔最大秒数 |
| `--job-title` | "" | 按岗位名称筛选 |
| `--config-id` | "" | position_export_config_id |
| `--config-ids` | "" | 多个 position_export_config_id（逗号分隔） |
| `--sheet-indexes` | "" | 多个 sheet_index（逗号分隔） |
| `--token` | "" | API Token（或使用环境变量） |
| `--dry-run` | False | 只抓第一页并打印字段名 |

## 新增环境变量

| 变量名 | 说明 |
|--------|------|
| `HAITOU_MAX_PAGES` | 鱼泡校招列表最大抓取页数（默认 16） |

## 输出字段

| 字段 | 说明 |
|------|------|
| job_id | 岗位 ID |
| company | 公司简称 |
| company_type_industry | 公司性质/行业 |
| company_tags | 公司标签 |
| department | 下级公司/部门 |
| job_title | 岗位名称 |
| location | 工作地点 |
| major_req | 专业要求 |
| job_req | 岗位要求 |
| job_duty | 岗位职责 |
| referral_code | 内推码 |
| publish_date | 发布时间 |
| deadline | 截止时间 |
| detail_url | 岗位详情链接 |
| apply_url | 投递链接 |
| job_stage | 岗位类型（campus/internship/both） |
| source_config_id | 来源配置 ID |
| scraped_at | 抓取时间 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `auto_login_scraper.py` | **自动登录脚本**（推荐） |
| `filter_jobs.py` | **岗位筛选器**（按类别+日期筛选） |
| `tata_jobs_export.py` | 手动 Token 脚本 |
| `format_csv.py` | 格式化 CSV（调整列顺序、列名） |
| `jobs.csv` | 抓取的全量数据 |
| `filtered_jobs.csv` | 筛选后的目标岗位 |
## 常见问题

### 401 Unauthorized
Token 已过期，需要重新登录获取新 token。

### 429 Too Many Requests
请求频率过高，脚本会自动重试。可以增加 `--sleep-min` 和 `--sleep-max`。

### 登录失败
1. 使用 `--show-browser` 查看登录过程
2. 检查账号密码是否正确
3. 检查登录页面结构是否变化

### apply_url 和 referral_code 为空
当前 API 返回**不包含**这两个字段，如需获取，需要分析"去投递"按钮的 URL 规律。

## 字段映射

| CSV 字段 | API 字段 |
|----------|----------|
| job_id | position_id |
| company | company_alias |
| company_type_industry | org_type + industry |
| company_tags | tags |
| department | company_name |
| job_title | job_title |
| location | address_str |
| major_req | major_str |
| job_req | raw_position_require |
| job_duty | responsibility |
| publish_date | publish_date |
| deadline | expire_date |
| detail_url | position_web_url |

---

## 每日工作流（推荐）

### 1. 抓取最新数据
```bash
# PowerShell
$env:TATA_USERNAME = "你的账号"
$env:TATA_PASSWORD = "你的密码"
python auto_login_scraper.py --max-pages 100
```

### 2. 筛选目标岗位
```bash
# 筛选最近3天的目标岗位
python filter_jobs.py --days 3

# 或者筛选最近7天
python filter_jobs.py --days 7
```

### 3. 查看筛选结果
```bash
# 结果保存在 filtered_jobs.csv
# 包含以下筛选类别：
# - 数据挖掘/数据分析
# - 投研
# - AI产品经理
# - 咨询
```

---

## filter_jobs.py - 岗位筛选器

根据目标岗位类型和日期筛选岗位。

### 使用方法
```bash
# 默认筛选最近3天
python filter_jobs.py

# 自定义天数
python filter_jobs.py --days 7

# 指定输入输出文件
python filter_jobs.py --input jobs.csv --output my_filtered.csv --days 3
```

### 筛选类别
| 类别 | 关键词示例 |
|------|----------|
| 数据挖掘/数据分析 | 数据分析, 数据挖掘, 数据科学, 算法工程师, 机器学习, 量化分析, 商业分析 |
| 投研 | 投研, 行业研究, 证券分析师, 投资分析, 基金经理, 金融工程 |
| AI产品经理 | AI产品, 产品经理, 算法产品, 大模型产品, AIGC |
| 咨询 | 咨询, 顾问, 管理咨询, 战略咨询, 数字化转型, 售前 |

### 输出字段
筛选后的 CSV 文件包含额外字段：
- `matched_categories` - 匹配的岗位类别
- `matched_keywords` - 匹配的关键词
- `match_score` - 匹配分数（关键词数量）

### 自定义筛选条件
编辑 `filter_jobs.py` 中的配置：
```python
# 目标岗位关键词
TARGET_KEYWORDS = {
    "数据挖掘/数据分析": [...],
    "投研": [...],
    ...
}

# 排除关键词（不想要的岗位）
EXCLUDE_KEYWORDS = [...]
```
