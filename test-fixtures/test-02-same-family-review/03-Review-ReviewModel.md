---
tof:
  run_id: "test-02"
  phase: "review"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-opus-4.8"
    claimed_model: "claude-opus-4.8"
    assigned_family: "claude"
    actual_family: "claude"
  inputs:
    - phase: "establish"
      path: "02-Establish-EstModel.md"
      sha256: "aff8c834d9d1ad24b144cdfb6dfc37f480d055016cde549e8f6ebcd3edd8c80f"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks fine"
  blocking: []
---
