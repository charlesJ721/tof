#!/usr/bin/env python3
"""ModelRegistryAdapter — validates model slugs against live provider endpoints.

Reads models.yaml, queries each provider's /v1/models, and checks whether
the provider_model_id slugs still exist. Reports stale models and updates
freshness_checked_at on success.

Usage:
    python3 model_registry_adapter.py                # check all models
    python3 model_registry_adapter.py --model gpt-5.5  # check single model
    python3 model_registry_adapter.py --json           # machine-readable output

Adapter contract: read_registry(models_yaml_path) -> {status, report, stale_models}
Orchestrator calls check_model(model_id) before dispatch.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


# ---------------------------------------------------------------------------
# Provider endpoints
# ---------------------------------------------------------------------------

PROVIDER_ENDPOINTS: Dict[str, str] = {
    "openrouter": "https://openrouter.ai/api/v1/models",
    "deepseek": "https://api.deepseek.com/v1/models",
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def check_model(model_id: str, models_yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Validate a single model slug against its provider endpoint.
    
    Returns {status, model_id, provider, provider_model_id, fresh, error}.
    status: 'fresh' | 'stale' | 'unknown_model' | 'network_error' | 'skipped'
    """
    registry = _load_registry(models_yaml_path)
    if model_id not in registry["models"]:
        return {"status": "unknown_model", "model_id": model_id, "error": "not in registry"}
    
    cfg = registry["models"][model_id]
    provider = cfg.get("provider", "")
    slug = cfg.get("provider_model_id", model_id)
    
    if provider not in PROVIDER_ENDPOINTS:
        return {"status": "skipped", "model_id": model_id, "error": f"no endpoint for provider '{provider}'"}
    
    try:
        known_slugs = _fetch_model_list(provider)
    except Exception as e:
        return {"status": "network_error", "model_id": model_id, "provider": provider, "error": str(e)}
    
    fresh = slug in known_slugs
    return {
        "status": "fresh" if fresh else "stale",
        "model_id": model_id,
        "provider": provider,
        "provider_model_id": slug,
        "fresh": fresh,
        "error": None if fresh else f"slug '{slug}' not found; closest: {_closest_match(slug, known_slugs)}",
    }


def check_all(models_yaml_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Validate all models in registry. Returns list of per-model results."""
    registry = _load_registry(models_yaml_path)
    results = []
    for model_id in registry.get("models", {}):
        results.append(check_model(model_id, models_yaml_path))
    return results


def read_registry(models_yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Full registry audit. Returns {status, stale_models, report_lines, checked_at}."""
    results = check_all(models_yaml_path)
    stale = [r for r in results if r["status"] == "stale"]
    errors = [r for r in results if r["status"] == "network_error"]
    
    status = "ok"
    report = []
    if stale:
        status = "stale_models"
        report.append(f"STALE ({len(stale)}):")
        for r in stale:
            report.append(f"  - {r['model_id']}: {r['error']}")
    if errors:
        if not stale:
            status = "network_error"
        report.append(f"ERROR ({len(errors)}):")
        for r in errors:
            report.append(f"  - {r['model_id']} ({r['provider']}): {r['error']}")
    if not stale and not errors:
        fresh_count = len([r for r in results if r["status"] == "fresh"])
        skipped = len([r for r in results if r["status"] == "skipped"])
        report.append(f"All {fresh_count} models fresh" + (f" ({skipped} skipped)" if skipped else ""))
    
    return {
        "status": status,
        "stale_models": [r["model_id"] for r in stale],
        "results": results,
        "report_lines": report or ["All models fresh."],
        "checked_at": date.today().isoformat(),
    }


def update_freshness_dates(models_yaml_path: Optional[Path] = None) -> Dict[str, Any]:
    """Check all models and update freshness_checked_at for fresh ones.
    
    Only writes to models.yaml if models are fresh — stale models
    keep their old date so the staleness is visible.
    """
    registry = _load_registry(models_yaml_path)
    results = check_all(models_yaml_path)
    today = date.today().isoformat()
    updated = 0
    
    for r in results:
        if r["status"] == "fresh" and r["model_id"] in registry["models"]:
            registry["models"][r["model_id"]]["freshness_checked_at"] = today
            updated += 1
    
    if updated > 0 and models_yaml_path:
        _write_registry(models_yaml_path, registry)
    
    return {
        "status": "updated" if updated > 0 else "no_changes",
        "updated_count": updated,
        "checked_at": today,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_registry(path: Optional[Path] = None) -> Dict[str, Any]:
    if path is None:
        path = Path(__file__).resolve().parent / "models.yaml"
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _write_registry(path: Path, registry: Dict[str, Any]) -> None:
    with open(path, "w") as f:
        yaml.dump(registry, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  updated freshness_checked_at in {path}")


def _fetch_model_list(provider: str) -> set[str]:
    """Fetch available model slugs from provider endpoint. Returns set of model IDs."""
    endpoint = PROVIDER_ENDPOINTS[provider]
    cmd = ["curl", "-s", "--max-time", "15", endpoint]
    
    # OpenRouter may need proxy; use TOF_OPENROUTER_PROXY or https_proxy.
    # No default fallback — if neither is set, curl connects directly.
    env = None
    if provider == "openrouter":
        proxy_url = os.environ.get("TOF_OPENROUTER_PROXY",
                                   os.environ.get("https_proxy"))
        if proxy_url:
            env = {**os.environ, "https_proxy": proxy_url}
    
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=20, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"curl failed: {proc.stderr.strip()}")
    
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"invalid JSON from {endpoint}")
    
    models = data.get("data", data.get("models", []))
    slugs: set[str] = set()
    for m in models:
        slug = m.get("id") or m.get("name") or ""
        if slug:
            slugs.add(slug)
    return slugs


def _closest_match(slug: str, known: set[str]) -> str:
    """Find the best matching slug for a stale model ID."""
    # Exact match
    if slug in known:
        return slug
    # Prefix match (e.g., 'google/gemini-3.1-pro' matches 'google/gemini-3.1-pro-preview')
    prefix_matches = [s for s in known if s.startswith(slug) or slug.startswith(s)]
    if prefix_matches:
        return prefix_matches[0]
    # Levenshtein-like: most shared prefix
    best = max(known, key=lambda s: _shared_prefix_len(slug, s), default="?")
    return best


def _shared_prefix_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            n += 1
        else:
            break
    return n


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="model-registry-adapter", description="Validate model slugs")
    parser.add_argument("--model", help="Check a single model")
    parser.add_argument("--json", action="store_true", help="Machine-readable output")
    parser.add_argument("--update", action="store_true", help="Update freshness_checked_at for fresh models")
    args = parser.parse_args()
    
    if args.update:
        result = update_freshness_dates()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Updated {result['updated_count']} model(s) at {result['checked_at']}")
        sys.exit(0 if result["status"] == "updated" else 1)
    
    if args.model:
        result = check_model(args.model)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status_icon = {"fresh": "✓", "stale": "✗", "network_error": "⚠", "unknown_model": "?", "skipped": "○"}
            icon = status_icon.get(result["status"], "?")
            print(f"{icon} {result['model_id']}: {result['status']}")
            if result.get("error"):
                print(f"  {result['error']}")
        sys.exit(0 if result["status"] == "fresh" else 1)
    
    # Default: check all
    report = read_registry()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for line in report["report_lines"]:
            print(line)
    sys.exit(0 if report["status"] == "ok" else 1)
