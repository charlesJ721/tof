---
tof:
  run_id: "test-a"
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
      path: "01-Scout-Model.md"
      sha256: "b41b1515d42c2ccd5c6a76690e2d7347a41c716cd9b360f528f2fab1621d0256"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks good"
---
