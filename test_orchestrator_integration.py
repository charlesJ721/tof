#!/usr/bin/env python3
"""Integration tests for orchestrator.py dispatch/validate/receipt loop.

These tests exercise the P1.2 dispatch.command_argv injection point with
stub subprocesses. They do NOT require a real hermes CLI or a real agent.log.

Usage: python3 test_orchestrator_integration.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
from pathlib import Path
from types import SimpleNamespace

# Add TOF dir to path so we can import orchestrator
TOF_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOF_DIR))

import orchestrator
from orchestrator import _build_dispatch_command, _dispatch_ot, run


# ── Helpers ────────────────────────────────────────────────────────


def write_stub_dispatch(path: Path) -> None:
    """Write a stub OT command that parses the orchestrator prompt and writes an artifact."""
    path.write_text(textwrap.dedent(r'''
        #!/usr/bin/env python3
        import re
        import sys
        from pathlib import Path

        prompt = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
        m = re.search(r"Write your artifact to:\s*(\S+)", prompt)
        if not m:
            raise SystemExit("missing artifact target in prompt")
        artifact_path = Path(m.group(1))
        name = artifact_path.name.lower()
        if "clarify" in name:
            phase = "clarify"
            model = "deepseek-v4-flash"
            family = "deepseek"
            body = """---
tof:
  run_id: stub-run
  phase: clarify
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: stub
    assigned_model: deepseek-v4-flash
    claimed_model: deepseek-v4-flash
    assigned_family: deepseek
    actual_family: deepseek
  inputs: []
task:
  scope: "exercise orchestrator integration loop"
  success_criteria:
    - "stub dispatch writes artifacts"
  explicit_exclusions:
    - "real hermes CLI"
  constraints:
    - "uses stub dispatch"
  verdict: READY
---
Clarify body.
"""
        elif "scout" in name:
            phase = "scout"
            model = "claude-opus-4.8"
            family = "claude"
            body = """---
tof:
  run_id: stub-run
  phase: scout
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: stub
    assigned_model: claude-opus-4.8
    claimed_model: claude-opus-4.8
    assigned_family: claude
    actual_family: claude
  inputs:
    - phase: clarify
      path: "00-Clarify.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
scout:
  affected_files:
    - orchestrator.py
  dependency_graph: "orchestrator -> tof validate"
  verification_functions:
    - "python3 test_orchestrator_integration.py"
  risk_areas:
    - "dispatch/audit coupling"
  unknowns:
    - "none in stubbed scenario"
  implicit_dependencies:
    - "pipeline.yaml dispatch.command_template"
  verdict: PASS
---
Scout body.
"""
        elif "verify" in name:
            phase = "verify"
            model = "deepseek-v4-pro"
            family = "deepseek"
            body = """---
tof:
  run_id: stub-run
  phase: verify
  schema_version: "0.1"
  round: 1
  produced_by:
    adapter: stub
    assigned_model: deepseek-v4-pro
    claimed_model: deepseek-v4-pro
    assigned_family: deepseek
    actual_family: deepseek
  inputs:
    - phase: scout
      path: "01-Scout.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
verify:
  verdict: PASS
  mismatches:
    - expected: "all good"
      actual: "all good"
      status: "no_issues"
  vf_results:
    - vf_name: "stub loop"
      passed: true
      output: "ok"
