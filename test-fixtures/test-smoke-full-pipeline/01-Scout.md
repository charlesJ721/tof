---
tof:
  run_id: "smoke"
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
      path: "00-Clarify.md"
      sha256: "f3251f67aaf4a0f5e134a9604d77e6b30fe3015b85667e27b33efa53c1fee6f4"
scout:
  verdict: "PASS"
  unknowns: ["module X has undocumented side effects"]
---
