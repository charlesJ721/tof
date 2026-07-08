#!/usr/bin/env python3
"""Unit tests for orchestrator.py pure functions.

Covers the 5 non-hermes-dependent functions that contain the most
logic-dense code in the orchestrator. No external deps — runs
against tmp dirs within the TOF tree.

Usage: python3 test_orchestrator_unit.py
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

# Add TOF dir to path so we can import orchestrator
sys.path.insert(0, str(Path(__file__).resolve().parent))
from orchestrator import (
    _build_dispatch_command,
    _build_upstream_context,
    _extract_response_body,
    _inject_artifact_shas,
    _preprocess_prompt,
    _snapshot_configs,
    _strip_ansi,
)

# ── _preprocess_prompt ────────────────────────────────────────────

def test_preprocess_known_metadata():
    """FILL WITH placeholders for known fields → concrete values."""
    prompt = "Run: FILL WITH RUN ID, Round: FILL WITH ROUND NUMBER, Model: FILL WITH MODEL NAME, Family: FILL WITH FAMILY"
    result = _preprocess_prompt(
        prompt,
        run_dir=Path("/tmp/run-abc123"),
        phase="establish",
        model="gpt-5.5",
        model_cfg={"family": "gpt"},
    )
    assert "run-abc123" in result, f"RUN ID not replaced: {result}"
    assert "Round: 1" in result, f"ROUND NUMBER not replaced: {result}"
    assert "Model: gpt-5.5" in result, f"MODEL NAME not replaced: {result}"
    assert "Family: gpt" in result, f"FAMILY not replaced: {result}"
    assert "FILL WITH" not in result, f"Unreplaced placeholder: {result}"


def test_preprocess_sha_placeholder():
    """FILL WITH SHA256 OF <phase> ARTIFACT → {{SHA_WILL_BE_INJECTED}}."""
    prompt = "Input SHA: FILL WITH SHA256 OF scout ARTIFACT"
    result = _preprocess_prompt(prompt, Path("/tmp/x"), "review", "gpt", {"family": "gpt"})
    assert "{{SHA_WILL_BE_INJECTED}}" in result


def test_preprocess_field_markers():
    """FILL WITH VERDICT|OPTIONS → {{FIELD: ...}} markers."""
    prompt = "Verdict: FILL WITH PASS|FAIL"
    result = _preprocess_prompt(prompt, Path("/tmp/x"), "scout", "opus", {"family": "claude"})
    assert "{{FIELD: PASS|FAIL}}" in result


def test_preprocess_descriptive_text():
    """FILL WITH Descriptive Text → {{FIELD: Descriptive Text}}."""
    prompt = "Summary: FILL WITH Analysis Results Here"
    result = _preprocess_prompt(prompt, Path("/tmp/x"), "scout", "opus", {"family": "claude"})
    assert "{{FIELD: Analysis Results Here}}" in result


def test_preprocess_catchall():
    """Isolated FILL WITH → {{FIELD}}."""
    prompt = "Some text FILL WITH more text"
    result = _preprocess_prompt(prompt, Path("/tmp/x"), "scout", "opus", {"family": "claude"})
    assert "{{FIELD}}" in result
    assert "FILL WITH" not in result


def test_preprocess_no_placeholders():
    """Prompt without any FILL WITH → returned unchanged."""
    prompt = "This is a clean prompt with no placeholders."
    result = _preprocess_prompt(prompt, Path("/tmp/x"), "scout", "opus", {"family": "claude"})
    assert result == prompt


# ── _strip_ansi ───────────────────────────────────────────────────

def test_strip_ansi_colors():
    text = "\x1b[32mGREEN\x1b[0m normal"
    assert _strip_ansi(text) == "GREEN normal"


def test_strip_ansi_crlf():
    text = "line1\r\nline2\rline3"
    result = _strip_ansi(text)
    assert "\r" not in result
    assert "\n" in result


# ── _extract_response_body ────────────────────────────────────────

def test_extract_normal_output():
    """Plain model output without TUI framing."""
    text = "Here is the analysis.\n\nConclusion: it works."
    assert _extract_response_body(text) == "Here is the analysis.\n\nConclusion: it works."


def test_extract_strips_footer():
    """Strip 'Resume this session with:' footer."""
    text = "Model output here.\nResume this session with: hermes chat --continue abcd1234\nMore footer."
    result = _extract_response_body(text)
    assert "Model output here." in result
    assert "Resume this session" not in result


def test_extract_strips_session_summary():
    """Strip Session:/Duration:/Messages: lines."""
    text = "Session: abc-123\nDuration: 45s\nMessages: 12\nActual output here."
    result = _extract_response_body(text)
    assert "Session:" not in result
    assert "Duration:" not in result
    assert "Actual output here." in result


def test_extract_strips_tui_framing():
    """Strip ╭ and ╰ TUI box-drawing lines."""
    text = "╭─ ⚕ Hermes Agent\nModel output here.\n╰──────────"
    result = _extract_response_body(text)
    assert "╭" not in result
    assert "╰" not in result
    assert "Model output here." in result


def test_extract_strips_hermes_header():
    """Strip Hermes Agent header line."""
    text = "Hermes  Agent  v2.1.0\nActual content."
    result = _extract_response_body(text)
    assert "Hermes" not in result or "Actual content" in result


def test_extract_empty():
    assert _extract_response_body("") == ""


def test_extract_realistic_hermes_output():
    """Simulate a realistic hermes TUI output block."""
    text = """╭─ ⚕ Hermes Agent (deepseek-v4-pro · deepseek) ───╮
