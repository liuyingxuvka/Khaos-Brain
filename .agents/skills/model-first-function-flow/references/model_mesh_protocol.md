# ModelMesh Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-model-mesh`.

Load:
`.agents/skills/flowguard-model-mesh/references/model_mesh_protocol.md`

Use this route when three or more local models, an oversized model, stale child
evidence, parent/child model partitioning, target split derivation, or affected
sibling review controls the confidence claim.

Keep the hard gates: inventory child evidence ids, prove freshness, avoid
expanding every child state graph, reattach repaired children to the parent,
and treat background progress as liveness until final artifacts and exit status
exist.
