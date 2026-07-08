---
tof:
  run_id: "test-05"
  phase: "review"
  schema_version: "0.1"
  round: 1
  next_allowed: "implement"
  produced_by:
    adapter: "fake"
    assigned_model: "gemini-3.1-pro-preview"
    claimed_model: "gemini-3.1-pro-preview"
    assigned_family: "gemini"
    actual_family: "gemini"
  inputs:
    - phase: "establish"
      path: "02-Establish-EstModel.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks fine"
  blocking: []
---