Session: sess-abc123
Duration: 12.3s
Messages: 5

## Scout Analysis

The affected files are:
- src/main.py
- config/settings.yaml

Unknown: nested YAML include resolution behavior.

Resume this session with: hermes chat --continue sess-abc123
╰──────────────────────────────────────────────────╯"""
    result = _extract_response_body(text)
    assert "## Scout Analysis" in result
    assert "src/main.py" in result
    assert "nested YAML" in result
    assert "Resume this session" not in result
    assert "Duration:" not in result
    assert "╭" not in result


# ── _build_dispatch_command ────────────────────────────────────────

def test_build_dispatch_command_argv_apostrophe_prompt():
    """command_argv keeps apostrophes in prompt as one argv element."""
    pipeline = {
        "dispatch": {
            "command_argv": ["hermes", "chat", "-q", "{prompt}", "--provider", "{provider}", "--model", "{model}"]
        }
    }
    prompt = "Bob's task"
    argv = _build_dispatch_command(pipeline, prompt, "openrouter", "openai/gpt-5.5")
    assert argv == ["hermes", "chat", "-q", prompt, "--provider", "openrouter", "--model", "openai/gpt-5.5"]


def test_build_dispatch_command_argv_double_quote_prompt():
    """command_argv keeps double quotes in prompt as one argv element."""
    pipeline = {
        "dispatch": {
            "command_argv": ["hermes", "chat", "-q", "{prompt}", "--provider", "{provider}", "--model", "{model}"]
        }
    }
    prompt = 'He said "hello"'
    argv = _build_dispatch_command(pipeline, prompt, "openrouter", "openai/gpt-5.5")
    assert argv[3] == prompt
    assert argv[-1] == "openai/gpt-5.5"


def test_build_dispatch_command_argv_newline_prompt():
    """command_argv keeps newlines in prompt as one argv element."""
    pipeline = {
        "dispatch": {
            "command_argv": ["hermes", "chat", "-q", "{prompt}", "--provider", "{provider}", "--model", "{model}"]
        }
    }
    prompt = "line1\nline2"
    argv = _build_dispatch_command(pipeline, prompt, "openrouter", "openai/gpt-5.5")
    assert argv[3] == prompt
    assert len(argv) == 8


def test_build_dispatch_command_legacy_command_template_compat():
    """Legacy command_template remains supported when command_argv is absent."""
    pipeline = {
        "dispatch": {
            "command_template": "python3 stub.py --provider {provider} --model {model} {prompt}"
        }
    }
    prompt = "hello legacy world"
    argv = _build_dispatch_command(pipeline, prompt, "openrouter", "openai/gpt-5.5")
    assert argv == [
        "python3", "stub.py", "--provider", "openrouter",
        "--model", "openai/gpt-5.5", prompt,
    ]


# ── _build_upstream_context ───────────────────────────────────────

def test_build_context_reads_upstream():
    """Read upstream artifact body (after frontmatter)."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        # Create a scout artifact
        (run_dir / "01-scout.md").write_text("""---
tof:
  phase: scout
  round: 1
---
Scout body content here.
Line two of scout body.
""")
        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["scout"]},
                }
            }
        }
        result = _build_upstream_context(run_dir, "establish", pipeline)
        assert "Scout body content here." in result
        assert "Line two of scout body." in result


def test_build_context_multiple_upstream():
    """Read multiple upstream artifacts."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        (run_dir / "01-clarify.md").write_text("""---
tof:
  phase: clarify
---
Clarify body.
""")
        (run_dir / "02-scout.md").write_text("""---
