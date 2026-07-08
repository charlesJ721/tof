"""SessionAuditAdapter — reads agent.log to verify which model actually executed.

P0 Minimal implementation. Parses agent.log API call lines.
Agreed interface: read_session(session_id, log_path, assigned_model, models_registry) -> (AuditOutcome, dict).
Adapters return facts, do not orchestrate.  Orchestrator merges output into metadata.json.
"""

import re
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


class AuditOutcome(Enum):
    """Structured audit result for session verification."""
    VERIFIED_MATCH = "verified_match"         # API model == registry assigned model
    VERIFIED_MISMATCH = "verified_mismatch"   # API model != registry (fallback occurred)
    UNVERIFIED = "unverified"                 # agent.log exists but format unrecognized
    UNAVAILABLE = "unavailable"               # agent.log not found / session_id not in log
    UNKNOWN_MODEL = "unknown_model"           # API model not in models.yaml registry
    EXCEPTION = "exception"                   # audit process itself threw an error


def _resolve_model_alias(actual_model, models_registry):
    """Resolve a log-level model ID to the registry alias.

    Agent log lines use provider-specific model IDs (e.g., openai/gpt-5.5),
    while models.yaml keys are provider-agnostic aliases (e.g., gpt-5.5).
    This function does bidirectional lookup: returns the registry alias
    whether the input matches the alias key or the provider_model_id value.
    """
    if not actual_model:
        return None
    # Direct match: actual_model is already the alias
    if actual_model in models_registry:
        return actual_model
    # Reverse lookup: actual_model matches a provider_model_id
    for alias, cfg in models_registry.items():
        if isinstance(cfg, dict) and cfg.get("provider_model_id") == actual_model:
            return alias
    return None


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def read_session(
    session_id: str,
    log_path: str,
    assigned_model: str,
    models_registry: Dict[str, Any],
) -> Tuple[AuditOutcome, Dict[str, Any]]:
    """Read agent.log and return (outcome, detail_dict).

    outcome classifies the trustworthiness of the session's model routing.
    detail_dict carries raw fields for metadata and validation.
    """
    path = Path(log_path).expanduser()
    if not path.exists():
        return (AuditOutcome.UNAVAILABLE, _unverified_result("log file not found"))

    try:
        lines = _grep_session(path, session_id)
    except OSError:
        return (AuditOutcome.EXCEPTION, _unverified_result("cannot read log file"))

    calls = _parse_api_calls(lines)
    if not calls:
        return (AuditOutcome.UNAVAILABLE, _unverified_result("no API calls found for session"))

    first = calls[0]
    actual_model = first.get("model") or None
    provider = first.get("provider") or None
    latency_ms = _parse_latency(first.get("latency"))

    # Determine fallback: multiple API calls with different models → fallback
    fallback_detected = False
    if len(calls) > 1:
        for c in calls[1:]:
            if c.get("model") and c["model"] != actual_model:
                fallback_detected = True
                break

    # Resolve actual_model to registry alias
    resolved_alias = _resolve_model_alias(actual_model, models_registry)

    actual_family: Optional[str] = None
    if resolved_alias:
        actual_family = models_registry[resolved_alias].get("family")

    # Determine outcome
    if not actual_model:
        outcome = AuditOutcome.UNVERIFIED
    elif not resolved_alias:
        outcome = AuditOutcome.UNKNOWN_MODEL
    elif resolved_alias != assigned_model:
        outcome = AuditOutcome.VERIFIED_MISMATCH
    elif fallback_detected:
        outcome = AuditOutcome.VERIFIED_MISMATCH
    else:
        outcome = AuditOutcome.VERIFIED_MATCH

    detail = {
        "actual_model": actual_model,
        "actual_family": actual_family,
        "fallback_detected": fallback_detected,
        "provider": provider,
        "latency_ms": latency_ms,
        "verification_confidence": 0.7 if actual_model else 0.0,
        "method": "log_parsed" if actual_model else "unverified",
        "outcome": outcome.value,
    }
    return (outcome, detail)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CALL_LINE_RE = re.compile(
    r"API call #(?P<n>\d+):\s*"
    r"model=(?P<model>\S+)\s+"
    r"provider=(?P<provider>\S+)\s+"
    r".*?latency=(?P<latency>[\d.]+)s"
)


def _grep_session(log_path: Path, session_id: str) -> list[str]:
    """Return all log lines containing the exact session_id bracket and 'API call'.
    
    Uses bracket-delimited match (e.g., '[20260705_151052_546f8f]') rather than
    bare substring, preventing false matches from partial session_id collisions
    or session_id appearing inside other fields (timestamps, cache stats, etc.).
    """
    bracket_pattern = f"[{session_id}]"
    result: list[str] = []
    with log_path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if bracket_pattern in line and "API call" in line:
                result.append(line.rstrip("\n"))
    return result


def _parse_api_calls(lines: list[str]) -> list[dict[str, str]]:
    """Parse API call lines, ordered by call number."""
    calls: list[tuple[int, dict[str, str]]] = []
    for line in lines:
        m = _CALL_LINE_RE.search(line)
        if m:
            calls.append((int(m.group("n")), {
                "model": m.group("model"),
                "provider": m.group("provider"),
                "latency": m.group("latency"),
            }))
    calls.sort(key=lambda x: x[0])
    return [c[1] for c in calls]


def _parse_latency(raw: Optional[str]) -> Optional[int]:
    """Parse latency string (e.g. '2.7') → milliseconds."""
    if raw is None:
        return None
    try:
        return int(float(raw) * 1000)
    except (ValueError, TypeError):
        return None


def _unverified_result(reason: str) -> Dict[str, Any]:
    """Return a result with null model fields — log unavailable."""
    return {
        "actual_model": None,
        "actual_family": None,
        "fallback_detected": None,
        "provider": None,
        "latency_ms": None,
        "verification_confidence": 0.0,
        "method": "unverified",
        "unverified_reason": reason,
    }
