# Model-Miss Review Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-model-miss-review`.

Load:
`.agents/skills/flowguard-model-miss-review/references/model_miss_protocol.md`

Use this route when runtime, tests, replay, logs, manual validation, or
production evidence fails after FlowGuard modeling passed, or when a repaired
bug needs same-class model representation before confidence is widened.

Keep the hard gates: separate bug instance from bug class, represent or scope
same-class responsibility, feed boundary changes to the affected mesh or
alignment route, and rerun relevant evidence before broad claims.