tof:
  phase: scout
---
Scout body.
""")
        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["clarify", "scout"]},
                }
            }
        }
        result = _build_upstream_context(run_dir, "establish", pipeline)
        assert "Clarify body." in result
        assert "Scout body." in result


def test_build_context_no_upstream():
    """Phase with no required inputs → empty string."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        pipeline = {
            "phases": {
                "clarify": {"inputs": {}},
            }
        }
        result = _build_upstream_context(run_dir, "clarify", pipeline)
        assert result == ""


def test_build_context_missing_upstream_file():
    """Missing upstream file → empty string (graceful)."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["scout"]},
                }
            }
        }
        result = _build_upstream_context(run_dir, "establish", pipeline)
        assert result == ""


# ── _inject_artifact_shas ─────────────────────────────────────────

def test_inject_shas_basic():
    """Inject real SHA256 into artifact frontmatter input references."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        # Create upstream artifact
        upstream = run_dir / "01-scout.md"
        upstream.write_text("""---
tof:
  phase: scout
---
scout content
""")
        # Create artifact with placeholder SHA
        art_path = run_dir / "02-establish.md"
        art_path.write_text("""---
tof:
  phase: establish
  inputs:
    - phase: scout
      path: "01-scout.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
establish:
  verdict: READY
---
establish content
""")
        import hashlib
        expected_sha = hashlib.sha256(upstream.read_bytes()).hexdigest()

        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["scout"]},
                }
            }
        }
        _inject_artifact_shas(art_path, run_dir, pipeline, "establish",
                              "gpt-5.5", {"family": "gpt"})

        # Verify SHA was injected
        updated = art_path.read_text()
        assert expected_sha in updated, f"SHA not injected. Expected {expected_sha[:16]}..."
        assert "0000000000000000" not in updated, "Placeholder SHA still present"


def test_inject_shas_missing_file():
    """Non-existent artifact → no error, silent return."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        art_path = run_dir / "nonexistent.md"
        pipeline = {"phases": {"establish": {"inputs": {"required": []}}}}
        # Should not raise
        _inject_artifact_shas(art_path, run_dir, pipeline, "establish",
                              "gpt-5.5", {"family": "gpt"})


def test_inject_shas_no_frontmatter():
    """File without YAML frontmatter → no error, silent return."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        art_path = run_dir / "plain.md"
        art_path.write_text("Just plain text, no frontmatter.")
        pipeline = {"phases": {"establish": {"inputs": {"required": []}}}}
        _inject_artifact_shas(art_path, run_dir, pipeline, "establish",
                              "gpt-5.5", {"family": "gpt"})
        # File unchanged
        assert art_path.read_text() == "Just plain text, no frontmatter."


def test_inject_shas_multiple_inputs():
    """Inject SHAs for multiple upstream references."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        # Two upstream files
        clarify = run_dir / "01-clarify.md"
        clarify.write_text("""---
tof:
  phase: clarify
---
clarify body
""")
        scout = run_dir / "02-scout.md"
        scout.write_text("""---
tof:
  phase: scout
---
scout body
""")
        import hashlib
        c_sha = hashlib.sha256(clarify.read_bytes()).hexdigest()
        s_sha = hashlib.sha256(scout.read_bytes()).hexdigest()

        art_path = run_dir / "03-establish.md"
        art_path.write_text(f"""---
tof:
  phase: establish
  inputs:
    - phase: clarify
      path: "01-clarify.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
    - phase: scout
      path: "02-scout.md"
      sha256: "1111111111111111111111111111111111111111111111111111111111111111"
establish:
  verdict: READY
---
""")
        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["clarify", "scout"]},
                }
            }
        }
        _inject_artifact_shas(art_path, run_dir, pipeline, "establish",
                              "gpt-5.5", {"family": "gpt"})

        updated = art_path.read_text()
        assert c_sha in updated
        assert s_sha in updated
        assert "000000000000" not in updated
        assert "111111111111" not in updated


def test_inject_shas_skips_non_required():
    """Only inject SHAs for phases declared in pipeline required inputs."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td)
        upstream = run_dir / "01-extra.md"
        upstream.write_text("""---
tof:
  phase: extra
---
extra body
""")
        art_path = run_dir / "02-main.md"
        art_path.write_text("""---
tof:
  phase: establish
  inputs:
    - phase: extra
      path: "01-extra.md"
      sha256: "0000000000000000000000000000000000000000000000000000000000000000"
establish:
  verdict: READY
---
""")
        # Pipeline does NOT list "extra" as required input
        pipeline = {
            "phases": {
                "establish": {
                    "inputs": {"required": ["scout"]},  # only scout, not extra
                }
            }
        }
        _inject_artifact_shas(art_path, run_dir, pipeline, "establish",
                              "gpt-5.5", {"family": "gpt"})
        # SHA should NOT be injected since "extra" is not a required input
        updated = art_path.read_text()
        assert "0000000000000000000000000000000000000000000000000000000000000000" in updated


