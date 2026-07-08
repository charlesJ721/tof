---
tof:
  run_id: "retry-backtrack"
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
      path: "01-Scout.md"
      sha256: "c2ad116c68a0c8665e552ec509bc0d1612dc6bacaa163c475467b27fc518be30"
    - phase: "establish"
      path: "02-Establish-v1.md"
      sha256: "29e80fcfae3957aabc19136c93abb52f14154056b5979117abbfc7b25b6299c9"
review:
  verdict: "BLOCKING"
  findings:
    - type: "HIGH"
      severity: "critical"
      description: "Design v1 has critical flaw"
  blocking:
    - "Architecture must be redesigned"
---
Review v1 body.
