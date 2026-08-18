# 语音面试验收 Runbook（四关 · 可执行版）

> 对应规划文档 [voice-agent-acceptance-2026-08-16.md](./voice-agent-acceptance-2026-08-16.md) 与
> [voice-agent-phase-retrospective-and-acceptance-2026-08-16.md](./voice-agent-phase-retrospective-and-acceptance-2026-08-16.md)。
> 那两份写的是"应该验什么"，这份写的是"谁在哪天、敲哪条命令、拿什么判"。
>
> 原方案要求 20 位说话人 / 100 段录音 / 两人交叉标注，以当前人力过不去。这里压缩成
> 可执行版本，**但没有降低可证伪的要求**：每一关都写死了通过线和不通过时的降级动作，
> 方案里不存在"想办法让它过"这个选项。

- 日历时间：4 天（不必连续）
- 人力：约 2.5 人日 + 1 个晚上的机器时间
- 现金成本：0（Gate 3 先自建，达标后再谈买云服务）
- 证据目录：`eval-runs/voice-acceptance-<YYYY-MM-DD>/gate{1,2,3,4}/`
  （项目规矩：评测产物留在 `eval-runs/`，不要放 `/tmp`）

---

## 关卡总览

| 关 | 证明什么 | 谁做 | 成本 | 不通过时的降级动作 |
| --- | --- | --- | --- | --- |
| 1 自动检查 | 没坏、且测试有杀伤力 | 开发 | 半天 | 停止，不启动后三关 |
| 2 真人语料 | 时间类指标量得准 | 产品 + 2 位同学 | 1–2 天 | 锁死手动提交，automatic 保持关闭 |
| 3 真实通话 | 实时体验达标 | 开发 | 1 晚 | 保持旧链路上线，不买云服务 |
| 4 老师盲评 | 对学院真的更有用 | 产品 + 1 位老师 | 2 场面试 | 改内容与提示词，不改代码 |

前三关证明的是"没坏"，第四关证明的是"更好"。

---

## Gate 1 · 自己能跑的自动检查

**前置**：分支 checkout、`backend/.venv` 就绪、`backend/.env.local` 存在。

**命令**

```bash
cd backend

# 红线 A —— 冒用他人身份取录音必须失败
PYTHONPATH=. .venv/bin/pytest -q tests/test_interview_audio_authz.py

# 红线 B —— 连跑 20 轮不允许出现一次指标丢失
for i in $(seq 1 20); do
  PYTHONPATH=. .venv/bin/pytest -q \
    tests/test_interview_orchestrator.py tests/test_interview_turn_write_contention.py \
    || echo "ROUND $i FAILED"
done

# 声学 fixture go/no-go（checksum 固定的 7 个样本）
PYTHONPATH=. .venv/bin/python scripts/evaluate_voice_intelligence.py

# 迁移必须是单一 head
PYTHONPATH=. .venv/bin/alembic heads

cd ../resume-copilot-web && npx tsc --noEmit && npm run lint && npm run build
```

**这一关的灵魂是控制实验，不是跑绿。** 把 `backend/app/routers/_session_identity.py`
里 `resolve_user_key` 的函数体临时替换成 `return (x_resume_user_key or "").strip()`
（旧行为），重跑越权测试，确认**它真的会挂**，然后恢复。记录里写清"退回后 N 条失败 /
恢复后 N 条通过"——否则"测试全绿"什么也证明不了。

**通过线**

| 检查 | 通过线 |
| --- | --- |
| 越权（读取/回放/删除他人录音、借用他人 key、过期令牌） | 全部拒绝，且冒名删除后**物理文件仍在** |
| 20 轮确定性 | 0 轮失败 |
| 声学 fixture | `status: go`，7 例，处理 RTF p95 < 0.5 |
| Alembic | 单一 head |
| 前端 | tsc 通过 / lint 0 errors / production build 通过 |

**产出**：`eval-runs/voice-acceptance-<date>/gate1/` 下原始 log + `result.md`（一行结论 + 控制实验记录）。

**不通过**：当天修，整关重跑。后三关不启动。

---

## Gate 2 · 真人语料校准

### 录之前先定死三件事

1. **设备必须分开**：3 个人分别用 MacBook 内置麦 / 蓝牙耳机 / 手机。
   不是为了样本多样性好看，而是线上学生就是这三种输入。
2. **每人 10 段的构成**（共 30 段）：
   - 4 段正常回答（60–90 秒）
   - 2 段含刻意思考停顿（心里数 0.5 秒 / 1.5 秒各一段）
   - 2 段密集术语（从 50 词表里各挑 8–10 个）
   - 1 段带咳嗽 / 键盘声
   - 1 段主动打断面试官
3. **授权**：走产品里的 consent 弹窗，把 `consent_version` 记进记录。验收本身也要合规。

### 标注

一个人标即可——这三个量没有主观空间，不需要两人交叉仲裁。
Audacity 拉 label track，导出 TSV（`start_s <TAB> end_s <TAB> speech|pause`）。30 段约 1.5 小时。

### 跑分

