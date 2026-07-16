# TestMesh Handoff

This kernel-side file is a compact handoff stub. The detailed protocol is
owned by the direct satellite skill `flowguard-test-mesh`.

Load:
`.agents/skills/flowguard-test-mesh/references/test_mesh_protocol.md`

Use this route when validation is too large, slow, layered, backgrounded,
stale-prone, release-only, or parent/child suite-owned to trust as one flat
test command, including large transition or artifact-payload case matrices.

Keep the hard gates: child suites own explicit validation partitions, evidence
freshness is checked before confidence, hidden skips and timeouts remain
visible, payload case ids stay owned, and final long-check artifacts are
required before pass claims.
