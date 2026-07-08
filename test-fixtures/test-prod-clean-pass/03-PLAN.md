---
tof:
  run_id: "prod-clean-pass"
  phase: "establish"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "gpt-5.5"
    claimed_model: "gpt-5.5"
    assigned_family: "gpt"
    actual_family: "gpt"
  inputs:
    - phase: "clarify"
      path: "01-TASK.md"
      sha256: "895e5113d91962997fb761afd648d93e8c9e2f1c034469dca5a971617704ff42"
    - phase: "scout"
      path: "02-RESEARCH.md"
      sha256: "383700f015c7ef28e61a452a1ec6f2b620e643ebdbafa8207db4832053740fae"
establish:
  verdict: "READY"
  architecture: "Simple module"
  steps: ["Add types", "Add parser"]
  verification_functions: ["test_basic"]
  rollback: "revert"
  out_of_scope: ["perf"]
  execution_mode: "sync"
---
