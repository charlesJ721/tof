---
tof:
  run_id: "trigger-layer-review-2026-07-07"
  phase: review
  round: 1
  reviewer: "openai/gpt-5.5"
  reviewed_range: "e38a2c2..ec138af"
  created_at: "2026-07-07T13:48:07Z"
review:
  verdict: WEAKNESS_FOUND
  findings:
    - type: ci_guardrail
      severity: high
      description: ".github/workflows/review-required.yml accepts any pre-existing TOF/REVIEW.md or REVIEW.md when the current diff does not include a review file, so later core-file pushes can pass with a stale review artifact rather than an accompanying family-different review."
      evidence: "review-required.yml lines 49-58: after checking git diff for REVIEW.md, the workflow falls back to any existing TOF/REVIEW.md or REVIEW.md in the checked-out tree."
      recommendation: "Require REVIEW.md to be changed in the same diff for core-file changes, or validate that the review artifact references the current HEAD/range. Do not fall back to an unchanged repository file."
    - type: dispatch_command_quoting
      severity: medium
      description: "dispatch.command_template quoting is brittle: _build_dispatch_command shlex-quotes the prompt and then substitutes it inside a template that already surrounds {prompt} with double quotes. Prompts containing apostrophes can raise ValueError, and even simple prompts are passed with literal quote characters."
      evidence: "orchestrator.py lines 337-344 plus pipeline.yaml line 48. Reproduction: _build_dispatch_command(..., \"Bob's task\", ...) raises ValueError: No closing quotation."
      recommendation: "Do not nest shell quoting. Prefer argv templates or substitute an unquoted prompt into an argv list; if keeping a shell-like template, remove the literal quotes around {prompt} and add tests for apostrophes/newlines."
    - type: ledger_test_isolation
      severity: low
      description: "The execution ledger path is hardcoded to ~/.hermes/tof-execution-ledger.jsonl, so tests or local dry runs mutate real operator telemetry and triage-stats output. This does not break runtime behavior, but it weakens ledger usefulness."
      evidence: "orchestrator.py line 20 and tof line 1487 define fixed ledger paths; running the integration tests appended full-seri entries visible via tof triage-stats."
      recommendation: "Allow TOF_LEDGER_PATH or an injected ledger path for tests, defaulting to ~/.hermes/tof-execution-ledger.jsonl for normal use."
  blocking: []
---

# TOF Review — trigger-layer changes e38a2c2..ec138af

## Verdict

**WEAKNESS_FOUND** — the trigger-layer design mostly satisfies the imposed architectural constraints, but I found three concrete weaknesses before this should be treated as a reliable guardrail/telemetry layer.

## Scope reviewed

- `orchestrator.py`: `run(..., only_phase=...)`, `run_triage()`, execution ledger helpers, metadata/audit path, upstream artifact discovery.
- `tof`: `run --only`, `triage`, `triage-stats`, `phase_items()` triage exclusion.
- `pipeline.yaml`: standalone `triage` phase insertion.
- `phases/triage/prompt.md`: adversarial routing advisor prompt.
- `.github/workflows/review-required.yml`: CI review-required guardrail.

## Positive assessment

- `tof run --only <phase>` is intentionally single-dispatch: it creates a dispatch pipeline with `timeout_policy.max_retries=0`, dispatches one phase, audits metadata, validates once, and returns. I did not see phase cascade or mini-SERI behavior in this path.
- `run_triage()` correctly avoids `_dispatch_ot()`, does not create a run directory artifact, and does not write session provenance metadata. It is advisory-only by construction.
- The ledger write is best-effort and fail-soft (`try/except Exception: pass`), matching the stated constraint that ledger failure must not break TOF runs.
- The triage prompt is narrow and explicitly asks for the cheapest route that addresses a concrete blind spot, which is aligned with the trigger-layer goal.
- `phase_items()` excludes `triage`, preventing the advisory phase from becoming part of the main validator DAG.

## Findings

### 1. CI guardrail can pass stale reviews (high)

The workflow checks whether a `REVIEW.md` appears in the current diff, but if none is changed it falls back to any existing `TOF/REVIEW.md` or root `REVIEW.md` in the repository. That means a later push touching `TOF/orchestrator.py`, `TOF/tof`, `TOF/pipeline.yaml`, adapters, or `TOF/phases/**` can pass without updating the review artifact, as long as an old review file already exists.

This conflicts with the stated purpose: core-file changes must be **accompanied** by a family-different review. Presence is not accompaniment.

Recommended fix: remove the fallback-to-existing-file branch, or require the review frontmatter to name the current `BASE..HEAD` range / current HEAD SHA and check that in CI.

### 2. `dispatch.command_template` prompt quoting is brittle (medium)

`_build_dispatch_command()` applies `shlex.quote(prompt)` and substitutes that into the template. The default template in `pipeline.yaml` already quotes `{prompt}`:

```yaml
dispatch:
  command_template: 'hermes chat -q "{prompt}" --provider {provider} --model {model}'
```

This double quoting produced two problems under direct reproduction:

- `hello world` becomes an argv item containing literal quote characters: `"'hello world'"`.
- `Bob's task` raises `ValueError: No closing quotation` during `shlex.split()`.

This affects both normal dispatch and `tof triage`, because triage uses the same `_build_dispatch_command()` helper. It is not a mini-SERI violation, but it is a real reliability bug in the trigger layer.

Recommended fix: treat command templates as argv templates rather than shell strings, or remove the literal quotes around `{prompt}` in `pipeline.yaml` and add regression tests for apostrophes, quotes, and multiline prompts.

### 3. Ledger telemetry is not test-isolated (low)

The ledger is hardcoded in both `orchestrator.py` and `tof` to `~/.hermes/tof-execution-ledger.jsonl`. Because `run()` now writes the ledger unconditionally on terminal paths, integration tests and local dry runs mutate the user's real ledger. I observed `tof triage-stats` reporting entries created by local test execution.

This does not violate the best-effort/silent-failure requirement. It does weaken the accuracy of `triage-stats` as operational telemetry.

Recommended fix: support `TOF_LEDGER_PATH` or injection for tests, with the current path as the production default.

## Constraint check

| Constraint | Assessment |
|---|---|
| `--only` must not become mini-SERI | **Pass.** Single dispatch, no phase cascade; retries are disabled for the dispatch path. |
| `run_triage` must not use `_dispatch_ot` | **Pass.** It builds a command directly and returns parsed JSON only. |
| Ledger must be best-effort | **Pass.** Ledger write is fail-soft. |
| CI guardrail scope must be narrow | **Partially pass.** Path scope is narrow, but the stale-review fallback weakens enforcement. |

## Validation performed

Commands run from `/Users/ArsLonga/Projects/hermes-kit/TOF`:

```bash
python3 -m py_compile orchestrator.py tof
python3 tof lint-pipeline
python3 tests_expected.py
python3 test_orchestrator_unit.py
python3 test_orchestrator_integration.py
python3 tof --help
python3 tof run --help
python3 tof triage-stats
```

Results: lint passed, expected fixture semantics passed, 26 unit tests passed, and 4 integration tests passed. The quoting issue was found with a targeted direct call to `_build_dispatch_command()`.
