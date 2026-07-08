---
tof:
  run_id: "test-06"
  phase: "establish"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-sonnet-4"
    claimed_model: "claude-sonnet-4"
    assigned_family: "claude"
    actual_family: "claude"
  inputs: []
plan:
  verdict: "READY"
  architecture: "simple arch"
  steps: ["step 1"]
  verification_functions: ["test_basic"]
  rollback: "revert"
  out_of_scope: ["perf"]
  execution_mode: "sync"
---
