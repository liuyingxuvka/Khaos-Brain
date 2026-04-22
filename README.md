# Codex-Memory-Plugin

- Repository head (`main`) / 仓库主线（`main`）: `v0.1.8`
- Latest released version / 最新已发布版本: `v0.1.8`
- 中文正文在前；后半部分是完整英文镜像。
- Chinese comes first; the second half is a full English mirror.

## 中文

### 这是什么

这是一个给 Codex 配套使用的本地预测型知识库系统，不是一个脱离 Codex 单独存在的“记忆应用”。

它的作用，是把经验写成可检索、可审查、可版本化的结构化模型，让 Codex 在做事前先回忆、做事后再沉淀。

它建模的不只是任务经验，也包括：

- 用户偏好
- 协作方式
- Codex 自己的运行时行为

### 最简单的用法

对大多数人来说，用法其实只有一句话：

把这个仓库网址交给 Codex，然后告诉它：

> “我想在本地使用 / 安装这套系统。”

或者更具体一点：

> “请把这个仓库作为我的本地 Codex 记忆系统安装起来，并接入日常使用。”

通常不需要先自己读完 README，再手工敲所有命令。

下面那些安装和检查命令，更适合：

- 想手动验证安装的人
- 想调试仓库的人
- 想继续开发这套系统的人

### 它和 Codex 的关系

这不是一个“换成任何 AI 都能直接照抄运行”的通用模板。它明确依赖 Codex 已经提供的能力，例如：

- skills / preflight invocation
- 仓库级指令，例如 `AGENTS.md`
- automations / scheduled runs
- 本地 Python 脚本执行
- 仓库里的检索、maintenance 和 write-back 流程

也正因为它依赖 Codex，这套系统才不需要用户持续盯着维护：

- Codex 可以在任务开始前先检索已有经验
- Codex 可以在任务结束后把 observation 写回 history 或 candidates
- Codex 可以按定时规则自动跑 sleep / dream maintenance
- 用户不需要天天手工检查这个库有没有整理、有没有继续长经验

### Sleep 和 Dream

这个仓库现在把维护拆成两条分开的节律：

- `KB Sleep`
  用来整理真实发生过的任务证据，默认每天 `12:00` 运行
- `KB Dream`
  用来对邻近但还没被充分验证的机会做一次有边界的小实验，默认每天 `13:00` 运行

它们不会并发混跑，而且都由安装器写入 Codex 的 automations。

所以把仓库换到另一台机器后，只要重新让 Codex 安装一次，同样的维护机制就会一起恢复。

### 它到底在建模什么

这套系统至少在建三类模型：

1. 任务模型
   某类发布、调试、写作、协作任务里，什么路径更可能成功。
2. 用户模型
   某个用户更偏好什么结构、什么说明顺序、什么交付边界。
3. 运行时模型
   Codex 在什么提示、流程、工具条件下更容易漏什么，改完后什么更稳。

所以它不是只保存一句“下次这样做”，而是保存更像“如果这样做，更可能发生什么”的经验关系。

### 如果你只是想使用它

默认路径应该是：

1. 把这个仓库发给 Codex。
2. 明确说你想“在本地安装并使用这套系统”。
3. 让 Codex 完成安装、检查、接入和后续维护。

只有在你想手动排查、改代码或做二次开发时，才需要关心下面这些仓库内部细节。

### 手动安装与检查（可选）

如果你是协作者，或者你就是想手动跑一遍：

```bash
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
```

安装器会做三类事情：

- 安装全局 preflight / launcher，让 Codex 知道在仓库任务前先检索这套 KB
- 在 `$CODEX_HOME/AGENTS.md` 下写入或刷新 repo-managed 的全局默认约束 block，把 KB preflight / postflight 变成另一台机器也能继承的强默认规则层
- 在 `$CODEX_HOME/automations/` 下刷新 repo-managed 的 `KB Sleep` 和 `KB Dream`

### 公开仓库里放什么，不放什么

这个公开仓库默认放的是：

- schema
- 检索、记录、maintenance 工具
- skills、prompt、安装器和测试
- 可公开的结构和示例

默认不应该顺手公开：

- live private cards
- 真实 `kb/history`
- 真实 `kb/candidates`
- 任何用户特定、敏感、未确认可公开的经验数据

### 如果你是开发者

