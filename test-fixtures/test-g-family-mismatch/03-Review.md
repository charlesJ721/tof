---
tof:
  run_id: "test-g"
  phase: "review"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-opus-4.8"
    claimed_model: "claude-opus-4.8"
    assigned_family: "claude"
    actual_family: "gemini"
  inputs: [{phase: "establish", path: "02-Establish.md", sha256: "aa2f4ae14d5d17a6069c0bde27d9a3583e286b3e423c42477b89057ca1f005bd"}]
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "OK"
---
