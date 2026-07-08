#!/usr/bin/env python3
"""TOF Orchestrator — receipt-driven state machine loop.

Dispatches OT subprocesses, calls SessionAuditAdapter, merges metadata,
re-runs tof validate.  Stateless and idempotent.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

_LEDGER_PATH = os.environ.get(
    "TOF_LEDGER_PATH", os.path.expanduser("~/.hermes/tof-execution-ledger.jsonl")
)


def _write_execution_ledger(mode: str, run_dir: str, status: str, **extra_fields) -> None:
    """Append a best-effort execution record; never fail TOF runs."""
    try:
        entry = {
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "mode": mode,
            "run_dir": run_dir,
            "status": status,
            **extra_fields,
        }
        with open(_LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _ledger_status(status: Any) -> str:
    """Normalize validator/orchestrator states into ledger status values."""
    status_str = str(status or "ERROR").upper()
    return status_str if status_str in {"PASS", "BLOCKING", "INVALID"} else "ERROR"


def _return_with_ledger(mode: str, run_dir: Path, status: Any, rc: int) -> int:
    _write_execution_ledger(mode, str(run_dir), _ledger_status(status))
    return rc


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run(run_dir: str, step_mode: bool = False, task: Optional[str] = None,
        only_phase: Optional[str] = None,
        audit_fn: Optional[Callable[[str, str, str, Dict[str, Dict[str, Any]]], Tuple[Any, Dict[str, Any]]]] = None) -> int:
    """Orchestrate a TOF run to completion (or single step)."""
    rd = Path(run_dir).resolve()
    if not rd.exists():
        print(f"Creating run directory: {rd}")
        rd.mkdir(parents=True)

    tof_bin = _find_tof_bin()
    snap_dir = rd / ".tof"
    # Snapshot live config into immutable run directory FIRST,
    # then load loop control from snapshot — prevents split-brain
    # between orchestrator (loop driver) and validator (gate judge).
    _snapshot_configs(rd, tof_bin.parent)
    pipeline_path = snap_dir / "pipeline.yaml"
    models_path = snap_dir / "models.yaml"
    pipeline = _load_pipeline(snap_dir)
    models_registry = _load_models(snap_dir)
    phase_order = list(pipeline.get("phases", {}).keys())

    if only_phase:
        next_phase = only_phase.strip().lower()
        ledger_mode = f"single-{next_phase}"
        phase_cfg = pipeline.get("phases", {}).get(next_phase)
        if not phase_cfg:
            print(f"STOP — phase '{next_phase}' not found in pipeline.yaml")
            return _return_with_ledger(ledger_mode, rd, "ERROR", 1)
        assigned_model = phase_cfg.get("model")
        if not assigned_model:
            print(f"STOP — phase '{next_phase}' has no model assignment")
            return _return_with_ledger(ledger_mode, rd, "ERROR", 1)
        try:
            _require_upstream_artifacts(rd, next_phase, pipeline)
        except RuntimeError as e:
            print(f"STOP — {e}")
            return _return_with_ledger(ledger_mode, rd, "ERROR", 1)

        phase_idx = phase_order.index(next_phase) if next_phase in phase_order else 0
        artifact_name = f"{phase_idx:02d}-{next_phase.capitalize()}.md"
        artifact_path = rd / artifact_name
        dispatch_pipeline = dict(pipeline)
        dispatch_pipeline["timeout_policy"] = dict(pipeline.get("timeout_policy", {}) or {}, max_retries=0)

        print(f"  ONLY: dispatching {next_phase} via {assigned_model} ...")
        try:
            session_id, provenance_verified = _dispatch_ot(
                tof_bin.parent, next_phase, assigned_model, artifact_path, rd,
                dispatch_pipeline, models_registry,
                extra_context=task if (next_phase == "clarify" and task) else None)
        except RuntimeError as e:
            print(f"STOP — OT dispatch failed: {e}")
            return _return_with_ledger(ledger_mode, rd, "ERROR", 1)

        _audit_and_write_metadata(rd, next_phase, session_id, assigned_model,
                                  models_registry, pipeline, audit_fn,
                                  provenance_verified)
        receipt = _tof_validate(tof_bin, rd, pipeline_path, models_path)
        print(json.dumps(receipt, indent=2))
        status = receipt.get("validation", {}).get("status")
        return _return_with_ledger(
            ledger_mode, rd, status, 0 if status == "PASS" else 1
        )

    max_iter = 20
    last_phase = None
    last_phase_count = 0

    for _ in range(max_iter):
        receipt = _tof_validate(tof_bin, rd, pipeline_path, models_path)
        status = receipt["validation"]["status"]
        phase = receipt["validation"].get("phase")
        next_allowed = receipt["validation"].get("next_allowed", [])
        frontier = receipt["validation"].get("causal_frontier")

        print(f"  [{status}] phase={phase} next={next_allowed}")

        # Terminal: pipeline complete
        if status == "PASS" and frontier and frontier.get("phase") in ("verify", "deposition"):
            print("DONE — pipeline complete.")
            return _return_with_ledger("full-seri", rd, status, 0)

        # Terminal: INVALID artifact
        if status == "INVALID":
            reasons = receipt["validation"].get("reasons", [])
            print(f"STOP — INVALID artifact. Reasons:")
            for r in reasons:
                print(f"  - {r}")
            return _return_with_ledger("full-seri", rd, status, 1)

        # Terminal: PENDING — start from clarify
        if status == "PENDING":
            next_phase = next_allowed[0] if next_allowed else "clarify"
        elif status == "BLOCKING":
            if not next_allowed:
                print("STOP — BLOCKING with no next phase, escalation required.")
                return _return_with_ledger("full-seri", rd, status, 1)
            next_phase = next_allowed[0]
        elif next_allowed:
            next_phase = next_allowed[0]
        else:
            print("STOP — unknown state.")
            return _return_with_ledger("full-seri", rd, "ERROR", 1)

        if step_mode:
            print(f"  STEP: next phase = {next_phase}")
            print(f"  Run: tof run {rd} to continue")
            return 0

        # Dispatch OT subprocess
        phase_cfg = pipeline["phases"].get(next_phase)
        if not phase_cfg:
            print(f"STOP — phase '{next_phase}' not found in pipeline.yaml")
            return _return_with_ledger("full-seri", rd, "ERROR", 1)
        assigned_model = phase_cfg.get("model")
        if not assigned_model:
            print(f"STOP — phase '{next_phase}' has no model assignment")
            return _return_with_ledger("full-seri", rd, "ERROR", 1)

        print(f"  → dispatching {next_phase} via {assigned_model} ...")

        # Loop guard: if dispatching same phase again without progress, stop
        if next_phase == last_phase:
            last_phase_count += 1
            if last_phase_count >= 3:
                print(f"STOP — dispatching {next_phase} repeatedly ({last_phase_count}x) without progress")
                return _return_with_ledger("full-seri", rd, "ERROR", 1)
        else:
            last_phase = next_phase
            last_phase_count = 0

        try:
            phase_idx = phase_order.index(next_phase) if next_phase in phase_order else 0
            artifact_name = f"{phase_idx:02d}-{next_phase.capitalize()}.md"
            artifact_path = rd / artifact_name
            extra_context = task if (next_phase == "clarify" and task) else None
            session_id, provenance_verified = _dispatch_ot(tof_bin.parent, next_phase, assigned_model,
                                     artifact_path, rd, pipeline, models_registry,
                                     extra_context=extra_context)
        except RuntimeError as e:
            print(f"STOP — OT dispatch failed: {e}")
            return _return_with_ledger("full-seri", rd, "ERROR", 1)

        _audit_and_write_metadata(rd, next_phase, session_id, assigned_model,
                                  models_registry, pipeline, audit_fn,
                                  provenance_verified)

        time.sleep(0.5)

    print("STOP — max iterations reached.")
    return _return_with_ledger("full-seri", rd, "ERROR", 1)


# ---------------------------------------------------------------------------
# Internal: tof validate invocation
# ---------------------------------------------------------------------------

def _tof_validate(tof_bin: Path, run_dir: Path, pipeline_path: Path, models_path: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        [sys.executable, str(tof_bin), "validate", str(run_dir),
         "--pipeline", str(pipeline_path), "--models", str(models_path)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"tof validate failed: {proc.stderr}")
    return json.loads(proc.stdout)


def _find_tof_bin() -> Path:
    """Locate tof script (alongside this module or in parent TOF dir)."""
    this_dir = Path(__file__).resolve().parent
    for cand in [this_dir / "tof", this_dir / ".." / "TOF" / "tof"]:
        if cand.exists():
            return cand.resolve()
    raise FileNotFoundError("cannot find tof script relative to orchestrator")


def _audit_and_write_metadata(
    run_dir: Path,
    phase: str,
    session_id: str,
    assigned_model: str,
    models_registry: Dict[str, Dict[str, Any]],
    pipeline: Dict[str, Any],
    audit_fn: Optional[Callable[[str, str, str, Dict[str, Dict[str, Any]]], Tuple[Any, Dict[str, Any]]]],
    provenance_verified: Optional[bool],
) -> None:
    """Run SessionAuditAdapter and write phase metadata, fail-soft on audit errors."""
    try:
        if audit_fn is None:
            from session_audit_adapter import read_session as audit
        else:
            audit = audit_fn

        log_path = os.path.expanduser(
            pipeline.get("dispatch", {}).get("audit_log_path", "~/.hermes/logs/agent.log")
        )
        outcome, result = audit(session_id, log_path, assigned_model, models_registry)
        _write_metadata(run_dir, phase, session_id, result, provenance_verified)
        print(f"  metadata: actual={result['actual_model']} "
              f"outcome={outcome.value} "
              f"confidence={result['verification_confidence']}")
    except Exception as e:
        print(f"  WARNING: session audit failed ({e}), continuing")
        # Write EXCEPTION metadata so validator knows audit was attempted.
        _write_metadata(run_dir, phase, session_id, {
            "assigned_model": assigned_model,
            "actual_model": None,
            "actual_family": None,
            "fallback_detected": None,
            "provider": None,
            "latency_ms": None,
            "verification_confidence": 0.0,
            "method": "exception",
            "outcome": "exception",
            "exception": str(e),
        }, provenance_verified)


def _require_upstream_artifacts(run_dir: Path, phase: str, pipeline: Dict[str, Any]) -> None:
    """Fail clearly if a single-phase dispatch is missing required inputs."""
    required = (pipeline.get("phases", {}).get(phase, {})
                .get("inputs", {}).get("required", [])) or []
    missing = []
    for upstream_phase in required:
        if _find_artifact_for_phase(run_dir, upstream_phase, pipeline) is None:
            artifact_name = (pipeline.get("phases", {}).get(upstream_phase, {})
                             .get("artifact", f"{upstream_phase}.md"))
            missing.append(f"{upstream_phase} ({artifact_name})")
    if missing:
        raise RuntimeError(
            f"--only {phase} requires upstream artifact(s): {', '.join(missing)}"
        )


def _find_artifact_for_phase(run_dir: Path, phase: str,
                             pipeline: Dict[str, Any]) -> Optional[Path]:
    """Find an artifact by phase frontmatter, falling back to configured filename."""
    for f in sorted(run_dir.glob("*.md"), reverse=True):
        try:
            import yaml
            text = f.read_text()
            if not text.startswith("---"):
                continue
            end = text.find("---", 3)
            if end <= 0:
                continue
            fm = yaml.safe_load(text[3:end]) or {}
            if fm.get("tof", {}).get("phase") == phase:
                return f
        except Exception:
            continue
    artifact_name = pipeline.get("phases", {}).get(phase, {}).get("artifact")
    candidates = []
    if artifact_name:
        candidates.append(run_dir / artifact_name)
    phases = list((pipeline.get("phases", {}) or {}).keys())
    phase_idx = phases.index(phase) if phase in phases else 0
    candidates.append(run_dir / f"{phase_idx:02d}-{phase.capitalize()}.md")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Internal: dispatch
# ---------------------------------------------------------------------------

_SESSION_RE = re.compile(r"Session:\s+(\S+)")


def _build_dispatch_command(pipeline: Dict[str, Any], prompt: str,
                           provider: str, provider_model_id: str) -> List[str]:
    """Build the OT subprocess command from pipeline dispatch template.

    If pipeline.yaml contains dispatch.command_argv, treat it as an argv
    template: substitute {prompt}, {provider}, {model} within each element
    and return the resulting argv list directly. This keeps prompt text as a
    standalone subprocess argument, with no shell quoting or shlex round-trip.

    If only dispatch.command_template exists, use the legacy shell-string path
    for backward compatibility. Otherwise fall back to the default hermes chat
    -q command.

    Returns a list of argv tokens ready for subprocess.run().
    """
    dispatch_cfg = pipeline.get("dispatch", {}) or {}
    argv_template = dispatch_cfg.get("command_argv")
    if argv_template:
        if not isinstance(argv_template, list):
            raise RuntimeError("dispatch.command_argv must be a list")
        return [
            str(arg).replace("{prompt}", prompt)
                    .replace("{provider}", provider)
                    .replace("{model}", provider_model_id)
            for arg in argv_template
        ]

    template = dispatch_cfg.get("command_template")
    if template:
        # Simple variable substitution: {prompt}, {provider}, {model}
        # Legacy shell-string path: prompt is shell-quoted for safety.
        import shlex
        cmd_str = template.replace("{prompt}", shlex.quote(prompt))
        cmd_str = cmd_str.replace("{provider}", provider)
        cmd_str = cmd_str.replace("{model}", provider_model_id)
        return shlex.split(cmd_str)

    # Default: hermes chat -q
    return ["hermes", "chat", "-q", prompt,
            "--provider", provider, "--model", provider_model_id]


def run_triage(task: str, pipeline: Dict[str, Any], models: Dict[str, Dict[str, Any]],
               tof_dir: Path) -> Dict[str, str]:
    """Dispatch a cheap adversarial triage. Returns parsed JSON route decision.

    Triage is advisory-only: it does not use _dispatch_ot, does not write to a
    run_dir, and does not create provenance/session metadata.
    """
    triage_cfg = pipeline.get("phases", {}).get("triage", {})
    if not triage_cfg:
        raise RuntimeError("pipeline.yaml missing 'triage' phase")

    model = triage_cfg.get("model")
    if not model:
        raise RuntimeError("triage phase missing model")
    model_cfg = models.get(model, {})
    provider = model_cfg.get("provider", "openrouter")
    provider_model_id = model_cfg.get("provider_model_id", model)

    prompt_rel = triage_cfg.get("prompt", "phases/triage/prompt.md")
    prompt_path = tof_dir / prompt_rel
    if not prompt_path.exists():
        raise RuntimeError(f"triage prompt not found: {prompt_path}")

    prompt = prompt_path.read_text().replace("{task}", task)

    # Build just enough pipeline for command_template dispatch.
    mini_pipeline = {"dispatch": pipeline.get("dispatch", {})}
    cmd = _build_dispatch_command(mini_pipeline, prompt, provider, provider_model_id)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                          cwd=str(tof_dir))
    output = (proc.stdout or "") + (proc.stderr or "")
    output = _strip_ansi(output)
    if not output:
        raise RuntimeError(f"triage dispatch produced no output (exit {proc.returncode})")

    # Extract JSON from output. Prefer a fenced JSON block if present, then any
    # shallow object; triage output contract is exactly one flat JSON object.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", output, re.DOTALL)
    match = fenced or re.search(r"\{[^{}]*\}", output, re.DOTALL)
    if not match:
        raise RuntimeError(f"no JSON found in triage output: {output[:200]}")

    json_text = match.group(1) if fenced else match.group(0)
    try:
        result = json.loads(json_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"invalid JSON in triage output: {e}: {json_text[:200]}") from e

    valid_routes = {"self", "review-only", "scout+review", "full-seri"}
    route = result.get("route", "self")
    if route not in valid_routes:
        route = "self"

    # Write advisory ledger entry (best-effort, never blocks triage)
    _write_execution_ledger(
        "triage-advice", "advisory", "OK",
        route=route,
        blind_spot=str(result.get("blind_spot", "")),
    )

    return {
        "route": route,
        "blind_spot": str(result.get("blind_spot", "")),
        "reasoning": str(result.get("reasoning", "")),
    }


# ---------------------------------------------------------------------------
# Internal: dispatch
# ---------------------------------------------------------------------------

def _dispatch_ot(tof_dir: Path, phase: str, model: str, artifact_path: Path,
                 run_dir: Path, pipeline: Dict[str, Any],
                 models_registry: Dict[str, Dict[str, Any]],
                 extra_context: Optional[str] = None) -> Tuple[str, bool]:
    """Run hermes chat -q, wait for artifact to be written to artifact_path.
    
    The prompt instructs the model to write its output directly to the target
    artifact path. The orchestrator reads from that path after OT completes.
    """
    # Pre-dispatch: validate model slug against models.yaml
    if model not in models_registry:
        available = ', '.join(sorted(models_registry.keys()))
        raise RuntimeError(
            f"model '{model}' not found in models.yaml. "
            f"Available: {available}"
        )
    
    model_cfg = models_registry[model]
    provider = model_cfg.get("provider", "openrouter")
    provider_model_id = model_cfg.get("provider_model_id", model)
    
    # Pre-dispatch: verify model slug freshness against provider
    # Stale slugs cause silent provider fallback (e.g., Gemini 400→DeepSeek),
    # creating INVALID trust-chain breaks downstream. Catching staleness
    # before dispatch is cheaper than session audit rejection.
    _check_model_freshness(model, tof_dir)
    
    prompt_path = tof_dir / "phases" / phase / "prompt.md"
    if not prompt_path.exists():
        raise RuntimeError(f"prompt file not found: {prompt_path}")

    prompt = prompt_path.read_text()

    # Preprocess template placeholders: replace known FILL WITH tokens
    # with concrete values before OT dispatch. Content FILL WITH tokens
    # become {{MARKER}} templates that models can safely fill in.
    prompt = _preprocess_prompt(prompt, run_dir, phase, model, model_cfg)

    # Append upstream artifact context
    upstream = _build_upstream_context(run_dir, phase, pipeline)
    if upstream:
        prompt += "\n\n## Upstream Artifacts\n\n" + upstream

    # Inject task context for clarify phase
    if extra_context:
        prompt += f"\n\n## Task Description\n\n{extra_context}\n\nProduce your artifact based on the task above. Do NOT ask clarifying questions."

    # Inject target file path
    prompt += f"\n\nWrite your artifact to: {artifact_path}\nOutput the file content to stdout as well."

    # Write prompt to temp file for hermes to read
    prompt_file = run_dir / f".hermes_prompt_{phase}.txt"
    prompt_file.write_text(prompt)

    cmd = _build_dispatch_command(pipeline, prompt, provider, provider_model_id)

    # Read dispatch timeout and retry policy from pipeline config
    dispatch_timeout = int(pipeline.get("dispatch_timeout_seconds", 300))
    timeout_policy = pipeline.get("timeout_policy", {})
    max_retries = int(timeout_policy.get("max_retries", 0))
    retry_interval = int(timeout_policy.get("retry_interval_seconds", 60))

    proc = None
    for attempt in range(max_retries + 1):
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=dispatch_timeout,
                cwd=str(run_dir),
            )
            break
        except subprocess.TimeoutExpired:
            if attempt < max_retries:
                print(f"  timeout (attempt {attempt+1}/{max_retries+1}), "
                      f"retrying in {retry_interval}s...")
                time.sleep(retry_interval)
                continue
            # Retry budget exhausted — write stub artifact and metadata
            _write_timeout_exhausted_stub(artifact_path, run_dir, phase, model, dispatch_timeout)
            raise RuntimeError(
                f"OT dispatch timed out after {max_retries+1} attempts "
                f"({dispatch_timeout}s each) for phase '{phase}'"
            )

    if proc is None:
        raise RuntimeError(f"OT dispatch failed for phase '{phase}': no process result")

    output = (proc.stdout or "") + (proc.stderr or "")
    if not output:
        raise RuntimeError(f"hermes chat produced no output (exit {proc.returncode})")

    # Extract session ID
    m = _SESSION_RE.search(output)
    if not m:
        session_match = re.search(r'\b\d{8}_\d{6}_[a-f0-9]+\b', output)
        if session_match:
            session_id = session_match.group(0)
        else:
            debug_file = run_dir / f".hermes_debug_{phase}.txt"
            debug_file.write_text(output)
            raise RuntimeError(f"cannot find session ID in output; wrote debug to {debug_file}")
    else:
        session_id = m.group(1)

    # Read artifact from target path (model may have written it via write_file tool)
    if artifact_path.exists():
        size = artifact_path.stat().st_size
        print(f"  wrote artifact: {artifact_path.name} ({size} chars)")
    else:
        # Fallback: capture stdout as artifact
        clean = _strip_ansi(output)
        body = _extract_response_body(clean)
        if body:
            artifact_path.write_text(body)
            print(f"  wrote artifact from stdout: {artifact_path.name} ({len(body)} chars)")
        else:
            print(f"  WARNING: no artifact found at {artifact_path.name} and no stdout content")

    # Inject mechanical metadata (SHA256, model identity)
    _inject_artifact_shas(artifact_path, run_dir, pipeline, phase, model, model_cfg)

    # Provenance check: does the artifact body appear in OT output?
    # Extract body (content after frontmatter), check OT stdout for it.
    # Saves OT output to disk for future independent verification by validator.
    (run_dir / f".ot-stdout-{phase}.txt").write_text(output)
    text = artifact_path.read_text()
    parts = text.split("---", 2)
    body = parts[2].strip() if len(parts) >= 3 else ""
    provenance_verified = bool(body and len(body) > 5 and body in output)

    return session_id, provenance_verified


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences and carriage returns."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text).replace('\r\n', '\n').replace('\r', '\n')


def _extract_response_body(text: str) -> str:
    """Extract the model's textual response from hermes TUI output.
    
    Looks for content between TUI framing markers or strips the session footer.
    """
    # Strip session summary footer
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        if 'Resume this session with:' in line:
            break
        if re.match(r'^(Session:|Duration:|Messages:|Query:|Initializing)', line.strip()):
            continue
        if line.strip().startswith('╭') or line.strip().startswith('╰'):
            continue
        if line.strip().startswith('──') or line.strip().startswith('──'):
            continue
        cleaned.append(line)
    
    body = '\n'.join(cleaned).strip()
    # Remove leading hermes header lines
    body = re.sub(r'^.*Hermes\s+Agent.*\n', '', body)
    return body.strip()


def _check_model_freshness(model: str, tof_dir: Path) -> None:
    """Verify model slug is fresh before dispatch.

    Calls ModelRegistryAdapter to check provider endpoint. Stale models
    with on_stale=blocking raise RuntimeError. Stale models with
    on_stale=warning log but allow dispatch (operator decision).

    Skips freshness check if model_registry_adapter.py is not importable
    (graceful degradation — registry freshness is advisory, not blocking
    by default).
    """
    try:
        from model_registry_adapter import check_model as check_freshness
    except ImportError:
        return  # adapter not available, skip

    models_yaml = tof_dir / "models.yaml"
    result = check_freshness(model, models_yaml)

    if result["status"] == "fresh":
        return
    elif result["status"] == "network_error":
        print(f"  WARNING: model freshness check failed (network): {result.get('error')}")
        return
    elif result["status"] == "stale":
        msg = f"stale model slug: {result.get('error', 'unknown')}"
        # Check pipeline policy for on_stale behavior
        try:
            import yaml
            pipeline = yaml.safe_load((tof_dir / "pipeline.yaml").read_text()) or {}
            on_stale = pipeline.get("model_freshness", {}).get("on_stale", "warning")
        except Exception:
            on_stale = "warning"

        if on_stale == "blocking":
            raise RuntimeError(f"Cannot dispatch {model}: {msg}")
        else:
            print(f"  WARNING: {msg}")


# ---------------------------------------------------------------------------
# Internal: prompt construction
# ---------------------------------------------------------------------------

def _build_upstream_context(run_dir: Path, phase: str, pipeline: Dict[str, Any]) -> str:
    """Read upstream artifacts listed in pipeline.yaml inputs for this phase."""
    phase_cfg = pipeline.get("phases", {}).get(phase, {})
    inputs_cfg = phase_cfg.get("inputs", {})
    required = inputs_cfg.get("required", [])

    context_parts = []
    for src_phase in required:
        f = _find_artifact_for_phase(run_dir, src_phase, pipeline)
        if f is not None:
            text = f.read_text()
            end = text.find("---", 3) if text.startswith("---") else -1
            body = text[end+3:].strip() if end > 0 else text.strip()
            context_parts.append(f"### {src_phase}\n\n{body}")

    return "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# Internal: metadata
# ---------------------------------------------------------------------------

def _inject_artifact_shas(artifact_path: Path, run_dir: Path,
                          pipeline: Dict[str, Any], phase: str,
                          model: str, model_cfg: Dict[str, Any]) -> None:
    """Post-process artifact: replace placeholder SHA256 with real values.

    Models in OT subprocesses cannot access upstream artifact files, so they
    fill in dummy SHA256 values. The orchestrator computes the real SHA256
    for each upstream input and injects them into the artifact frontmatter.
    Only injects for inputs declared in pipeline.yaml for this phase.
    """
    if not artifact_path.exists():
        return
    try:
        import hashlib
        import yaml
        text = artifact_path.read_text()
        if not text.startswith("---"):
            return
        # Line-aware frontmatter parsing (matches tof.parse_frontmatter)
        lines = text.split('\n')
        if lines[0].strip() != "---":
            return
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            return
        frontmatter_str = '\n'.join(lines[1:end_idx])
        body = '\n'.join(lines[end_idx + 1:])
        fm = yaml.safe_load(frontmatter_str) or {}

        # Determine expected upstream inputs from pipeline config
        phase_cfg = pipeline.get("phases", {}).get(phase, {})
        required_inputs = phase_cfg.get("inputs", {}).get("required", [])

        # Inject assigned_model / assigned_family from models.yaml
        tof_section = fm.get("tof", {})
        if isinstance(tof_section, dict):
            produced = tof_section.get("produced_by", {})
            if isinstance(produced, dict):
                produced["assigned_model"] = model
                produced["assigned_family"] = model_cfg.get("family", "unknown")

            # Fix SHA256 for each input
            inputs = tof_section.get("inputs") or []
            injected = 0
            for inp in inputs:
                if not isinstance(inp, dict):
                    continue
                path_str = inp.get("path") or ""
                inp_phase = inp.get("phase") or ""

                # Only inject for phases declared as required inputs
                if inp_phase not in required_inputs:
                    continue

                # Resolve safely: only within run_dir, no traversal
                try:
                    upstream_path = (run_dir / path_str).resolve()
                    if not str(upstream_path).startswith(str(run_dir.resolve())):
                        print(f"  WARNING: input path '{path_str}' escapes run_dir, skipping SHA injection")
                        continue
                except (ValueError, OSError):
                    continue

                if upstream_path.exists() and upstream_path.is_file():
                    sha = hashlib.sha256(upstream_path.read_bytes()).hexdigest()
                    inp["sha256"] = sha
                    injected += 1
                elif inp_phase in required_inputs:
                    raise RuntimeError(
                        f"Required upstream '{path_str}' for phase {inp_phase} not found in {run_dir}. "
                        f"Cannot compute SHA256 for trust chain."
                    )
                else:
                    print(f"  WARNING: upstream '{path_str}' for phase {inp_phase} not found — keeping model-provided SHA")

            if injected:
                # Rebuild frontmatter YAML
                new_fm = yaml.dump(fm, default_flow_style=False, allow_unicode=True,
                                  sort_keys=False)
                new_text = "---\n" + new_fm.strip() + "\n---\n" + body
                artifact_path.write_text(new_text)
                print(f"  injected {injected} SHA256(s) into {artifact_path.name}")

    except Exception as e:
        print(f"  WARNING: SHA injection failed for {artifact_path.name}: {e}")

def _write_metadata(run_dir: Path, phase: str, session_id: str,
                    result: Dict[str, Any],
                    provenance_verified: Optional[bool] = None) -> None:
    """Write session-metadata.json alongside artifacts."""
    path = run_dir / f".session-metadata-{phase}.json"
    payload = {
        "phase": phase,
        "session_id": session_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assigned_model": result.get("assigned_model", "?"),
        "actual_model": result["actual_model"],
        "actual_family": result["actual_family"],
        "fallback_detected": result["fallback_detected"],
        "provider": result["provider"],
        "latency_ms": result["latency_ms"],
        "verification_confidence": result["verification_confidence"],
        "verification_method": result["method"],
        "outcome": result.get("outcome"),
        "provenance_verified": provenance_verified,
    }
    path.write_text(json.dumps(payload, indent=2))


def _write_timeout_exhausted_stub(artifact_path: Path, run_dir: Path,
                                   phase: str, model: str,
                                   dispatch_timeout: int) -> None:
    """Write a stub INVALID artifact when retry budget is exhausted."""
    import yaml
    stub = {
        "tof": {
            "run_id": run_dir.name,
            "phase": phase,
            "schema_version": "0.1",
            "round": 1,
            "produced_by": {
                "adapter": "fake",
                "assigned_model": model,
                "claimed_model": model,
                "assigned_family": "unknown",
                "actual_family": "unknown",
            },
            "inputs": [],
        },
        phase: {
            "verdict": "TIMEOUT_EXHAUSTED",
            "reason": f"OT dispatch timed out after all retries ({dispatch_timeout}s per attempt)",
        },
    }
    content = "---\n" + yaml.dump(stub, default_flow_style=False,
                                   allow_unicode=True, sort_keys=False).strip() + "\n---\n"
    artifact_path.write_text(content)
    print(f"  wrote timeout stub: {artifact_path.name}")
    _write_metadata(run_dir, phase, "timeout-exhausted", {
        "actual_model": None,
        "actual_family": None,
        "fallback_detected": None,
        "provider": None,
        "latency_ms": None,
        "verification_confidence": 0.0,
        "method": "timeout_exhausted",
    })


def _write_unverified_metadata(run_dir, phase, session_id, assigned_model, reason):
    """Write metadata when session audit itself fails (e.g., log unreadable).

    fallback_detected=None means "audit could not determine" — distinguished
    from False (verified no fallback) and True (fallback confirmed).
    """
    path = run_dir / f".session-metadata-{phase}.json"
    payload = {
        "phase": phase,
        "session_id": session_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "assigned_model": assigned_model,
        "actual_model": None,
        "actual_family": None,
        "fallback_detected": None,
        "provider": None,
        "latency_ms": None,
        "verification_confidence": 0.0,
        "verification_method": "unverified",
        "unverified_reason": reason,
    }
    path.write_text(json.dumps(payload, indent=2))


# ---------------------------------------------------------------------------
# Internal: prompt preprocessing
# ---------------------------------------------------------------------------

def _preprocess_prompt(prompt: str, run_dir: Path, phase: str,
                        model: str, model_cfg: Dict[str, Any]) -> str:
    """Replace FILL WITH placeholders before OT dispatch.

    Known metadata placeholders get concrete values. Content placeholders
    become {{MARKER}} templates that models can safely fill in without
    triggering echo detection.
    """
    # Known metadata — replace with concrete values
    prompt = prompt.replace("FILL WITH RUN ID", run_dir.name)
    prompt = prompt.replace("FILL WITH ROUND NUMBER", "1")
    prompt = prompt.replace("FILL WITH MODEL NAME", model)
    prompt = prompt.replace("FILL WITH FAMILY", model_cfg.get("family", "unknown"))

    # SHA placeholders — mark for post-dispatch injection
    prompt = re.sub(
        r'FILL WITH SHA256 OF \w+ ARTIFACT',
        '{{SHA_WILL_BE_INJECTED}}',
        prompt, flags=re.IGNORECASE
    )

    # Remaining FILL WITH — convert to safe template markers
    # Order matters: descriptive text (must contain at least one lowercase)
    # before PASS|FAIL (all caps, pipes, underscores only).
    # FILL WITH <descriptive text> → {{FIELD: descriptive text}}
    # Requires [a-z] to distinguish from all-caps tokens like PASS|FAIL.
    prompt = re.sub(
        r'FILL WITH ([A-Z][A-Za-z ]*[a-z][A-Za-z ]*)',
        r'{{FIELD: \1}}',
        prompt
    )
    # FILL WITH PASS|FAIL → {{FIELD: PASS|FAIL}}
    prompt = re.sub(
        r'FILL WITH ([A-Z_| ]+)',
        r'{{FIELD: \1}}',
        prompt
    )
    # Catch-all: any remaining isolated FILL WITH
    prompt = prompt.replace("FILL WITH", "{{FIELD}}")

    return prompt


# ---------------------------------------------------------------------------
# Internal: config snapshot
# ---------------------------------------------------------------------------

def _snapshot_configs(run_dir: Path, tof_dir: Path) -> None:
    """Snapshot pipeline.yaml and models.yaml into run_dir/.tof/

    This ensures the run uses an immutable config snapshot, preventing
    mid-run config drift from invalidating the trust chain.
    """
    import shutil

    snap_dir = run_dir / ".tof"
    snap_dir.mkdir(parents=True, exist_ok=True)
    for fname in ("pipeline.yaml", "models.yaml"):
        src = tof_dir / fname
        if src.exists():
            shutil.copy2(src, snap_dir / fname)


# ---------------------------------------------------------------------------
# Internal: config loading
# ---------------------------------------------------------------------------

def _load_pipeline(tof_dir: Path) -> Dict[str, Any]:
    import yaml
    path = tof_dir / "pipeline.yaml"
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _load_models(tof_dir: Path) -> Dict[str, Any]:
    import yaml
    path = tof_dir / "models.yaml"
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("models", {})


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="tof-run", description="TOF Orchestrator")
    parser.add_argument("run_dir", help="TOF run directory")
    parser.add_argument("--step", action="store_true", help="Single-step mode")
    args = parser.parse_args()
    sys.exit(run(args.run_dir, step_mode=args.step))
