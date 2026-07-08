---
tof:
  run_id: "test-04"
  phase: "review"
  schema_version: "0.1"
  round: 3
  produced_by:
    adapter: "fake"
    assigned_model: "gemini-3.1-pro-preview"
    claimed_model: "gemini-3.1-pro-preview"
    assigned_family: "gemini"
    actual_family: "gemini"
  inputs:
    - phase: "establish"
      path: "02-Establish-EstModel.md"
      sha256: "e0b2652345ac1f5ea76483fb1466587933b3e1bf9ee7e1d7031eff507e033bce"
review:
  verdict: "BLOCKING"
  findings:
    - type: "design_flaw"
      severity: "high"
      description: "Still missing error handling (round 3)"
  blocking:
    - "Add error handling"
---
