# 工作流规则

> 这个文件定义了对 `C:\Users\Administrator\Desktop\控制电脑` 项目做改动的硬性规则。
> AI 助手（包括但不限于 OpenClaw / Claude / GPT）必须遵守。

## 🔒 规则 1：改文件前必须先备份

**任何对项目源文件（.py / .json / .spec / .md / 配置）的修改，必须先调用 `python backup.py` 创建快照。**

### 备份脚本
- 路径: `backup.py`
- 位置: 项目根目录
- 备份目录: `backups/snapshot_YYYYMMDD_HHMMSS[_描述]/`

### 标准流程

```
1. python backup.py                    # 备份所有项目源文件
   或 python backup.py -d "描述本次改动"   # 加描述
2. <修改文件>
3. python backup.py --list             # 验证备份已创建
```

### 一键回档

```
python backup.py --rollback             # 回档到最新备份
python backup.py --rollback <name>      # 回档到指定备份
python backup.py --diff                 # 查看与最新备份的差异
python backup.py --diff <name>          # 查看与指定备份的差异
```

### 强制约定
- ✅ 改任何源码前必须先 `python backup.py`
- ✅ 回档前会自动再备份一次当前状态（防止回档后回不来）
- ✅ 备份描述要简短有意义（如 `-d "fix: 修复托盘闪退"`）
- ❌ 不要 `rm` / `trash` 任何备份，除非用户明确要求

### AI 助手必须遵守

如果你（AI 助手）正在修改这个项目：
1. **第一动作必须是 `python backup.py -d "<简短描述>"`**
2. 用 backup 的输出（snapshot 名）证明备份已建
3. 改完后再用 `python backup.py --list` 确认

## 🔒 规则 2：改动后必须验证编译

```
python -m py_compile <file.py>     # 验证 Python 语法
```

如果失败，立即回档：
```
python backup.py --rollback
```

## 🔒 规则 3：提交到 Git

```
git add -A
git commit -m "<type>: <subject>"
```

Commit message 用英文简短描述（用户偏好）。

---

**违反这些规则的改动视为事故，需要立即回档。**
