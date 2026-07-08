# Orchestrator Threads (OT) — True Multi-Model Routing

> **The single hardest problem in multi-model orchestration isn't choosing which model — it's ensuring the chosen model actually executes the work.**

## The Problem

Almost every agent framework provides a delegation API — "spawn a subagent to handle this task." The promise: assign different models to different subagents. The reality:

- The subagent **inherits the parent's model configuration** (API key, base URL, model name)
- Runtime configuration changes don't affect already-running subagents (configuration is cached at startup)
- The model name you specified gets **overridden by the default delegation config** before reaching the API
- The only person who knows a fallback happened is the API log — the subagent reports it used the model you asked for

This creates a silent but catastrophic failure mode: **claimed multi-model pipeline that's actually a single model doing all the work.**

## The Solution: Orchestrator Threads

An Orchestrator Thread (OT) is a **subprocess invocation** that explicitly specifies both the provider and model:

```bash
# OT pattern — spawn a new agent process with explicit model routing
clio chat --provider primary-provider --model claude-opus-4.8 -q "Scout the codebase for affected files"
```

Key differences from framework-level delegation:

| Aspect | Framework Delegation | Orchestrator Thread |
|--------|--------------------|--------------------|
| Model inheritance | Inherits parent model config | Explicit per-invocation |
| Configuration cache | Cached at process start | Reads fresh config each time |
| Process isolation | Same language runtime | OS-level process isolation |
| Log traceability | Claims parent model | Actual model in process log |
| Fallback risk | Silent, no notification | Logged as error on failure |

## OT Verification Protocol

The model you asked for ≠ the model that executed. Verification is non-optional.

### L1: Session Record Check

After each OT completes, check the session record to confirm the actual model:

```bash
# Query session records for the dispatched OT
session-tool export /tmp/verify.jsonl
grep "SOURCE_TAG" /tmp/verify.jsonl | parse-session-info
```

Expected output shows the actual model, provider, and source tag:

```
Model: claude-opus-4.8    Provider: primary   Source: ot-scout-task  ← PASS
```

If multiple phases all show the same model, the pipeline is fake — invalidate and redo.

### L2: Cross-Session Audit

A healthy pipeline produces 4-5 independent sessions:
1. Orchestrator session (source: cli)
2. Scout session (source: ot-scout-*)  
3. Establish session (source: ot-establish-*)
4. Review session (source: ot-review-*)
5. (Optional) Task definition writer (source: ot-pro-*)

If they all show the same model, the multi-model pipeline never happened.

### L3: API Log Trace

For forensic verification when model records seem wrong, trace the actual API calls:

```bash
grep "API call #1" ~/agent/logs/agent.log | grep "<session_id>"
grep "Fallback activated" ~/agent/logs/agent.log | grep "<session_id>"
```

The first API call line shows the actual model the HTTP client used. If it doesn't match the assigned model, fallback occurred silently.

## Common OT Failure Modes

### 1. Model ID Outdated

Model slugs change with version releases. A slug that worked last week may 404 today.

**Prevention:** Before dispatching to a model for the first time in a session, verify the model ID is still valid:

```bash
# Check available models matching your target
curl -s "https://models-endpoint/v1/models" | select-model "target-model-name"
```

### 2. Model Timeout

Some models have longer response times, especially under long prompts. Through a proxy/tunnel, response times can double.

**Protocol for timeouts:**
1. Report the timeout fact — which model, how many attempts, what the chain looks like
2. **Do NOT silently fallback** to a different model or self-execute
3. Wait for a decision: retry / switch model / skip verification

### 3. Orchestrator Pre-Emption

The orchestrator starts doing the downstream phase's work "while waiting" — researching what Scout should research, drafting what Establish should design.

**The boundary:** Gathering raw materials as context for the downstream phase is OK. Forming analytical conclusions and writing the phase's deliverable is NOT OK.

**Test:** Did the analysis and judgment in the phase output come from the assigned model, or from the orchestrator? If the orchestrator wrote the conclusions and the phase model just approved them — the pipeline is fake.

## OT Dispatch Pattern (Generic)

```bash
# Each phase in the pipeline
ot_dispatch() {
  local phase="$1"     # scout | establish | review | implement
  local model="$2"     # fully-qualified model ID
  local prompt="$3"    # self-contained task description
  local provider="$4"  # provider routing

  clio chat --provider "$provider" --model "$model" -q "$prompt"
  
  # Immediately verify
  verify_model "$phase" "$model"
}
```

## Summary

| Rule | Why |
|------|-----|
| Always use subprocess routing for multi-model pipelines | Framework-level delegation inherits parent model; subprocesses are truly isolated |
| Verify every dispatch | An unverified model assignment is an unverifiable pipeline |
| Never silently fallback on timeout | A pipeline that reports "Opus reviewed" but actually used Claude Sonnet is a fake pipeline |
| Report before re-routing | Let user/system decide what to do when the assigned model is unavailable |
