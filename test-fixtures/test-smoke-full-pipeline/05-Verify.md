---
tof:
  run_id: "smoke"
  phase: "verify"
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: "fake"
    assigned_model: "deepseek-v4-pro"
    claimed_model: "deepseek-v4-pro"
    assigned_family: "deepseek"
    actual_family: "deepseek"
  inputs:
    - phase: "establish"
      path: "02-Establish.md"
      sha256: "1f72f568e2689c26a350b3b3b057f764b1301f3787392a916d29181fa2b6fa10"
    - phase: "implement"
      path: "04-Implement.md"
      sha256: "732051e5cebd36751decc83892b8fe79cef8254a7d754295f9170a8450f9ed7e"
verify:
  verdict: "PASS"
  mismatches: []
  vf_results: []
---
