---
tof:
  run_id: "test-self"
  phase: "review"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "gemini-3.1-pro-preview"
    claimed_model: "gemini-3.1-pro-preview"
    assigned_family: "gemini"
    actual_family: "gemini"
  inputs:
    - phase: "establish"
      path: "02-Establish-Model.md"
      sha256: "e6637cc164d3ac88b9905d7b6dce0cd1b7b980584afcebf1d2035ff1ce809041"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks good"
---
