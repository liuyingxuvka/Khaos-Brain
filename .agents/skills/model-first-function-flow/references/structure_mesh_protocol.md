# StructureMesh Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-structure-mesh`.

Load:
`.agents/skills/flowguard-structure-mesh/references/structure_mesh_protocol.md`

Use this route when a large script, module, package, command, public API,
facade, config surface, or compatibility boundary is being split across child
modules.

Keep the hard gates: derive target structure from a FlowGuard model, preserve
public entrypoint compatibility, expose dependency and ownership conflicts, and
require parity evidence before claiming behavior-preserving structure changes.
