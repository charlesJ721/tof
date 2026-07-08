# Implementation Status — 2026-07-07 (P1.3 complete)

> What works today, what's deferred, and what's out of scope.

## Version Mapping

| Label | Meaning | Date |
|-------|---------|------|
| pipeline.yaml:0.1 | Schema version (not framework version) | — |
| P0.1-P0.3 | Runtime hardening: 5-check chain, session audit, config snapshot | 2026-07-03/04 |
| P1.1-P1.3 | Execution layer: orchestrator tests, dispatch template, provenance | 2026-07-07 |
| P2.x | Test fidelity: production schema, retry backtrack, allow_empty | 2026-07-07 |
| v2.1 (skill) | TOF specification version in task-orchestration-framework SKILL.md | — |
| v4 hardening | Post-P0.3 config split-brain fix + production validations | 2026-07-05 |

Current effective version: **P1.3** (all P0+P1 gates mechanical, orchestrator tested).

## Test Coverage (48 tests)

| Suite | Count | Covers |
|-------|-------|--------|
| tests_expected.py | 17 fixtures | tof validate: 5 checks + cascade + retry + backtrack |
| test_orchestrator_unit.py | 26 tests | _preprocess_prompt, _extract_response_body, _inject_artifact_shas, _build_upstream_context, _snapshot_configs |
| test_orchestrator_integration.py | 4 tests | dispatch→validate→receipt loop, INVALID detection, provenance check |
| tof lint-pipeline | 1 | pipeline.yaml consistency |

## MECHANICAL — Enforced by `tof validate`

| Constraint | Mechanism | Since |
|-----------|-----------|-------|
| Schema validation | `validate_schema()` — required_fields, required_if_verdict, allow_empty, echo detection | P0.1 |
| Input lineage | Path+phase+SHA256 resolution, required/required_if_present | P0.2a |
| Stale downstream detection | Global artifact truth, cascade | P0.2a |
| Model family diversity | `family_must_differ_from` — registry-backed | P0.1 |
| Model family consistency | `actual_family` must match registry; session audit cross-check | P0.2b, P0.2 |
| Session audit provenance gate | Rejects fixture/unverified/self_reported evidence; `--allow-untrusted-audit` bypass | P0.1 |
| actual-vs-assigned cross-check | For trusted methods, validates actual_model == assigned_model | P0.1b |
| Family override from metadata | Session audit actual_family overrides artifact self-report | P0.2 |
| Provenance hash | Artifact body must appear in OT stdout (FM-1 defense) | P1.3 |
| Retry budget | `>=max_rounds` → escalation | P0.1 |
| Config source tracking | Receipt embeds pipeline/models path+SHA256 | P0.3 |
| Config split-brain prevention | Orchestrator snapshots configs to .tof/ before run | P0.3 |
| Model slug pre-dispatch gate | Validates slug against models.yaml + provider freshness | P0.3 |

## BEHAVIORAL — Documented protocol, not enforced by code

| Protocol | Documented in | Notes |
|----------|-------------|-------|
| STATE_LOCKER | SKILL.md §0.1 | UX protocol for manual supervision workflows |
| Orchestrator behavior boundaries | SKILL.md §安全沙箱层 | What orchestrator may/may not do |
| Phase EX escalation | SKILL.md §Phase EX | Human-in-the-loop escalation path |
| Constitution review | SKILL.md §0.2 | Design constitution enforcement |
| Knowledge Deposition | SKILL.md §Phase 5.5 | Five-channel check |

## Known Gaps

| Gap | Severity | Status |
|-----|----------|--------|
| verify.mismatches empty list required allow_empty | Low | Fixed (P2.x) |
| required_if_present circular SHA problem | Low | Documented; forward-flow workaround |
| cascade fail-closed granularity | Low | BLOCKING does not cascade; fine for now |
| orchestrator depends on hermes CLI (default template) | Low | Template override available via dispatch.command_template |
| model_registry_adapter uses personal proxy as fallback | Low | TOF_OPENROUTER_PROXY env var override available |
| memory_dreaming_adapter removed from repo | Resolved | Sanitized per CONVENTIONS.md; personal tool, not framework |
