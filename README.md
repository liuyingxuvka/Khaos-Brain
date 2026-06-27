# Khaos Brain

<!-- README HERO START -->
<p align="center">
  <img src="./assets/readme-hero/hero.png" alt="Khaos Brain concept hero image" width="100%" />
</p>

<p align="center">
  <strong>A local predictive experience layer where AI agents turn repeated work into inspectable model cards.</strong>
</p>
<!-- README HERO END -->

| Repository Head | Latest Release | Project | License |
| --- | --- | --- | --- |
| `v0.5.2` | `v0.5.2` | `Khaos Brain` | MIT |

English comes first. A Chinese mirror follows below.

<p align="center">
  <img src="assets/khaos-brain-icon.png" alt="Khaos Brain icon" width="136">
</p>

## What Khaos Brain Is

Khaos Brain is a local predictive experience system for AI agents.

It does not save vague memories such as "remember this next time." It stores bounded model cards: the situation, the action under consideration, the predicted or observed result, confidence, source, status, and how an agent should use that lesson later.

Those cards are visible files. They can be searched, reviewed, diffed, consolidated, rolled back, and optionally shared through an organization repository. Personal memory stays local by default.

The current implementation is Codex-first: installer-managed skills, global defaults, local maintenance automations, and a desktop viewer are already wired for Codex. The design can be adapted to any host agent that supports preflight retrieval, post-task write-back, local scripts, reusable workflows, scheduled maintenance, and Git.

## The Problem

AI agents often restart from shallow context:

1. The agent solved a similar task before, but the lesson is buried in chat history.
2. A user preference is remembered as a sentence, not as a condition/action/outcome pattern.
3. A route worked once, but nobody knows when it should be reused.
4. A bad path repeats because the correction was never turned into a reusable warning.
5. Team knowledge is either private and invisible, or shared without review and provenance.

Khaos Brain turns repeated work into maintainable experience.

## Product Preview

| Local + Organization Cards | Organization Source | Card Detail |
| --- | --- | --- |
| ![Khaos Brain desktop overview with local and organization cards](assets/screenshots/desktop-overview-en.png) | ![Khaos Brain organization source view](assets/screenshots/desktop-organization-en.png) | ![Khaos Brain card detail view](assets/screenshots/desktop-detail-en.png) |

## How It Works

The everyday loop is:

```text
preflight search
-> task work
-> postflight observation
-> candidate or trusted card
-> Sleep / Dream / Architect maintenance
-> better retrieval next time
```

In plain language:

- **Preflight search** retrieves relevant local and organization cards before work starts.
- **Postflight write-back** records lessons, misses, corrections, and reusable patterns after work.
- **Sleep** consolidates repeated or swollen cards.
- **Dream** explores nearby opportunities and weak signals without treating them as trusted facts.
- **Architect** reviews the machinery: installer, automations, rollback, proposals, and maintenance routes.
- **Organization mode** lets reviewed cards and skill bundles move through a shared repository without exposing private local memory by default.

## What A Card Contains

| Card field | Why it matters |
| --- | --- |
| Situation | When the lesson applies |
| Action | What route, tool, skill, or decision should be considered |
| Predicted or observed result | Why the card is useful |
| Confidence and status | Whether the card is candidate, trusted, weak, stale, or under review |
| Source and author | Where the lesson came from |
| Contrast | What weaker route failed, when that matters |
| Skill dependency | Which reusable workflow or skill the card depends on |
| Operational guidance | How a future agent should use it |

This makes memory inspectable instead of opaque.

## Personal Mode And Organization Mode

Personal mode is the default. Each machine keeps its own local KB, including private preferences, local context, and local skill-use evidence.

Organization mode is optional. After Settings validates an organization KB GitHub repository, the desktop UI enables organization sources, organization cards, organization skill registry, and contribution / maintenance flows.

The boundary is intentional:

- personal preferences stay local by default;
- reusable task models and engineering lessons can enter an organization candidate pool;
- organization cards carry source, author, status, confidence, and read-only metadata;
- local retrieval remains first;
- organization cards become local experience only after actual use;
- meaningful local improvements can flow back as reviewed organization candidates.

## Organization Sharing Is More Than Skill Sharing

Khaos Brain can share Skills, but the important layer is the experience model that explains why a Skill exists.

An organization card can say:

- which task class the lesson applies to;
- which route or action to use;
- what outcome it predicts;
- who authored it and how confident it is;
- whether it depends on a Skill bundle.

Candidate Skills are not auto-installed. Only approved Skills with pinned version and content-hash metadata are eligible for installation on another machine.

## Why GitHub Is Enough For An Organization KB

An organization shared KB can be a private GitHub repository:

