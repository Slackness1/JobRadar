# Phase G — 推荐链路 v2 生产上线 Playbook

**版本**: v1 draft (2026-05-28)
**Owner**: 网站设计-devvpstmux 会话
**前置条件**: 全 21 工序完成, T13 / T20 验收通过

---

## 一句话

把 `RECOMMENDATION_V2_ENABLED=1` 在 prod VPS (`myvps`, jobcopilot.top) 打开,
推荐链路从 v1 (10 canonical_track + rule_score + LLM rerank) 切到 v2 (29 sub_category +
3-dim cross + KB-aware LLM rerank + 4-anchor narrative + 公司 fallback)。

---

## 切换前必查清单

- [ ] **T13 准确率**: `docs/phase_g_audit/sub_cat_accuracy_review_*.md` 末尾"通过准确率" ≥ 90%
- [ ] **T20 硬指标 1-4 全过**: `docs/phase_g_audit/v2_acceptance_report_*.md`
  - top-10 干净度 27/27
  - narrative 个性化 ≥ 80%
  - fallback API smoke 全 sub_cat 都能返
  - v2 vs v1 主观胜率 ≥ 22/27
- [ ] **DB 完整性**: prod VPS 的 jobs 表必须有 sub_category 字段填到位 (T12 跑完同步)
- [ ] **knowledge_subcategories DB row**: 29 sub_cat 全在 (每条带 embedding 不能 NULL)
- [ ] **ground_truth_companies_v1.json**: 已部署到 prod backend/data/
- [ ] **dev VPS 实测通过**: `lavm-wlcndo6anm` 上 `RECOMMENDATION_V2_ENABLED=1` 灰度跑过 ≥ 48h 无 503/超时

---

## Prod 切换步骤 (myvps 上手动跑)

```bash
# 1. SSH 到 prod
ssh myvps

# 2. cd 进 worktree + 拉最新 main
cd /home/ubuntu/opencode-worktrees/jobrador-edit
git pull --ff-only origin main 2>&1 | tail -5

# 3. 跑 alembic 把 phase-g 新表/列 migration up (taxonomy_xhs_posts + knowledge_subcategories
#    + jobs 新 7 列)
cd backend
.venv/bin/pip install -r requirements.txt 2>&1 | tail -3
PYTHONPATH=. .venv/bin/alembic upgrade head 2>&1 | tail -5

# 4. 把 dev VPS 上跑好的 enrich 结果迁过来
#    选项 A — 完整 DB dump+restore (推荐):
#    在 dev VPS 上:
#       sqlite3 backend/data/jobradar.db ".backup /tmp/jobradar_phaseg.db"
#       scp /tmp/jobradar_phaseg.db myvps:/tmp/
#    在 prod VPS 上:
#       sudo systemctl stop jobradar
#       cp backend/data/jobradar.db backend/data/jobradar.db.before-phaseg
#       cp /tmp/jobradar_phaseg.db backend/data/jobradar.db
#       sudo systemctl start jobradar
#
#    选项 B — 仅迁 knowledge_subcategories 表 (jobs.sub_category 在 prod 重跑 T10+T12):
#       在 prod 跑 scripts/phase_g/06+07/10+12 一遍 (~5-7h 总时长)
#       推荐选项 A 省时间。

# 5. 在 prod env 加 RECOMMENDATION_V2_ENABLED=1
sudo systemctl edit jobradar  # 加 Environment="RECOMMENDATION_V2_ENABLED=1"
# 或改 /etc/default/jobradar (看现有部署模式)
sudo systemctl restart jobradar
sleep 5
systemctl is-active jobradar   # 应该 active

# 6. Smoke 测试 v2 endpoint
curl 'https://jobcopilot.top/api/recommend-v2/companies-fallback?sub_cat=公募权益研究员'
# 期望: 200 JSON 含 fallback_companies 数组 (不能 403 — 403 = flag 没生效)

# 7. 抽 1 个真实 session 跑推荐, 看是否走 v2 (响应里 matched_track_label 是 sub_cat 名)
# 在 prod 数据库找一个真实 session_id, 触发 /api/resume-copilot/sessions/N/recommend
# 检查返回 items[0].matched_track_label 是 "公募权益研究员" 这种 sub_cat (不是
# 老 canonical_track 像 "二级买方·基本面")
```

---

## 回滚步骤 (出问题 ≤ 5 分钟内)

