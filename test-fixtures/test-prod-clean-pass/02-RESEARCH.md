---
tof:
  run_id: "prod-clean-pass"
  phase: "scout"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "claude-opus-4.8"
    claimed_model: "claude-opus-4.8"
    assigned_family: "claude"
    actual_family: "claude"
  inputs:
    - phase: "clarify"
      path: "01-TASK.md"
      sha256: "895e5113d91962997fb761afd648d93e8c9e2f1c034469dca5a971617704ff42"
scout:
  verdict: "PASS"
  affected_files: ["src/main.py"]
  dependency_graph:
    "src/main.py":
      depends_on: []
  verification_functions: ["test_basic"]
  risk_areas: ["YAML"]
  unknowns: ["Nested includes"]
  implicit_dependencies: ["Python >= 3.9"]
---
