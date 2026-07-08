---
tof:
  run_id: "test-h"
  phase: "review"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-opus-4.8"
    claimed_model: "claude-opus-4.8"
    assigned_family: "claude"
    actual_family: "claude"
  inputs: [{phase: "establish", path: "02-Establish.md", sha256: "25daa61cfd5b60299e20c2804d4e3e01357c42a7405ea9596a060c1630cb3eb0"}]
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "OK"
---
