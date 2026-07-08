---
tof:
  run_id: "test-b"
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
      path: "pipeline.yaml"
      sha256: "4fab316d9008aa35aba9bd69fd0ad81574031829608a3ec1f2d3ede6f0d18e05"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks good"
---