```bash
cd backend
# 1) 从一批 wav 生成清单与标注模板
PYTHONPATH=. .venv/bin/python scripts/eval_voice_corpus.py \
    --make-template ../eval-runs/voice-corpus-<date>

# 2) 人工补完 manifest.json + labels/*.tsv 之后出分
PYTHONPATH=. .venv/bin/python scripts/eval_voice_corpus.py \
    --corpus ../eval-runs/voice-corpus-<date> \
    --report ../eval-runs/voice-acceptance-<date>/gate2/result.json
```

**"误判说完 / 误判打断"不靠人工标注**：把 automatic 开成"只记录、不提交"
（`VOICE_LIVEKIT_AUTOMATIC_TURNS_ENABLED=0` 时 turn detector 仍会发 `eot_prediction` 事件），
跑 3 场真面试，比对「系统会在何时提交」与「人何时点提交」的时间差分布，用它估误判率。

### 通过线（首轮宽口径）

| 指标 | 通过线 | 备注 |
| --- | --- | --- |
| 句尾被吞 | **0 / 30** | 不可妥协，吞句尾等于丢答案 |
| 开口/结束边界 MAE | ≤ 250 ms | 原方案 150 ms 是朗读语料标准，真人面试先站住再收紧 |
| 长停顿检测 F1 | ≥ 0.85 | |
| 金融术语 recall | ≥ 90% | 最对口 SAIF，也最能暴露通用 ASR 的短板 |

### 不通过怎么办

**不要回去撞阈值。** 按「哪个设备 / 哪类停顿」分桶看：大概率是某一种麦克风低音量漏检，
那就只对那一类做增益补偿。全局放宽阈值等于用误判换漏判。

在 Gate 2 通过之前，automatic 结束与 adaptive interruption 一律保持关闭。

---

## Gate 3 · 真实通话测试

**环境**：devvps 上 docker 起自建 `livekit-server`（**记得配 TURN**，否则手机蜂窝网连不上），
填 `LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET`，起 agent worker：

```bash
cd backend && PYTHONPATH=. .venv/bin/python scripts/run_interview_voice_agent.py
```

**三个数不许人工掐表。** `interview_realtime_events` 里已经有 `occurred_at`
（事件发生时刻，不是入库时刻）和 `turn_index`，直接从事件流导出算 p95。

**场景**：Chrome 桌面 + 手机 Safari 各一场 20 分钟；外加 30 次定向打断 / 断网重连。

| 指标 | 通过线 |
| --- | --- |
| 答完 → 面试官出声 | p95 < 1.5 s |
| 按下打断 → 真的静音 | p95 < 300 ms |
| 断网恢复 | < 5 s，且不重复问题、无旧音残留 |
| 凭证泄漏 | 浏览器流量 / localStorage / 日志中不得出现 provider key |

**不通过**：事件流能区分是 agent 侧慢还是网络侧慢。达不到就**保持旧链路上线，不买云服务**
——这一关的商业意义就是"先花一晚上，再决定要不要花钱"。

---

## Gate 4 · 老师盲评

**设计**：同一个学生、同一条 JD，用旧版本与新版本各跑一场，两份报告**去掉标识、随机排 A/B**。

老师只回答三个问题：

1. 哪份更到位？
2. 哪一句最有用？
3. 哪一句最像废话或像编的？

**不做统计显著性**——2 场做不出，硬做反而露怯。产出是定性结论 + 可引用的老师原话。

**通过线**：老师选新版，且能指出至少一条"这条我会拿去跟学生说"。

**不通过**：这是最有价值的失败——说明工程做对了但产品价值没兑现，
回去改的是**内容与提示词，不是代码**。

---

## 签字页模板

| 关卡 | 日期 | 执行人 | 关键数字 | 结论 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 1 自动检查 | | 开发 | 越权 N/N 拒绝；20 轮 0 丢失；fixture go，RTF p95 | | `eval-runs/.../gate1/` |
| 2 真人语料 | | 产品+2 | 句尾丢失 0/30；边界 MAE __ ms；停顿 F1 __；术语 recall __% | | `eval-runs/.../gate2/` |
| 3 真实通话 | | 开发 | 出声 p95 __ s；打断 p95 __ ms；重连 __ s | | `eval-runs/.../gate3/` |
| 4 老师盲评 | | 产品+老师 | 老师选 __ 版；原话摘录 | | `eval-runs/.../gate4/` |

**必须附「本次未覆盖」一段**，例如：未测多人同时在线、未测 3% 丢包弱网、automatic 结束仍默认关闭、
语音保存默认不授权、真人样本仅 3 人。主动写出边界，比堆通过项更让人信。

---

## 预判的三个质疑

**"3 个人的样本能代表学生吗？"**
不能。所以它只用来校准**客观时间量**——这类量与说话人关系小、与设备和算法关系大。
主观判断全部留给 Gate 4。

**"你们自己测自己，不算数吧？"**
所以有 Gate 4：报告去标识、随机排序、老师来选。前三关我们只敢说"没坏"。

**"没通过怎么办？"**
每一关都写死了降级动作（见总览表）。方案里没有"想办法让它过"。