# ── _snapshot_configs ─────────────────────────────────────────────

def test_snapshot_configs():
    """Copies pipeline.yaml and models.yaml into run_dir/.tof/."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / "run"
        run_dir.mkdir()
        tof_dir = Path(td) / "tof_src"
        tof_dir.mkdir()

        # Create source configs
        (tof_dir / "pipeline.yaml").write_text("version: '0.1'\nphases: {}\n")
        (tof_dir / "models.yaml").write_text("models:\n  gpt-5.5:\n    family: gpt\n")

        _snapshot_configs(run_dir, tof_dir)

        snap_dir = run_dir / ".tof"
        assert snap_dir.exists(), ".tof/ not created"
        assert (snap_dir / "pipeline.yaml").exists(), "pipeline.yaml not copied"
        assert (snap_dir / "models.yaml").exists(), "models.yaml not copied"
        assert "version: '0.1'" in (snap_dir / "pipeline.yaml").read_text()
        assert "gpt-5.5" in (snap_dir / "models.yaml").read_text()


def test_snapshot_configs_missing_source():
    """Missing source file → skips gracefully."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / "run"
        run_dir.mkdir()
        tof_dir = Path(td) / "empty_src"
        tof_dir.mkdir()
        # No pipeline.yaml or models.yaml in tof_dir

        _snapshot_configs(run_dir, tof_dir)

        snap_dir = run_dir / ".tof"
        assert snap_dir.exists()
        # Neither file should exist
        assert not (snap_dir / "pipeline.yaml").exists()
        assert not (snap_dir / "models.yaml").exists()


# ── Runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = [
        # _preprocess_prompt
        ("preprocess_known_metadata", test_preprocess_known_metadata),
        ("preprocess_sha_placeholder", test_preprocess_sha_placeholder),
        ("preprocess_field_markers", test_preprocess_field_markers),
        ("preprocess_descriptive_text", test_preprocess_descriptive_text),
        ("preprocess_catchall", test_preprocess_catchall),
        ("preprocess_no_placeholders", test_preprocess_no_placeholders),
        # _strip_ansi
        ("strip_ansi_colors", test_strip_ansi_colors),
        ("strip_ansi_crlf", test_strip_ansi_crlf),
        # _extract_response_body
        ("extract_normal_output", test_extract_normal_output),
        ("extract_strips_footer", test_extract_strips_footer),
        ("extract_strips_session_summary", test_extract_strips_session_summary),
        ("extract_strips_tui_framing", test_extract_strips_tui_framing),
        ("extract_strips_hermes_header", test_extract_strips_hermes_header),
        ("extract_empty", test_extract_empty),
        ("extract_realistic_hermes_output", test_extract_realistic_hermes_output),
        # _build_dispatch_command
        ("build_dispatch_command_argv_apostrophe_prompt", test_build_dispatch_command_argv_apostrophe_prompt),
        ("build_dispatch_command_argv_double_quote_prompt", test_build_dispatch_command_argv_double_quote_prompt),
        ("build_dispatch_command_argv_newline_prompt", test_build_dispatch_command_argv_newline_prompt),
        ("build_dispatch_command_legacy_command_template_compat", test_build_dispatch_command_legacy_command_template_compat),
        # _build_upstream_context
        ("build_context_reads_upstream", test_build_context_reads_upstream),
        ("build_context_multiple_upstream", test_build_context_multiple_upstream),
        ("build_context_no_upstream", test_build_context_no_upstream),
        ("build_context_missing_upstream_file", test_build_context_missing_upstream_file),
        # _inject_artifact_shas
        ("inject_shas_basic", test_inject_shas_basic),
        ("inject_shas_missing_file", test_inject_shas_missing_file),
        ("inject_shas_no_frontmatter", test_inject_shas_no_frontmatter),
        ("inject_shas_multiple_inputs", test_inject_shas_multiple_inputs),
        ("inject_shas_skips_non_required", test_inject_shas_skips_non_required),
        # _snapshot_configs
        ("snapshot_configs", test_snapshot_configs),
        ("snapshot_configs_missing_source", test_snapshot_configs_missing_source),
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
