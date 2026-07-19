## 1. Contract and Model

- [x] 1.1 Align writer-lock, terminal, and launcher timeout constants with explicit headroom.
- [x] 1.2 Extend the existing FlowGuard postflight model to license success only for correctly ordered budgets and sole-owner execution.
- [x] 1.3 Update the predictive-KB author skill, install templates, and currentness expectations with same-event timeout handling.

## 2. Affected Verification

- [x] 2.1 Add focused runtime, FlowGuard, CLI, and installation regression assertions for timeout ordering and installed guidance.
- [x] 2.2 Run only the affected OpenSpec, FlowGuard, postflight, template, and installer checks; fix any failures.

## 3. Activation and Release

- [x] 3.1 Update v0.6.7 release notes, install the frozen source transactionally, and verify the installed current projection.
- [x] 3.2 Freeze the implementation and prepare the source-only v0.6.7 publication inputs.
- [x] 3.3 Validate the completed OpenSpec change is ready to archive into the canonical specification before the single final `main` validation.
