#!/usr/bin/env python3
"""Temporary expectation runner for TOF fix batch; kept in repo as executable smoke tests."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOF = ROOT / "tof"
CASES = {
    # P0.1 fixtures
    "test-01-missing-unknowns": ("INVALID", [], {}),
    "test-02-same-family-review": ("INVALID", [], {}),
    "test-03-blocking-with-retry": ("BLOCKING", ["establish"], {}),
    "test-04-retry-exhausted": ("BLOCKING", ["escalation"], {}),
    "test-05-sha-mismatch-and-claims-next-warning": ("INVALID", [], {
        "input_linkage": "BLOCKING",  # SHA mismatch triggers INVALID
        # schema=BLOCKING: local pipeline has blocking in required_fields (old schema)
        # next_allowed="implement" in artifact → ignored (warning, non-fatal)
    }),
    "test-06-hash-mismatch": ("INVALID", [], {}),
    # P0.2a fixtures
    "test-a-path-mismatch-phase": ("INVALID", [], {"input_linkage": "BLOCKING"}),
    "test-b-path-pipeline-yaml": ("INVALID", [], {"input_linkage": "BLOCKING"}),
    "test-c-stale-downstream": ("INVALID", [], {"stale": "BLOCKING"}),
    "test-d-invalid-upstream-no-stale": ("PASS", [], {}),
    "test-e-self-reference": ("INVALID", [], {"input_linkage": "BLOCKING"}),
    "test-f-no-path-sha-match": ("PASS", [], {"input_linkage": "PASS"}),
    # P0.2b fixtures
    "test-g-family-mismatch": ("INVALID", [], {"model_policy": "BLOCKING"}),
    "test-h-family-match": ("PASS", [], {"model_policy": "PASS"}),
    # Multi-round retry backtrack — resolve_current_attempt test
    # Review v1 BLOCKING → Establish v2 → Review v2 PASS
    "test-retry-backtrack": ("PASS", [], {
        "schema": "PASS",
        "input_linkage": "PASS",
        "model_policy": "PASS",
    }),
    # Smoke test — full 6-phase pipeline
    "test-smoke-full-pipeline": ("PASS", [], {}),
    # Production schema fixture — verifies review.blocking=[]
    # under required_if_verdict (Round 2 Bug #1 fix validation).
    # Now PASS: required_if_present removed from establish (round 3 fix).
    "test-prod-clean-pass": ("PASS", ["implement"], {
        "schema": "PASS",
        "input_linkage": "PASS",
        "model_policy": "PASS",
    }),
}

failures = []
for name, (status, next_allowed, check_checks) in CASES.items():
    cmd = [str(TOF), "validate", "--allow-untrusted-audit"]
    if name == "test-prod-clean-pass":
        cmd.extend(["--pipeline", str(ROOT / "pipeline.yaml"),
                    "--models", str(ROOT / "models.yaml")])
    cmd.append(str(ROOT / "test-fixtures" / name))
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        failures.append(f"{name}: default exit {proc.returncode}, expected 0; stderr={proc.stderr!r}")
        continue
    try:
        validation = json.loads(proc.stdout)["validation"]
    except Exception as exc:
        failures.append(f"{name}: invalid json {exc}; stdout={proc.stdout!r}")
        continue
    if validation.get("status") != status:
        failures.append(f"{name}: status {validation.get('status')} != {status}")
    if validation.get("next_allowed") != next_allowed:
        failures.append(f"{name}: next_allowed {validation.get('next_allowed')} != {next_allowed}")
    if status == "INVALID" and validation.get("required_action") != "rerun_current_phase":
        failures.append(f"{name}: INVALID missing required_action=rerun_current_phase")
    # Optional per-fixture check assertions
    for ck, cv in check_checks.items():
        actual = validation.get("checks", {}).get(ck)
        if actual != cv:
            failures.append(f"{name}: checks.{ck}={actual} != {cv}")

FAIL_ON = [
    (["--allow-untrusted-audit", "--fail-on", "invalid"], "test-01-missing-unknowns", 1),
    (["--allow-untrusted-audit", "--fail-on", "blocking"], "test-03-blocking-with-retry", 1),
    (["--allow-untrusted-audit", "--fail-on", "nonpass"], "test-03-blocking-with-retry", 1),
]
for args, name, expected in FAIL_ON:
    cmd = [str(TOF), "validate"] + args + [str(ROOT / "test-fixtures" / name)]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != expected:
        failures.append(f"{' '.join(args)}: exit {proc.returncode} != {expected}; stdout={proc.stdout!r} stderr={proc.stderr!r}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)
print("all expected TOF fixture semantics passed")
