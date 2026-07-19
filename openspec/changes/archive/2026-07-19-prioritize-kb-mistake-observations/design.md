## Context

The predictive KB integration has three prompt surfaces that shape normal task behavior: the installed skill text, the global AGENTS managed defaults block, and the implicit OpenAI skill prompt. The current surfaces require KB postflight and support contrastive fields, but the highest-value error and correction signal is not named as the first thing Codex should look for.

The repository also has an installer check that verifies broad postflight, skill/plugin, subagent/delegation, and phase-checkpoint wording. It does not currently verify mistake-priority wording, so a future install or template edit could silently lose this behavior.

## Goals / Non-Goals

**Goals:**
- Make Codex's own mistakes, weak paths, missed instructions, validation failures, tool or skill misuse, user corrections, and revised actions the highest-priority KB postflight evidence.
- Keep successful reusable patterns recordable.
- Add install-check and test coverage so the new priority survives reinstall and cross-machine setup.
- Keep the implementation minimal and auditable.

**Non-Goals:**
- Do not change the observation schema.
- Do not suppress successful observations.
- Do not rewrite existing history, candidates, trusted cards, or consolidation output.
- Do not add a new dependency or broad OpenSpec/FlowGuard integration layer.

## Decisions

- Put the rule in prompt templates first. This is the narrowest effective boundary because the issue is agent judgment at postflight time, not storage capacity.
- Verify the rule in installer checks. Prompt text without a health check can drift on another machine; a checklist item makes the install status visible.
- Use phrase-level checks for `mistake`, `weak path`, `correction`, and `highest-priority` wording. This keeps the installer deterministic and consistent with existing checks.
- Use a small FlowGuard model for the postflight decision flow. The model should prove the intended priority relation: when both mistake evidence and success evidence exist, mistake evidence remains selected as highest priority while success evidence remains allowed.

## Risks / Trade-offs

- Prompt wording can become too long -> keep the new sentence short and use the same markers in every installed surface.
- Installer phrase checks can be brittle -> check stable marker concepts rather than full paragraphs.
- FlowGuard can over-model a prompt-only change -> use a finite, focused model of the decision rule rather than modeling all KB maintenance.

## Migration Plan

1. Update repository prompt templates and local-kb workflow wording.
2. Add installer checklist checks and tests.
3. Add and run the focused FlowGuard model.
4. Run targeted tests and install check.
5. Rerun the installer so the local Codex installation receives the updated prompt surfaces.
