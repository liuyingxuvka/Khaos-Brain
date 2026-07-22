## Context

SkillGuard now separates author-maintenance state from consumer distribution
and provides explicit evidence-store audit and garbage-collection planning.
This repository has the correct domain boundary already: each of the five
skills is a single-member maintenance unit with five target-declared checks.
The mismatch is control-plane freshness, not target depth.

A separately modified KB retrieval model is present in the worktree and owned
outside this change. It must remain byte-identical throughout this work.

## Goals / Non-Goals

**Goals:**

- Adopt the current author-only repository shape without changing the five
  target contracts.
- Preserve exactly five units and twenty-five unique check/owner/subject
  bindings.
- Regenerate deterministic compiler outputs and prove source-only parity.
- Exercise read-only evidence audit and GC planning against a new isolated
  author evidence root.
- Keep all KB business state and native maintenance execution untouched.

**Non-Goals:**

- No new target obligation, check, route, rubric, or depth criterion.
- No Sleep, Dream, organization-maintenance, contribution, Architect, or
  manual-update execution.
- No reading or writing `kb`, `kbrb`, or `kbtx` business evidence for proof.
- No evidence quarantine/purge, consumer installation, Git commit, push, tag,
  or release.

## Decisions

1. The five existing `contract-source.json` files remain the sole target-owned
   declarations. Their semantic inventory is frozen before compiler output is
   regenerated.
2. SkillGuard `maintainer-adopt` owns the current author prompt and manifest.
   It receives only the five explicit source paths and their declared native
   owners; it cannot infer membership by scanning consumer skills.
3. The current compiler owns only `compiled-contract.json` and
   `check-manifest.json`. Source-only checks prove deterministic parity,
   positive/shallow calibration, disjoint test-node ownership, and clean
   consumer projection without launching a native maintenance run.
4. Evidence lifecycle is demonstrated in a fresh root under the repository's
   author work area. `evidence-audit` and `evidence-gc-plan` may read that root;
   apply and purge remain explicitly out of scope.
5. Full target execution depth is not claimed. The native receipt validators
   require a concrete Sleep/Dream/organization/update run, which this change
   is forbidden to start. Source maintenance can close only its narrower
   author-control claim.

## Risks / Trade-offs

- [Generated contracts change broadly] -> Diff only compiler-owned files and
  prove the source contracts, check count, owners, subjects, and obligations
  are unchanged.
- [Old evidence remains large] -> Produce a snapshot-bound read-only plan for
  the isolated demonstration root only; do not infer that historical shared
  evidence is safe to delete.
- [A peer changes protected KB state] -> Recheck its exact SHA-256 fingerprint
  before and after every stateful phase and stop on mismatch.
- [Source-only proof is mistaken for production completion] -> Keep the claim
  boundary explicit in OpenSpec, FlowGuard output, and final reporting.

## Migration Plan

Upgrade the FlowGuard project record, adopt the current SkillGuard author
shape, regenerate the ten derived files, run exact source-only and OpenSpec
checks, run the new FlowGuard model, audit/plan the isolated evidence root, and
finish with protected-file and worktree verification. No activation or release
step follows.
