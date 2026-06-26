# LESSONS_LEARNED — 工程教训快速索引

> **目的**: 未来会话第一步先扫这个文件, 避免重蹈已知坑。
> **来源**: `/skills:engineering-lite /learn` 持续沉淀, 完整版见 `STATUS.md` 末尾「工程教训汇总」章节。
> **维护**: 新增教训直接 PR 到 `STATUS.md`「工程教训汇总」, 并在本文件加一行索引。

最后更新: 2026-06-26 08:41

---

## 🔥 P0 — 会直接导致 bug / 数据丢失 / 调试浪费数小时

| # | 教训 | 触发场景 | 一句话解法 |
|---|---|---|---|
| 1 | LLM thinking 块泄露到 UI/TTS | 用户看到 `[joy]<think>...</think>实际回复` | 双保险: system prompt 禁止 + `THINKING_PATTERN` 正则 strip |
| 2 | exe 命名混乱 (硬编码中文名) | `dist/桌面自动化助手.exe` 与 `desktop-auto-v*.exe` 混用 | 统一用 `desktop-auto-v{date}-{time}-g{hash}.exe`,`build.spec` 自动生成 |
| 3 | `edit_file` 在双 CR 文件上失败 | `build.spec` 用 `\r\r\n` 换行,`edit_file` 报 "not found" | 切 Python 字节级脚本 `read_bytes` + `replace` + `write_bytes` |
| 4 | 改源码后先 build 再 commit | exe 名显示新 hash 但装的是旧代码 | 铁律顺序: **改 → 测试 → commit → build → 杀进程 → 启新** |

## ⚠️ P1 — 会导致失败回滚 / 浪费 1-2 小时

| # | 教训 | 触发场景 | 一句话解法 |
|---|---|---|---|
| 5 | `git commit -m` 在 cmd 嵌套中文失败 | git 把 `2>&1` 后字串当 pathspec | 走临时文件 `git commit -F __commit_msg.txt` |
| 6 | diagnose "AI 输出不对" 先看 tool_call | 用户报"模型返回假数据" | 先看 `tool_call.args` 参数是否合理, 再考虑模型本身 |
| 7 | 子进程 patch 必须在入口脚本顶部 | TTS 闪屏回归, `CREATE_NO_WINDOW` 没生效 | 改子进程行为前先 `sys.executable` 确认解释器与生产一致 |
| 8 | retry 装饰器默认 retries=0 | 装饰器太激进导致 30s 卡顿 | 默认 opt-in, 只覆盖幂等操作, 用 `concurrent.futures` + timeout |
| 9 | 字节级批量替换比 edit_file 高效 | 12+ 次 edit_file 失败, 30+ 轮才改完 | ≥3 次相似 edit → 一次性 Python 脚本 |
| 10 | 双 CR (`\r\r\n`) 是 Windows 中文项目地雷 | PowerShell 编辑插入了额外 CR | 编辑大型文件前先 hex dump 头 200 字节确认换行符 |

---

## 🛠️ 铁律清单 (违反必出事故)

1. **commit → build 铁律**: 任何 build 之前必须先 commit, 否则 short hash 与 exe 内容脱节
2. **test → commit 铁律**: 提交前必须 `pytest tests/ -q` 全绿, 否则锁死的护栏没意义
3. **思考链锁死铁律**: 任何 LLM 输出处理流水线必须是 "先 strip_thinking → 再扫表情 → 再去表情标签", 顺序错就 `UnboundLocalError`
4. **字节脚本优先铁律**: 涉及非标换行 / 混合编码文件, `edit_file` 第 1 次失败就切字节级脚本, 别再试第 2 次

---

## 📖 相关文档

- `STATUS.md` 末尾「工程教训汇总」 — 完整 10 条教训 + 详细症状/根因/解法
- `BUILD.md` 「产物命名规范」 — exe 命名 + commit-before-build
- `tests/test_assistant_core.py` — thinking 过滤 7 类 15 项断言
- `engineering-lite` skill — Stage 6 技能进化流程

## 🔄 维护记录

| 日期 | 新增教训 | 触发 commit |
|---|---|---|
| 2026-06-26 | #1 thinking 过滤, #2 exe 命名, #3 双 CR 换行 | 08a6571 / 6c218e9 / af03b0c |
| 2026-06-25 | #4 commit→build 铁律, #5 commit -m 中文 | (历史沉淀) |
| 2026-06-24 | #6 diagnose 顺序, #7 子进程 patch, #8 retry 默认值 | (历史沉淀) |
