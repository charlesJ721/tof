---
tof:
  run_id: "test"
  phase: "scout"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-sonnet-4"
    claimed_model: "claude-sonnet-4"
    assigned_family: "claude"
    actual_family: "claude"
  inputs: [{phase: "clarify", path: "00-Clarify.md", sha256: "3d87c8c8bdf6c83616bdbc174a3fb1070a036b1a98d3477fe52973f3f1b28923"}]
scout:
  verdict: "PASS"
  unknowns: ["test"]
---