建议从这几个入口开始：

- `PROJECT_SPEC.md`
- `.agents/skills/local-kb-retrieve/`
- `local_kb/`
- `tests/`

### Repository layout

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ VERSION
├─ docs/
├─ .agents/
├─ kb/
├─ local_kb/
├─ schemas/
├─ scripts/
├─ templates/
└─ tests/
```

## English Mirror

### What This Is

This is a local predictive knowledge system built to work with Codex. It is not a standalone memory app that lives independently from Codex.

Its job is to turn experience into retrievable, reviewable, versioned structured models so Codex can recall before acting and consolidate after acting.

It models more than task experience. It also models:

- user preferences
- collaboration patterns
- Codex's own runtime behavior

### The Simplest Way To Use It

For most people, the usage is really just one sentence:

Give this repository URL to Codex and tell it:

> "I want to use / install this system locally."

Or a little more explicitly:

> "Please install this repository as my local Codex memory system and wire it into daily use."

In most cases you do not need to read the whole README first and manually type every command yourself.

The install and check commands below are mainly for:

- people who want to verify the install manually
- people who want to debug the repository
- people who want to continue developing the system

### How It Relates To Codex

This is not a generic template that runs the same way with any AI. It explicitly depends on capabilities that Codex already provides, such as:

- skills / preflight invocation
- repository-level instructions such as `AGENTS.md`
- automations / scheduled runs
- local Python script execution
- repository-native retrieval, maintenance, and write-back flows

And because it depends on Codex, the system does not require a human to babysit it continuously:

- Codex can retrieve prior experience before a task begins
- Codex can write observations back to history or candidates after a task ends
- Codex can run sleep / dream maintenance on a schedule
- the user does not have to keep checking whether the library was consolidated or extended

### Sleep And Dream

The repository now separates maintenance into two different rhythms:

- `KB Sleep`
  consolidates evidence from real tasks and runs by default every day at `12:00`
- `KB Dream`
  runs one bounded experiment on a nearby but under-validated opportunity and runs by default every day at `13:00`

These lanes do not run concurrently, and both are provisioned by the installer into Codex automations.

So when the repository moves to another machine, asking Codex to install it again restores the same maintenance mechanism there too.

### What It Is Actually Modeling

The system is building at least three kinds of models:

1. Task models
   In a certain kind of release, debugging, writing, or collaboration task, which path is more likely to succeed.
2. User models
   What structure, explanation order, and delivery boundary a specific user is more likely to prefer.
3. Runtime models
   Under which prompts, workflows, or tool conditions Codex is more likely to miss something, and which revised path becomes more stable.

So it is not just saving one sentence like "do this next time." It is saving something closer to "if we act this way, this is more likely to happen."

### If You Just Want To Use It

The default path should be:

1. Send this repository to Codex.
2. State clearly that you want to install and use the system locally.
3. Let Codex handle installation, checks, integration, and ongoing maintenance.

You only need the repository-internal details below if you want to debug manually, change code, or extend the system.

### Manual Install And Check (Optional)

If you are a collaborator, or you simply want to run it yourself:

```bash
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
```

The installer does three main things:

- installs the global preflight / launcher so Codex knows to consult this KB before repository work
- writes or refreshes a repo-managed defaults block under `$CODEX_HOME/AGENTS.md` so another machine inherits the strongest available session-wide KB preflight and postflight rules
- refreshes the repo-managed `KB Sleep` and `KB Dream` automations under `$CODEX_HOME/automations/`

### What This Public Repository Includes And Excludes

This public repository is meant to include:

- schema
- retrieval, recording, and maintenance tools
- skills, prompts, installer logic, and tests
- public-safe structures and examples

It should not casually publish:

- live private cards
- real `kb/history`
- real `kb/candidates`
- any user-specific, sensitive, or not-yet-approved experience data

### If You Are A Developer

A good starting order is:

- `PROJECT_SPEC.md`
- `.agents/skills/local-kb-retrieve/`
- `local_kb/`
- `tests/`

### Repository Layout

```text
.
├─ AGENTS.md
├─ PROJECT_SPEC.md
├─ README.md
├─ VERSION
├─ docs/
├─ .agents/
├─ kb/
├─ local_kb/
├─ schemas/
├─ scripts/
├─ templates/
└─ tests/
```
