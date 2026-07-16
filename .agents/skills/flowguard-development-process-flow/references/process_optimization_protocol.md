# Conditional Process Optimization

Use this reference only when one of these reasons is present:

- `explicit_request`
- `multiple_equivalent_routes`
- `material_rework_risk`
- `diagnostic_boundary_choice`

Otherwise return `not_needed` and create no optimization records.

## Hard Equivalence Before Preference

Compare candidates only after they match on all six boundaries:

1. terminal outcome;
2. required obligations and evidence/claim boundary;
3. safety and hard invariants;
4. protected side effects;
5. dependency authority;
6. execution-owner authority.

A mismatch is a rejection, not a cost tradeoff.

## Two Composable Choices

Choose one diagnostic boundary:

- `targeted`: the smallest informative affected boundary;
- `declared_complete`: every item in a named finite boundary;
- `budgeted`: a named time, cost, or side-effect limit, with remainder visible.

Choose one execution mode:

- `sequential`;
- `safe_parallel`, only with current dependency, mutable-state, side-effect,
  and execution-owner isolation evidence.

A hard blocker universally stops invalid descendants. Material new evidence
universally stales the decision. Neither needs to be a selectable strategy.

## Evidence And Selection

The decision lists its current evidence ids. Candidate comparison, isolation,
repair relations, ownership, and revalidation references must all resolve
within that current evidence boundary.

Prefer evidence-backed lower repeated work, duplicated validation,
coordination, or side-effect exposure. Qualitative or estimated comparison may
support `preferred within declared candidates`. Only measured costs across an
exhausted named finite set may support `minimum within that finite set`.
Never claim a global optimum.

## Repair And Revalidation

TestMesh supplies the diagnostic boundary and execution evidence. Finding
Ledger supplies raw ids. Several findings enter one `ProcessRepairGroup` only
with relation evidence and a falsifiable root-cause claim. Use ordinary
Model-Test Alignment evidence for affected obligations, the primary code
owner, and tests. The group remains open until all required affected
revalidation ids are current.

## Original Example

When several related tests are cheap and valid, finish a declared diagnostic
boundary before editing so one underlying defect can be repaired once. When a
missing prerequisite or safety failure makes later tests invalid, stop and
record them as not run. This preserves the user's goal without making
"run every test first" a universal rule.

## Public Shape

The existing DPF route exposes five records and one review:

- `ProcessOptimizationContract`
- `ProcessOptimizationCandidate`
- `ProcessRepairGroup`
- `ProcessOptimizationDecision`
- `ProcessOptimizationReport`
- `review_process_optimization`

Do not add another route, skill, commitment, model owner, compatibility
reader, or alternate success vocabulary.
