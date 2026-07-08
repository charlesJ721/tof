---
tof:
  run_id: "test-01"
  phase: "scout"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-sonnet-4"
    claimed_model: "claude-sonnet-4"
    assigned_family: "claude"
    actual_family: "claude"
  inputs: []
scout:
  verdict: "PASS"
  affected_files: ["src/main.py"]
  dependency_graph: "none"
  verification_functions: ["test_basic"]
  risk_areas: ["auth module has no error handling"]
  unknowns: []
  implicit_dependencies: ["logging module"]
---
