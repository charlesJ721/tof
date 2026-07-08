---
tof:
  run_id: "test-self"
  phase: "scout"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-sonnet-4"
    claimed_model: "claude-sonnet-4"
    assigned_family: "claude"
    actual_family: "claude"
  inputs:
    - phase: "clarify"
      path: "00-Clarify-Model.md"
      sha256: "2539669ebd84a98539d2d236df406da8a34c6b2ef2a4db63ae854e0648a248ec"
scout:
  verdict: "PASS"
  unknowns: ["something unknown"]
---
