---
tof:
  run_id: "smoke"
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
      path: "02-Establish.md"
      sha256: "1f72f568e2689c26a350b3b3b057f764b1301f3787392a916d29181fa2b6fa10"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "No issues found"
---