---
Verify body.
"""
        else:
            phase = "unknown"
            model = "unknown"
            family = "unknown"
            body = "---\n---\nunknown\n"

        artifact_path.write_text(body)
        print(f"Session: fake-sess-{phase}", file=sys.stderr)
        print(body)
    ''').lstrip().replace("\n        ", "\n"))
    path.chmod(0o755)


def write_minimal_tof_tree(tof_dir: Path, stub_path: Path) -> None:
    """Create a self-contained TOF tree using the real validator and stub dispatch."""
    shutil.copy2(TOF_DIR / "tof", tof_dir / "tof")

    (tof_dir / "pipeline.yaml").write_text(textwrap.dedent(f'''
        version: "0.1"
        dispatch_timeout_seconds: 10
        timeout_policy:
          max_retries: 0
          retry_interval_seconds: 1
          allow_provider_fallback: false
        model_freshness:
          max_staleness_days: 9999
          on_stale: warning
        dispatch:
          command_argv: {[sys.executable, str(stub_path), '{{prompt}}']!r}
          audit_log_path: "/dev/null"
        phases:
          clarify:
            artifact: TASK.md
            model: deepseek-v4-flash
            inputs: {{}}
            required_fields:
              - task.scope
              - task.success_criteria
              - task.explicit_exclusions
              - task.constraints
            verdict_field: task.verdict
            verdicts:
              READY:
                next: scout
            approval_policy: always
          scout:
            artifact: RESEARCH.md
            model: claude-opus-4.8
            inputs:
              required:
                - clarify
            required_fields:
              - scout.affected_files
              - scout.dependency_graph
              - scout.verification_functions
              - scout.risk_areas
              - scout.unknowns
              - scout.implicit_dependencies
            field_rules:
              scout.unknowns:
                min_items: 1
              scout.implicit_dependencies:
                min_items: 1
            verdict_field: scout.verdict
            verdicts:
              PASS:
                next: verify
          verify:
            artifact: VERIFICATION.md
            model: deepseek-v4-pro
            inputs:
              required:
                - scout
            required_fields:
              - verify.verdict
              - verify.mismatches
              - verify.vf_results
            verdict_field: verify.verdict
            verdicts:
              PASS:
                next: null
    '''))

    (tof_dir / "models.yaml").write_text(textwrap.dedent('''
        models:
          deepseek-v4-flash:
            family: deepseek
            provider: deepseek
            provider_model_id: deepseek-v4-flash
            freshness_checked_at: "2026-07-01"
            default_verification: adapter_confirmed
          claude-opus-4.8:
            family: claude
            provider: openrouter
            provider_model_id: anthropic/claude-opus-4.8
            freshness_checked_at: "2026-07-01"
            default_verification: adapter_confirmed
          deepseek-v4-pro:
            family: deepseek
            provider: deepseek
            provider_model_id: deepseek-v4-pro
            freshness_checked_at: "2026-07-01"
            default_verification: adapter_confirmed
    '''))

    for phase in ("clarify", "scout", "verify"):
        phase_dir = tof_dir / "phases" / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        (phase_dir / "prompt.md").write_text(f"# {phase}\nphase: {phase}\nModel: FILL WITH MODEL NAME\n")


def stub_audit(session_id, log_path, assigned_model, models_registry):
    family = models_registry[assigned_model]["family"]
    return SimpleNamespace(value="verified_match"), {
        "assigned_model": assigned_model,
        "actual_model": assigned_model,
        "actual_family": family,
        "fallback_detected": False,
        "provider": models_registry[assigned_model].get("provider"),
        "latency_ms": 1,
        "verification_confidence": 1.0,
        "method": "adapter_confirmed",
        "outcome": "verified_match",
    }


# ── Tests ──────────────────────────────────────────────────────────


def test_dispatch_command_template_roundtrip():
    """Legacy dispatch.command_template still substitutes prompt/provider/model."""
    pipeline = {
        "dispatch": {
            "command_template": "python3 stub.py --provider {provider} --model {model} {prompt}"
        }
    }
    prompt = "hello 'quoted' world"
    argv = _build_dispatch_command(pipeline, prompt, "openrouter", "openai/gpt-5.5")
    assert argv == [
        "python3", "stub.py", "--provider", "openrouter",
        "--model", "openai/gpt-5.5", prompt,
    ]


def test_stub_dispatch_produces_artifact_and_prompt_file():
    """_dispatch_ot runs a stub template, extracts Session:, and post-processes artifact."""
    old_check = orchestrator._check_model_freshness
    orchestrator._check_model_freshness = lambda model, tof_dir: None
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tof_dir = root / "tof"
            run_dir = root / "run"
            tof_dir.mkdir()
            run_dir.mkdir()
            stub = root / "stub_dispatch.py"
            write_stub_dispatch(stub)
            write_minimal_tof_tree(tof_dir, stub)

            pipeline = orchestrator._load_pipeline(tof_dir)
            models = orchestrator._load_models(tof_dir)
            artifact = run_dir / "00-Clarify.md"
            session_id, provenance_verified = _dispatch_ot(
                tof_dir, "clarify", "deepseek-v4-flash", artifact, run_dir,
                pipeline, models, extra_context="integration task"
            )

            assert session_id == "fake-sess-clarify"
            assert provenance_verified == True, f"provenance_verified={provenance_verified}"
            assert artifact.exists()
            text = artifact.read_text()
            assert "phase: clarify" in text
            assert "assigned_model: deepseek-v4-flash" in text
            prompt_file = run_dir / ".hermes_prompt_clarify.txt"
            assert prompt_file.exists()
            prompt_text = prompt_file.read_text()
            assert "integration task" in prompt_text
            assert f"Write your artifact to: {artifact}" in prompt_text
    finally:
        orchestrator._check_model_freshness = old_check


def test_run_dispatch_validate_receipt_loop_without_real_hermes_or_agent_log():
    """run() loops validate→dispatch→audit metadata until a stubbed verify PASS."""
    old_find = orchestrator._find_tof_bin
    old_check = orchestrator._check_model_freshness
    orchestrator._check_model_freshness = lambda model, tof_dir: None
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_tof_dir = root / "tof"
            run_dir = root / "run"
            fake_tof_dir.mkdir()
            stub = root / "stub_dispatch.py"
            write_stub_dispatch(stub)
            write_minimal_tof_tree(fake_tof_dir, stub)

            orchestrator._find_tof_bin = lambda: fake_tof_dir / "tof"
            rc = run(str(run_dir), task="exercise the loop", audit_fn=stub_audit)

            assert rc == 0
            assert (run_dir / "00-Clarify.md").exists()
            assert (run_dir / "01-Scout.md").exists()
            assert (run_dir / "02-Verify.md").exists()
            assert (run_dir / ".hermes_prompt_clarify.txt").exists()
            assert (run_dir / ".hermes_prompt_scout.txt").exists()
            assert (run_dir / ".hermes_prompt_verify.txt").exists()

            scout_text = (run_dir / "01-Scout.md").read_text()
            assert "0000000000000000" not in scout_text, "clarify SHA placeholder was not injected"
            verify_text = (run_dir / "02-Verify.md").read_text()
            assert "0000000000000000" not in verify_text, "scout SHA placeholder was not injected"

            scout_meta = json.loads((run_dir / ".session-metadata-scout.json").read_text())
            assert scout_meta["verification_method"] == "adapter_confirmed"
            assert scout_meta["outcome"] == "verified_match"
            assert scout_meta["actual_model"] == "claude-opus-4.8"
    finally:
        orchestrator._find_tof_bin = old_find
        orchestrator._check_model_freshness = old_check


def test_run_stops_on_invalid_receipt():
    """run() stops when tof validate returns INVALID; no hermes/audit needed."""
    old_find = orchestrator._find_tof_bin
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_tof_dir = root / "tof"
            run_dir = root / "run"
            fake_tof_dir.mkdir()
            run_dir.mkdir()
            stub = root / "stub_dispatch.py"
            write_stub_dispatch(stub)
            write_minimal_tof_tree(fake_tof_dir, stub)
            orchestrator._find_tof_bin = lambda: fake_tof_dir / "tof"

            # Missing required task.success_criteria makes the first artifact INVALID.
            (run_dir / "00-Clarify.md").write_text("""---
tof:
  phase: clarify
  produced_by:
    assigned_model: deepseek-v4-flash
    actual_family: deepseek
  inputs: []
task:
  scope: "bad artifact"
  explicit_exclusions: []
  constraints: []
  verdict: READY
---
invalid
""")

            rc = run(str(run_dir), audit_fn=stub_audit)
            assert rc == 1
            assert not (run_dir / "01-Scout.md").exists()
    finally:
        orchestrator._find_tof_bin = old_find


# ── Runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        ("dispatch_command_template_roundtrip", test_dispatch_command_template_roundtrip),
        ("stub_dispatch_produces_artifact_and_prompt_file", test_stub_dispatch_produces_artifact_and_prompt_file),
        ("run_dispatch_validate_receipt_loop_without_real_hermes_or_agent_log", test_run_dispatch_validate_receipt_loop_without_real_hermes_or_agent_log),
        ("run_stops_on_invalid_receipt", test_run_stops_on_invalid_receipt),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except Exception:
            failed += 1
            print(f"  FAIL  {name}")
            traceback.print_exc()

    print(f"\n{passed} passed, {failed} failed, {len(tests)} total")
    sys.exit(0 if failed == 0 else 1)
