---
tof:
  run_id: "test-03"
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
      path: "02-Establish-EstModel.md"
      sha256: "5a3ea70f59c9141cbbf2bc39368ed6a429f6a5ab4354a1c2f352b47f7af52de0"
review:
  verdict: "BLOCKING"
  findings:
    - type: "design_flaw"
      severity: "high"
      description: "Missing error handling"
  blocking:
    - "Add error handling"
---