```bash
ssh myvps
# 关 v2 flag → 即时切回 v1
sudo systemctl edit jobradar  # 改成 Environment="RECOMMENDATION_V2_ENABLED=0"
sudo systemctl restart jobradar
sleep 3
curl 'https://jobcopilot.top/api/recommend-v2/companies-fallback?sub_cat=x'  # 应返 403

# 如 DB 出问题 (sub_category 字段污染了老数据), 回滚 DB:
sudo systemctl stop jobradar
cp backend/data/jobradar.db.before-phaseg backend/data/jobradar.db
sudo systemctl start jobradar
```

老 v1 链路 100% 字节级保留 (T19 没动 v1 一行), flag OFF 后立即恢复无副作用。

---

## 监控 (上线后 48h)

```bash
# 1. journalctl 看 v2 dispatcher 异常 (任何 "recommend_v2 failed, fallback to v1" warning)
ssh myvps 'sudo journalctl -u jobradar --since "1h ago" | grep -E "recommend_v2|RECOMMEND" | head -20'

# 2. v2 fallback 触发次数 (期望 < 1%, 高于这数说明 v2 链路有 bug)
ssh myvps 'sudo journalctl -u jobradar --since "1h ago" | grep -c "fallback to v1"'

# 3. 推荐 response 时间 — v2 因为 LLM rerank top-20 + narrative top-10, 比 v1 慢
# 期望 p50 < 12s, p95 < 30s (vs v1 p50 ~3s)
ssh myvps 'sudo journalctl -u jobradar --since "1h ago" | grep "POST /api/resume-copilot" | grep -oE "\(\d+ms\)" | sort -n | tail -20'

# 4. 用户实际反馈渠道 (飞书 SAIF 老师群)
```

---

## 老 v1 清理时间表 (Phase H, 不在本 playbook)

T21 之后保留 v1 至少 **2 周观察期**, 期间:
- 收集 prod v2 实际推荐 vs v1 的学生反馈
- 修 v2 链路意外暴露的 bug

观察期满后由独立 cleanup pass (Phase H) 删:
- `_recommend_v1_legacy` 路径 + 老 canonical_track-based 函数 (`_classify_track_match` / `_build_track_condition` / `compute_rule_score` 部分)
- `canonical_track` 列从 jobs 表 drop (alembic migration)
- legacy persona evaluation 测试 (`tests/test_recommendation_track_filter.py`)

---

## 已知风险 + 缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| LLM rerank/narrative 慢 (~10s/case) 把 p95 拖到 30s+ | UI 等待长 | top-N 收紧到 10 (不 rerank top-20); 加 redis 缓存 (Phase H) |
| 知识库 verbatim quote 偶尔被 LLM 改写 (即使 prompt 禁止) | 学生看到假 XHS 引用 | T16 prompt 已强调"必须 substring 原文"; 加 post-validation 抓 verbatim 不在 KB 时强制改 placeholder (Phase H) |
| 偏好 sub_cat 映射粗糙 (`_v2_extract_preferred_sub_cats` 用 substring) | 学生偏好"二级买方"映射不到 sub_cat → 推荐空 | T19 frontend 改完后让用户直接选 sub_cat, 不再走推断映射 |
| Prod DB 跟 dev DB 不一致 (sub_category 字段) | v2 跑出空推荐 | 上线前必须 dump+restore 或在 prod 重跑 T10+T12 |
| canonical_track 老字段还在 schema, 学生 confirmed_profile 仍用老 track 名 | profile→sub_cat 映射经 LLM 不稳 | 旧 profile 保留 canonical_track 字段, v2 用 substring 兜底 (T19 已实现) |

---

## 切换沟通模板 (给学院老师 / SAIF 试点学生)

```
Phase G 推荐链路 v2 已上线 (2026-XX-XX):

老版本能看到的:
- 推荐里偶尔混着银行客户经理 / 销售客服 这类"伪投研"岗 (来源 quality_label 太粗)
- 推荐理由模板化 ("匹配度高")
- 头部 must_have 公司本季没岗位时直接消失 (学生以为"我们没覆盖")

新版本:
- 29 sub_cat 细分赛道, 推荐池 sub_cat-only (10x 更干净)
- 每条推荐 4-anchor 个性化 narrative: 你的 hidden_highlight + 硬门槛命中 + tier 区分 + 差距
- 头部 must_have 公司无活跃岗位 → "本季暂未开放, 通常春招 X 月集中开放" placeholder 卡片

请试用 + 反馈到飞书 SAIF 老师群。
```