- no separate memory server to deploy;
- existing GitHub permissions, branches, review, Actions, and rollback;
- cards, candidates, import records, and skill registries remain inspectable files;
- automation can submit proposals while GitHub handles history and review;
- bad automation changes can be reverted through ordinary Git.

For many teams, a private repository is already the simplest reliable backend for shared agent memory.

## Install And Check

The Windows release includes the preview desktop app:

- download `KhaosBrain.exe` from [GitHub Releases](https://github.com/liuyingxuvka/Khaos-Brain/releases/latest);
- run the installer or repository setup for the local skill/runtime path used by your agent;
- run the health check before relying on retrieval.

Repository-local check:

```powershell
python scripts\install_codex_kb.py --check --json
```

Desktop viewer:

```powershell
python scripts\open_khaos_brain_ui.py
```

## What Kind Of AI Agent It Needs

The out-of-the-box host is Codex because Codex supports:

- repository-level instructions such as `AGENTS.md`;
- skills and preflight invocation;
- local script execution;
- automations and scheduled runs;
- GitHub and filesystem workflows;
- post-task observation and write-back.

Another AI host can adapt the structure if it can read experience before work, write evidence afterward, load reusable workflows, run local maintenance scripts, and safely read/write Git repositories.

## Public Boundary

This public repository contains the Khaos Brain source code, examples, schemas, installer/check scripts, UI assets, screenshots, public-safe Skill material, and empty KB scaffolding.

It does not contain a user's private KB, real local history, credentials, private candidate cards, personal preferences, organization secrets, live customer data, or unpublished local memory. Public screenshots use safe demo content.

## Repository Layout

```text
local_kb/              Core package, retrieval, cards, maintenance, desktop UI
.agents/skills/        Codex skills for retrieval, maintenance, organization flow, and UI launch
kb/                    Public-safe KB scaffold and taxonomy example
schemas/               Example card/schema files
scripts/               Install, check, launch, and maintenance helpers
templates/             Template artifacts
assets/                Icons, screenshots, and README hero assets
docs/                  Architecture, maintenance, organization, release, and UI docs
tests/                 Regression tests
VERSION                Current public version
CHANGELOG.md           Release history
```

## License

MIT. See [`LICENSE`](./LICENSE).

---

# Khaos Brain 中文说明

| 仓库主线 | 最新发布 | 项目 | 许可证 |
| --- | --- | --- | --- |
| `v0.5.1` | `v0.5.1` | `Khaos Brain` | MIT |

## 它是什么

Khaos Brain 是给 AI agent 用的本地预测经验系统。

它不是保存一句“下次记得这样做”的浅层记忆，而是保存有边界的 model cards：适用场景、可考虑的动作、预测或观察到的结果、信心、来源、状态，以及未来 agent 应该怎么使用这条经验。

这些 card 都是可见文件。它们可以被搜索、审查、diff、合并、回滚，也可以选择性通过 organization repository 共享。个人记忆默认留在本地。

当前实现是 Codex-first：installer-managed skills、global defaults、本地维护 automations 和 desktop viewer 已经接到 Codex。只要另一个 host agent 支持 preflight retrieval、post-task write-back、本地脚本、可复用 workflow、定时维护和 Git，也可以适配这个结构。

## 为什么需要它

AI agent 经常从很浅的上下文重新开始：

1. agent 以前做过类似任务，但经验埋在聊天历史里。
2. 用户偏好只是一句话，不是 condition/action/outcome pattern。
3. 某条路线成功过，但没人知道什么时候该复用。
4. 错路反复出现，因为修正没有变成可复用 warning。
5. 团队知识要么太私有、不可见，要么共享时没有 review 和 provenance。

Khaos Brain 把重复工作变成可维护经验。

## 产品预览

| 本地 + 组织 Cards | 组织来源 | Card Detail |
| --- | --- | --- |
| ![Khaos Brain desktop overview with local and organization cards](assets/screenshots/desktop-overview-en.png) | ![Khaos Brain organization source view](assets/screenshots/desktop-organization-en.png) | ![Khaos Brain card detail view](assets/screenshots/desktop-detail-en.png) |

## 它怎么工作

日常循环是：

```text
preflight search
-> task work
-> postflight observation
-> candidate or trusted card
-> Sleep / Dream / Architect maintenance
-> better retrieval next time
```

翻成人话：

- **Preflight search** 在任务开始前检索相关 local / organization cards。
- **Postflight write-back** 在任务结束后记录经验、miss、修正和可复用模式。
- **Sleep** 合并重复或过大的 card。
- **Dream** 探索附近机会和弱信号，但不把它们当成可信事实。
- **Architect** 审查 installer、automations、rollback、proposal 和 maintenance 路线。
- **Organization mode** 让 reviewed cards 和 skill bundles 可以通过共享仓库流转，同时默认不暴露私人本地记忆。

## 一张 Card 包含什么

| Card 字段 | 为什么重要 |
| --- | --- |
| Situation | 这条经验什么时候适用 |
| Action | 该考虑什么路线、工具、skill 或决定 |
| Predicted / observed result | 这张卡为什么有用 |
| Confidence / status | 它是 candidate、trusted、weak、stale 还是 under review |
| Source / author | 经验从哪里来 |
| Contrast | 哪条弱路线失败过 |
| Skill dependency | 依赖哪个可复用 workflow 或 skill |
| Operational guidance | 未来 agent 应该怎么用 |

这让 memory 可检查，而不是黑箱。

## 个人模式和组织模式

Personal mode 是默认模式。每台机器保留自己的 local KB，包括私人偏好、本地上下文和本地 skill-use evidence。

Organization mode 是可选的。Settings 验证 organization KB GitHub repository 后，desktop UI 会启用 organization sources、organization cards、organization skill registry，以及 contribution / maintenance flows。

边界是有意设计的：

- personal preferences 默认留在本地；
- 可复用任务模型和工程经验可以进入 organization candidate pool；
- organization cards 带有 source、author、status、confidence 和 read-only metadata；
- local retrieval 仍然优先；
- organization card 只有在真实使用后才会变成本地经验；
- 有意义的本地改进可以作为 reviewed organization candidate 回流。

## 组织共享不只是共享 Skill

Khaos Brain 可以共享 Skills，但更重要的是解释“为什么需要这个 Skill”的 experience model。

organization card 可以说明：

- 适用的任务类型；
- 应该使用的 route 或 action；
- 预测什么结果；
- 谁写的、可信度如何；
- 是否依赖一个 Skill bundle。

Candidate Skills 不会自动安装。只有带 pinned version 和 content-hash metadata 的 approved Skills，才有资格安装到另一台机器。

## 为什么 GitHub 足够作为组织 KB

组织共享 KB 可以就是一个 private GitHub repository：

- 不需要另起 memory server；
- 直接使用 GitHub permissions、branches、review、Actions 和 rollback；
- cards、candidates、import records 和 skill registries 都是可检查文件；
- 自动维护可以提交 proposals，GitHub 负责 history 和 review；
- 如果自动化改坏了，可以用普通 Git 历史回滚。

对很多团队来说，private repository 已经是最简单可靠的共享 agent memory backend。

## 安装和检查

Windows release 包含预览版 desktop app：

- 从 [GitHub Releases](https://github.com/liuyingxuvka/Khaos-Brain/releases/latest) 下载 `KhaosBrain.exe`；
- 按你的 agent 使用的本地 skill/runtime 路径运行安装或仓库 setup；
- 依赖 retrieval 前先运行 health check。

仓库本地检查：

```powershell
python scripts\install_codex_kb.py --check --json
```

Desktop viewer：

```powershell
python scripts\open_khaos_brain_ui.py
```

## 它需要什么样的 AI Agent

开箱支持的 host 是 Codex，因为 Codex 支持：

- `AGENTS.md` 这类仓库级说明；
- skills 和 preflight invocation；
- 本地脚本执行；
- automations 和 scheduled runs；
- GitHub / filesystem workflows；
- post-task observation 和 write-back。

其他 AI host 如果能在工作前读取经验、工作后写回证据、加载可复用 workflow、运行本地维护脚本，并安全读写 Git 仓库，也可以适配这个结构。

## 公开边界

这个公开仓库包含 Khaos Brain 源码、示例、schemas、安装/检查脚本、UI assets、screenshots、public-safe Skill material 和空 KB scaffold。

它不包含用户私人 KB、真实本地 history、credential、私人 candidate cards、个人偏好、组织 secret、真实客户数据或未公开本地记忆。公开 screenshots 使用安全演示内容。

## 仓库结构

```text
local_kb/              核心包、retrieval、cards、maintenance、desktop UI
.agents/skills/        retrieval、maintenance、organization flow 和 UI launch 的 Codex skills
kb/                    public-safe KB scaffold 和 taxonomy 示例
schemas/               card/schema 示例
scripts/               install、check、launch 和 maintenance helpers
templates/             template artifacts
assets/                icons、screenshots 和 README hero assets
docs/                  architecture、maintenance、organization、release 和 UI docs
tests/                 regression tests
VERSION                当前公开版本
CHANGELOG.md           发布历史
```

## 许可证

MIT. See [`LICENSE`](./LICENSE).
