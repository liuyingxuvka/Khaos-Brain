# Khaos Brain

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="Khaos Brain concept hero image" width="100%" />
</p>

<p align="center">
  <strong>A local predictive experience layer where AI agents turn repeated work into inspectable model cards.</strong>
</p>
<!-- README HERO END -->

- Repository head (`main`) / 仓库主线（`main`）: `v0.5.0`
- Latest released version / 最新已发布版本: `v0.5.0`
- Project name / 项目名称: `Khaos Brain`
- English lead content comes first; the full Chinese section follows below. / 英文主内容在前，完整中文部分在后方。

<p align="center">
  <img src="assets/khaos-brain-icon.png" alt="Khaos Brain icon" width="136">
</p>

`Khaos Brain` is a local predictive experience layer for AI agents. Instead of saving vague memories, it stores bounded model cards: the situation, the action under consideration, the predicted result, the confidence, the source, the status, and how an agent should use that lesson next time.

Those cards stay visible files. They can be searched, reviewed, diffed, consolidated, rolled back, and shared through an optional organization repository without exposing a user's private local KB by default. The current release is Codex-first, with installer-managed skills, global defaults, and local maintenance automations already wired for Codex; the design can be adapted to any host agent that supports preflight retrieval, post-task write-back, local scripts, reusable workflows, scheduled maintenance, and Git.

## Why It Is Worth Trying

- It turns "remember this" into a predictive model card with conditions, action, expected outcome, confidence, source, and operational guidance.
- It keeps agent memory local, file-based, Git-versioned, and inspectable instead of hiding it in an opaque memory service.
- It gives memory a maintenance rhythm: awake retrieval/write-back, Sleep consolidation, Dream exploration, Architect mechanism review, and optional organization maintenance.
- It makes Skill sharing more useful by pairing a Skill with the experience card that explains when and why to use it.

## Product Preview

| Local + Organization Cards | Organization Source | Card Detail |
| --- | --- | --- |
| ![Khaos Brain desktop overview with local and organization cards](assets/screenshots/desktop-overview-en.png) | ![Khaos Brain organization source view](assets/screenshots/desktop-organization-en.png) | ![Khaos Brain card detail view](assets/screenshots/desktop-detail-en.png) |

## English

### What Khaos Brain Is

`Khaos Brain` is a local predictive experience system for AI agents. It does not only store memories; it organizes task experience, predictive models, user preferences, runtime lessons, and shareable Skills into visible, maintainable, Git-versioned cards:

- the situation where a lesson applies;
- the action or route that was taken;
- the predicted or observed result;
- the weaker route that failed, when that contrast matters;
- source, author, status, confidence, and review metadata;
- skill or workflow dependencies when a lesson depends on a reusable capability.

The result is a card library that is local-first, inspectable, searchable, reviewable, mergeable, reversible, and friendly to Git history.

### The Problem It Solves

Most AI memory systems save shallow reminders: "remember to do this next time." That is rarely enough for real work.

Useful agent memory needs conditions, actions, outcomes, confidence, provenance, and maintenance. It should also know when a lesson is private, when it can be shared, when it is only a candidate, and when a repeated failure should become a stronger route.

Khaos Brain turns those details into files rather than opaque vector-only memory. A human or maintenance agent can inspect cards, diffs, candidates, rollback records, and review outcomes.

### Why It Feels Like A Brain

The system follows a brain-like rhythm:

- **Awake work:** the agent retrieves relevant experience before a task and writes observations afterward.
- **Sleep consolidation:** `KB Sleep` merges duplicates, splits swollen cards, repairs weak lessons, and maintains confidence.
- **Dream exploration:** `KB Dream` explores nearby but under-validated opportunities in a bounded way.
- **Architecture review:** `KB Architect` reviews installer, automation, rollback, proposal queues, and maintenance machinery.
- **Organization maintenance:** shared organization sources have their own candidate, review, and maintenance path.

After installation, these rhythms can run through local automations. Task preflight and postflight keep retrieval and write-back close to ordinary work, while Sleep, Dream, Architect, and organization maintenance improve the library over time.

### Personal Mode And Organization Mode

Personal mode is the default. Each machine maintains its own local KB, preserving private preferences, local context, and local skill-use evidence.

Organization mode is optional. After Settings validates a Khaos organization KB GitHub repository, the desktop UI enables organization sources, organization cards, organization skill registry, and contribution / maintenance flows.

The boundary is intentional:

