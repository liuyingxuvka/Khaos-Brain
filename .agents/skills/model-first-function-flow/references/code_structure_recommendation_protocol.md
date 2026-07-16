# Code Structure Recommendation Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-code-structure-recommendation`.

Load:
`.agents/skills/flowguard-code-structure-recommendation/references/code_structure_recommendation_protocol.md`

Use this route when the user asks for a code architecture recommendation, or
when a functional model exists and the next safe step is a module, function,
facade, adapter, side-effect, or validation-boundary plan instead of production
code edits.

Keep the hard gates: recommendations stay model-derived, do not mutate
production code, keep facade and validation boundaries explicit, and route
actual large splits through StructureMesh.
