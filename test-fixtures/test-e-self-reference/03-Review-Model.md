---
tof:
  run_id: "test-e"
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
      path: "03-Review-Model.md"
      sha256: "b015a28e5ba0b604285b935bc23a0daea252382eb15d9380581fbffd08b530d8"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks good"
---