- personal preferences stay local by default;
- reusable task models, engineering experience, maintenance routes, and skill-use evidence can enter an organization candidate pool;
- organization cards carry source, author, status, confidence, and read-only metadata;
- local retrieval remains first;
- organization cards sync into a local cache and become local experience only after actual use;
- meaningful local improvements can flow back as organization candidates.

### Organization Sharing Is More Than Skill Sharing

The core organization feature is not just copying skill files to teammates. The important layer is shared experience models.

An organization card can explain:

- which task class the lesson applies to;
- which route or action to use;
- what outcome it predicts;
- its status and confidence;
- who authored it;
- whether it depends on a skill.

When a card depends on a skill, the skill travels as a card-bound bundle through the organization candidate flow. Candidate skills are not auto-installed. Only approved skills with pinned version and content-hash metadata are eligible for installation on another machine.

That gives skill sharing context: a teammate receives not only a script, but the lesson explaining why it exists, when to use it, and where its boundaries are.

### Why GitHub Is Enough For An Organization KB

An organization shared KB can be a private GitHub repository.

That has practical advantages:

- no separate memory server to deploy;
- existing GitHub permissions, branches, review, Actions, and rollback;
- cards, candidate pools, import records, and skill registries remain inspectable files;
- automated maintenance can submit proposals while GitHub handles checks and history;
- if automation makes a bad change, a human can revert it through normal Git history.

For many teams, a private repository is already the simplest reliable memory backend.

### Why Try This Instead Of Another AI Memory Product

- **Visible:** cards can be opened directly; source, author, confidence, status, and skill dependencies are visible.
- **Maintainable:** Sleep, Dream, Architect, and organization maintenance treat memory as a living system.
- **Local-first:** organization mode does not overwrite personal memory.
- **Organization-ready:** teams can share routes, lessons, maintenance methods, and reviewed skills.
- **Git-native:** history, diff, review, rollback, private access, and automation can reuse GitHub.
- **Open and customizable:** structure, cards, scripts, skills, and UI are files and source code.
- **Honest automation:** shared knowledge still moves through candidates, review, maintenance, and rollback.

### What Kind Of AI Agent It Needs

The out-of-the-box host is currently Codex because Codex supports:

- repository-level instructions such as `AGENTS.md`;
- skills and preflight invocation;
- local script execution;
- automations and scheduled runs;
- GitHub and filesystem workflows;
- post-task observation and write-back.

Another AI host can adapt the structure if it can read experience before work, write evidence afterward, load reusable workflows, run local maintenance scripts, and safely read/write Git repositories.

### If You Just Want To Use It

The most natural path is to hand this repository to your AI agent and say:

```text
Install and enable this Khaos Brain experience system on this machine, then run the health check.
```

Codex follows the repository rules and runs:

```bash
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
```

After the check passes, the machine has the global preflight skill, postflight rules, `KB Sleep`, `KB Dream`, `KB Architect`, and the organization contribution / maintenance entry points.

### Desktop Card Viewer

The Windows Release includes the preview `KhaosBrain.exe`:

