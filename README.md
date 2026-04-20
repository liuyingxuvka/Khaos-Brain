# Codex Memory Starter

Current template version: `v0.1.1`

中文 / Chinese

一个轻量、文件型、可审查的 Codex 记忆库起步模板。

它不是在公开发布你的真实经验卡片，而是在发布这套系统本身：
- 路径优先的检索结构
- 预测型卡片 schema
- observation / consolidation / rollback 工具
- 供 Codex 使用的 skill 与维护流程

## 从哪里开始

如果你是普通使用者：
- 先看 “如何使用这个模板”
- 先运行检索与记录命令
- 再慢慢建立自己的 `kb/public/`、`kb/private/`、`kb/candidates/`

如果你是开发者：
- 先看 `PROJECT_SPEC.md`
- 再看 `.agents/skills/local-kb-retrieve/`
- 最后看 `local_kb/` 和 `tests/`

## 这个公开仓库里有什么

- 本地 KB 存储骨架
- route-first 检索与导航
- task observation 记录
- sleep maintenance 脚手架
- proposal / rollback 工具
- taxonomy 层与测试

## 这个公开仓库里没有什么

- 没有你的真实卡片
- 没有你的 private 偏好
- 没有你的真实 history
- 没有应在真实工作中直接依赖的 live trusted cards

如果你看到示范性内容，它只能作为结构示例，不应被当成你的真实经验系统直接使用。

## 如何使用这个模板

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 保持 `kb/` 为空骨架或只保留你自己愿意版本化的最小示例

3. 从自己的卡片开始，而不是从公开模板里的示例卡片开始：

- `kb/public/`：共享启发式
- `kb/private/`：私人偏好或敏感经验
- `kb/candidates/`：新出现、待 consolidation 的 lesson

4. 在工作前先做一次轻量检索：

```text
$local-kb-retrieve
```

## 常用命令

搜索 KB：

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_search.py \
  --repo-root . \
  --path-hint "your/route/hint" \
  --query "task summary plus useful keywords" \
  --top-k 5 \
  --json
```

查看 taxonomy：

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_taxonomy.py \
  --repo-root . \
  --json
```

记录一次 observation：

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_feedback.py \
  --repo-root . \
  --task-summary "what the task was" \
  --route-hint "best/route/hint" \
  --hit-quality "hit" \
  --outcome "short result" \
  --comment "what was learned or what was missing" \
  --suggested-action "new-candidate" \
  --json
```

运行 proposal-only maintenance：

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_consolidate.py \
  --repo-root . \
  --run-id "daily-maintenance" \
  --emit-files \
  --apply-mode none \
  --json
```

查看 maintenance stubs：

```bash
python .agents/skills/local-kb-retrieve/scripts/kb_proposals.py \
  --repo-root . \
  --run-id "daily-maintenance" \
  --json
```

## 仓库结构

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ VERSION
├─ requirements.txt
├─ .agents/
│  └─ skills/
│     └─ local-kb-retrieve/
├─ docs/
│  └─ maintenance_runbook.md
├─ kb/
│  ├─ public/
│  ├─ private/
│  ├─ candidates/
│  ├─ history/
│  └─ taxonomy.yaml
├─ local_kb/
├─ schemas/
└─ tests/
```

## 校验

运行当前真实可用的模板测试：

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## 模板说明

- 公开模板应主要发布架构，不应顺手把你的真实 KB 一起发布出去
- `kb/private/`、`kb/history/` 默认不应进入公开发布面
- `kb/public/` 里的 live cards 也不应默认跟这个公开模板一起演化
- 更推荐把真实记忆库放在 private repo 或 private clone 中持续使用

---

English

A lightweight, file-based starter kit for building a local memory layer that Codex can consult before it works.

This repository publishes the system itself, not your real experience cards:
- route-first retrieval structure
- predictive card schema
- observation / consolidation / rollback tooling
- Codex skills and maintenance workflow

## Start Here

If you are a normal user:
- read the usage section first
- run search and observation commands first
- then build your own `kb/public/`, `kb/private/`, and `kb/candidates/`

If you are a developer:
- read `PROJECT_SPEC.md` first
- then inspect `.agents/skills/local-kb-retrieve/`
- then inspect `local_kb/` and `tests/`

## What This Public Repo Includes

- file-based KB skeleton
- route-first retrieval and navigation
- task observation logging
- sleep-maintenance scaffolding
- proposal and rollback tooling
- taxonomy layer and tests

## What This Public Repo Does Not Include

- your real cards
- your private preferences
- your real history
- live trusted cards that should be directly relied on in production work

If any sample content appears, treat it as structural illustration only, not as a real memory system ready for direct use.

## Quick Use

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Keep `kb/` as an empty skeleton, or only preserve the smallest example content you intentionally want versioned.

3. Start with your own cards:

- `kb/public/` for reusable shared heuristics
- `kb/private/` for private or sensitive preferences
- `kb/candidates/` for new lessons waiting for consolidation

4. Use the repo-local skill before work:

```text
$local-kb-retrieve
```

## Validation

Run the current template-safe test set:

```bash
python -m unittest discover -s tests -p "test_*.py"
```
