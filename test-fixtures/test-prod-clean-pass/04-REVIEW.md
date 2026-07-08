---
tof:
  run_id: "prod-clean-pass"
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
    - phase: "scout"
      path: "02-RESEARCH.md"
      sha256: "383700f015c7ef28e61a452a1ec6f2b620e643ebdbafa8207db4832053740fae"
    - phase: "establish"
      path: "03-PLAN.md"
      sha256: "3eeb4605c48e16efadaa0e60df3c6a1d20837e9cf7d7de911225c48b4ef7f58b"
review:
  verdict: "PASS"
  findings:
    - type: "minor"
      severity: "low"
      description: "Looks fine"
  blocking: []
---