- download `KhaosBrain.exe` from [GitHub Releases](https://github.com/liuyingxuvka/Khaos-Brain/releases/latest);
- place it in this repository directory, or pass `--repo-root` to point it at this repository;
- double-click it to browse cards.

Source entry:

```bash
python scripts/kb_desktop.py --repo-root . --language en
```

Chinese UI:

```bash
python scripts/kb_desktop.py --repo-root . --language zh-CN
```

Headless check:

```bash
python scripts/kb_desktop.py --repo-root . --check
```

The desktop viewer does not start a browser, local web service, Electron, or Node. It reads the same file-based KB and, in organization mode, shows source, author, status, confidence, and skill dependency metadata.

For the Windows exe, desktop shortcut, or Codex UI-opening skill, see [Windows desktop app](docs/windows_desktop_app.md). For organization mode, see [Organization mode plan](docs/organization_mode_plan.md).

### Voluntary Support

If this project is useful to you, you can support its development here:

[Buy me a coffee via PayPal](https://paypal.me/Yingxuliu)

Contributions are voluntary and do not purchase support, warranty, priority service, commercial rights, or feature requests.

### What This Public Repository Includes And Excludes

This public repository is meant to include:

- schema;
- retrieval, recording, and maintenance tools;
- skills, prompts, installer logic, and tests;
- public-safe structures, screenshots, and examples.

It should not casually publish:

- live private cards;
- real private history;
- real candidate pools containing unreviewed personal details;
- credentials, account data, machine-specific paths, or sensitive project context.

### If You Are A Developer

A good starting order is:

- `PROJECT_SPEC.md`
- `.agents/skills/local-kb-retrieve/`
- `local_kb/`
- `tests/`
- `docs/organization_mode_plan.md`
- `docs/release_policy.md`

### Repository Layout

```text
.
├─ AGENTS.md
├─ CHANGELOG.md
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

## 中文

### Khaos Brain 是什么

`Khaos Brain` 是一个给 AI agent 使用的本地预测型经验层。它不只是保存一句“下次记得这样做”，而是把反复出现的工作经验写成有边界的模型卡片：适用情境、考虑中的动作、预测结果、可信度、来源、状态，以及 agent 下次应该怎样使用这条经验。

这些卡片仍然是可见文件，可以搜索、审查、diff、整理、回滚，也可以通过可选的组织仓库共享可复用经验，同时默认不公开用户自己的本地私有 KB。当前版本首先集成 Codex：安装器、全局 Skill、`AGENTS.md` 默认规则和本地维护自动化都已经接好；但只要宿主 agent 能在任务前检索、任务后写回、运行本地脚本、加载可复用工作流、做定期维护并读写 Git 仓库，同样结构也可以迁移。

### 为什么值得一试

- 它把“下次记得这样做”变成预测型模型卡片，写清适用条件、动作、预期结果、可信度、来源和使用方式。
- 它把 agent 记忆保留为本地、文件化、Git 可追踪、可审查的结构，而不是藏在黑盒记忆服务里。
- 它让记忆有维护节律：任务前检索和任务后写回，随后由 Sleep、Dream、Architect 和可选组织维护继续整理。
- 它让 Skill 共享更有上下文：共享的不只是脚本，还有说明“什么时候该用、为什么该用”的经验卡片。

### 它解决什么问题

大多数 AI memory 只保存浅层提醒，比如“下次记得这样做”。这对真实工作通常不够。

有用的 agent memory 需要条件、动作、结果、可信度、来源和维护节律。它还应该知道哪些经验是私人的，哪些可以共享，哪些只是候选，哪些重复失败应该沉淀成更强路线。

- 在什么条件下
- 采取什么动作
- 更可能得到什么结果
- 哪条路线失败过，哪条路线更稳
- 这个经验来自谁、哪个来源、是否已经被信任
- 如果一个 Skill 很关键，它到底在哪类任务里有用

`Khaos Brain` 把这些内容做成卡片。卡片不是黑盒向量，不是散乱笔记，也不是只能靠人手维护的规则列表。它们是文件型、可阅读、可搜索、可审查、可合并、可回滚的经验单元。

### 为什么它像一个“脑”

系统刻意采用脑式节律：

- **醒着做任务：** agent 在任务前检索相关经验，在任务后写回观察。
- **睡眠整理：** `KB Sleep` 合并重复卡片、拆分臃肿卡片、修复弱经验、维护 confidence。
- **做梦探索：** `KB Dream` 在有边界的范围内探索相近但证据不足的机会。
- **结构审查：** `KB Architect` 检查 installer、automation、rollback、proposal queue 和维护机制本身。
- **组织维护：** 共享组织来源有自己的 candidate、review 和 maintenance 路径。

安装后，这些节律可以通过本地 automations 运行。任务 preflight/postflight 让检索和写回贴近日常工作；Sleep、Dream、Architect 和 organization maintenance 则在后续窗口持续改进卡片库。

### 个人模式和组织模式

个人模式是默认模式。每台机器维护自己的本地 KB，保留私人偏好、本地上下文和本地 skill-use evidence。

组织模式是可选的。Settings 验证一个 Khaos organization KB GitHub 仓库后，桌面 UI 会启用 organization sources、organization cards、organization skill registry，以及 contribution / maintenance flows。

边界是故意这样设计的：

- personal preferences 默认留在本地；
- reusable task models、engineering experience、maintenance routes、skill-use evidence 可以进入 organization candidate pool；
- organization cards 携带 source、author、status、confidence、read-only metadata；
- local retrieval 仍然优先；
- organization cards 先同步到本地 cache，只有真正使用后才变成本地经验；
- 有意义的本地改进可以再作为 organization candidates 回流。

### 组织共享的不只是 Skill

组织功能的核心不是简单复制 skill 文件给同事，更重要的是共享经验模型。

一张 organization card 可以说明：

- 经验适用于哪类任务；
- 应该使用哪条 route 或 action；
- 预测什么 outcome；
- 当前 status 和 confidence；
- 谁创建了它；
- 是否依赖某个 skill。

如果一张 card 依赖 skill，这个 skill 会作为 card-bound bundle 进入 organization candidate flow。Candidate skill 不会自动安装。只有带 pinned version 和 content-hash metadata 的 approved skill，才有资格安装到另一台机器。

这让 skill sharing 有上下文：队友拿到的不只是脚本，还有说明它为什么存在、什么时候用、边界在哪里的经验卡片。

### 为什么用 GitHub 做组织 KB 就够了

组织共享 KB 可以是一个 private GitHub repository。

这样有几个实际好处：

- 不需要额外部署 memory server；
- 复用 GitHub permissions、branches、review、Actions 和 rollback；
- cards、candidate pools、import records、skill registries 都是可检查文件；
- 自动维护可以提交 proposal，同时由 GitHub 管理 checks 和历史；
- 如果自动化产生坏改动，人可以通过普通 Git 历史回滚。

对很多团队来说，private repository 已经是最简单可靠的 memory backend。

### 为什么它比普通 AI 记忆产品更值得试

- **可见：** card 可以直接打开，source、author、confidence、status、skill dependencies 都可见。
- **可维护：** Sleep、Dream、Architect 和 organization maintenance 把 memory 当成活系统。
- **本地优先：** organization mode 不覆盖个人记忆。
- **组织可用：** 团队共享 route、lesson、maintenance method 和 reviewed skill。
- **Git-native：** history、diff、review、rollback、private access 和 automation 都可以复用 GitHub。
- **开放可定制：** structure、cards、scripts、skills、UI 都是文件和源码。
- **诚实自动化：** 高价值共享知识仍然要经过 candidates、review、maintenance 和 rollback。

### 它依赖什么样的 AI agent

当前开箱 host 是 Codex，因为 Codex 支持：

- `AGENTS.md` 这样的 repository-level instructions；
- skills 和 preflight invocation；
- local script execution；
- automations 和 scheduled runs；
- GitHub 和 filesystem workflow；
- post-task observation 和 write-back。

其他 AI host 如果能在任务前读取经验、任务后写回证据、加载 reusable workflow、运行本地维护脚本，并安全读写 Git 仓库，也可以适配这套结构。

### 如果你只是想使用它

最自然的路径是把这个仓库交给 AI agent，并说：

```text
Install and enable this Khaos Brain experience system on this machine, then run the health check.
```

Codex 会按仓库规则运行：

```bash
python scripts/install_codex_kb.py --json
python scripts/install_codex_kb.py --check --json
```

检查通过后，这台机器就有 global preflight skill、postflight rules、`KB Sleep`、`KB Dream`、`KB Architect`，以及 organization contribution / maintenance 入口。

### 桌面卡片查看器

Windows Release 包含预览版 `KhaosBrain.exe`：

- 从 [GitHub Releases](https://github.com/liuyingxuvka/Khaos-Brain/releases/latest) 下载 `KhaosBrain.exe`；
- 放到这个仓库目录，或用 `--repo-root` 指向这个仓库；
- 双击浏览 cards。

源码入口：

```bash
python scripts/kb_desktop.py --repo-root . --language en
```

中文界面：

```bash
python scripts/kb_desktop.py --repo-root . --language zh-CN
```

Headless check：

```bash
python scripts/kb_desktop.py --repo-root . --check
```

桌面查看器不会启动浏览器、本地 web service、Electron 或 Node。它读取同一套 file-based KB；在 organization mode 下，会显示 source、author、status、confidence 和 skill dependency metadata。

Windows exe、桌面快捷方式和 Codex UI-opening skill 见 [Windows desktop app](docs/windows_desktop_app.md)。组织模式见 [Organization mode plan](docs/organization_mode_plan.md)。

### 自愿支持项目维护

如果这个项目对你有用，可以在这里自愿支持维护：

[Buy me a coffee via PayPal](https://paypal.me/Yingxuliu)

这只是自愿支持，不购买支持、保修、优先服务、商业权利或功能请求。

### 公开仓库里放什么，不放什么

公开仓库应该包含：

- schema；
- retrieval、recording、maintenance tools；
- skills、prompts、installer logic、tests；
- 公开安全的结构、截图和示例。

不应该随意公开：

- live private cards；
- 真实私人历史；
- 含未审查个人细节的真实 candidate pools；
- credentials、account data、machine-specific paths 或 sensitive project context。

### 如果你是开发者

推荐阅读顺序：

- `PROJECT_SPEC.md`
- `.agents/skills/local-kb-retrieve/`
- `local_kb/`
- `tests/`
- `docs/organization_mode_plan.md`
- `docs/release_policy.md`

### 仓库结构

```text
.
├─ AGENTS.md
├─ CHANGELOG.md
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
