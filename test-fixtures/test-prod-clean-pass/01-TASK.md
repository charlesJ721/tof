---
tof:
  run_id: "prod-clean-pass"
  phase: "clarify"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "deepseek-v4-flash"
    claimed_model: "deepseek-v4-flash"
    assigned_family: "deepseek"
    actual_family: "deepseek"
  inputs: []
task:
  verdict: "READY"
  scope: "Test review.blocking=[] with production schema"
  success_criteria: ["Review PASS with empty blocking list"]
  explicit_exclusions: ["None"]
  constraints: ["Production pipeline.yaml"]
---
