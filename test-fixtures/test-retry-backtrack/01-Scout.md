---
tof:
  run_id: "retry-backtrack"
  phase: "scout"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-opus-4.8"
    claimed_model: "claude-opus-4.8"
    assigned_family: "claude"
    actual_family: "claude"
  inputs: []
scout:
  verdict: "PASS"
  affected_files: ["orchestrator.py"]
  verification_functions: ["test_loop"]
  risk_areas: ["retry logic"]
  unknowns: ["multi-round backtrack correctness"]
---
Scout body v1.
