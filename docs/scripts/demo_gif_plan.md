# JobRadar Demo GIF 录制脚本

目标：录一个 **5~8 秒** 的首页 GIF，让 GitHub 访问者快速理解 JobRadar 是“岗位情报与投递决策系统”，而不是普通岗位爬虫。

---

## 推荐时长
- **5 秒版**：适合 README 首页首屏
- **8 秒版**：适合更完整的产品展示

---

## 推荐录制路线

### Scene 1 - 岗位总览（约 2 秒）
页面：`/`

动作：
1. 打开岗位总览页
2. 稍微滚动或移动鼠标，让人看到筛选区、岗位列表、评分/状态

想传达的信息：
- 这不是原始爬虫输出
- 这是一个可操作的岗位工作台

---

### Scene 2 - Job Intel（约 2~3 秒）
页面：`/job-intel/1`

动作：
1. 切到 Job Intel 页
2. 停留在摘要区和记录区
3. 如果需要，点击一次“搜索相关情报”

想传达的信息：
- 项目支持面经 / 薪资 / 工作强度等外部情报整合
- 它的价值不只是“抓到岗位”，而是“帮助判断是否投递”

---

### Scene 3 - 公司展开（约 2 秒）
页面：`/company-expand?...`

动作：
1. 切到有真实数据的公司展开页
2. 显示该公司下的岗位展开结果

想传达的信息：
- 支持从单岗位视角，切到公司级追踪视角
- 可以围绕重点公司持续跟踪，而不是只看散点岗位

---

## 推荐字幕文案（可选）
如果你后期加字幕，建议只放极短句：

### 版本 A
- Discover jobs
- Score and prioritize
- Enrich with job intelligence
- Decide where to apply

### 版本 B
- From job aggregation
- To job intelligence
- And focused application decisions

---

## 录制建议
- 尺寸：优先宽屏（GitHub 首页更自然）
- 尽量不要录太长
- 鼠标移动要慢
- 不要切太多页面
- 只展示最能体现差异化的部分

---

## 推荐产物路径
```text
docs/demo.gif
```

如果你后续想做更完整展示，也可以额外产出：
- `docs/demo-full.mp4`
- `docs/demo-lite.gif`

---

## README 中的替换方式
后续录好后，把当前截图区上面再补一张：

```md
![JobRadar Demo](./docs/demo.gif)
```

建议放在 `## Demo` 标题下面第一行。
