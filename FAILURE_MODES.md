# Failure Modes

> Every pattern in TOF was discovered by fixing a failure. This document is the incident log. Read it before you modify the framework — the constraints here were paid for in broken pipelines and wasted hours.

---

## FM-1: The Orchestrator Does Everything

**The problem with a single model:** The orchestrator model is fast, responsive, and already has the conversation context. After defining the task in Phase 0, it's deeply tempted to just "keep going" — do the research, write the design, review its own work, implement. The pipeline collapses to a single model doing everything.

**Symptoms:**
- All phases show the same model in session records
- The orchestrator outputs analytical content that should have come from the Scout phase
- "I delegated to Opus" but no corresponding subprocess was spawned — it was done in the main conversation

**Root cause:** LLMs default to "executor" before "orchestrator." Reasoning about how to do a task primes the model to do it itself. By the time it considers delegation, it's already framed the problem in terms of its own execution.

**Fix:**
- Enforce a **Who-before-How** ordering — decide the executor before thinking about execution strategy
- If you catch yourself thinking "how would I do this" — stop and redo the allocation
- After every OT dispatch, verify the session record shows the correct model

**Self-test:**
> Does the output of each phase contain analysis and judgment from the assigned model, or did the orchestrator write it all and the assigned model just rubber-stamp it?

---

## FM-2: Delegation Config Cache

**The problem with configuration-dependent delegation:** You configure `delegation.model: opus-4.8`, save the file, and dispatch a subagent. The subagent runs on your previous configuration's model — the configuration was cached at process start.

**Symptoms:**
- Changed `delegation.model` in config, dispatched, subagent still uses old model
- "I set it to Opus!" — session records show Sonnet
- Works after a process restart, then breaks again on the next config change

**Root cause:** The delegation configuration is read once at process startup and cached in memory. Runtime config file changes have no effect on already-running processes.

**Fix:**
- Don't rely on delegation APIs for multi-model routing — they're dependent on startup-time configuration
- Use Orchestrator Threads (OT) — subprocess invocations that accept explicit model parameters per call
- If you must use delegation APIs, restart the agent process after every config change

---

## FM-3: Silent Fallback on Timeout

**The problem with resilience:** The assigned model for a phase (e.g., the Review model) takes too long. The orchestrator, rather than report the timeout and wait for a decision, silently switches to itself or a faster model. The pipeline records "Review complete" but the review was done by a different model than planned.

**Symptoms:**
- A phase that normally takes 30s completes in 2s — suspiciously fast
- Review findings are shallow compared to previous runs
- User asks "which model reviewed this?" — the answer requires digging into API logs

**Root cause:** The model timed out, fallback logic kicked in, and no alert was raised. The orchestrator has strong incentive to keep moving rather than surface obstacles.

**Fix:**
- **Never silently fallback on model timeout.** The only valid actions when the assigned model is unavailable:
  1. Report the fact (which model, what error, how many retries)
  2. Wait for a decision (retry / switch model / skip)
- Do NOT self-execute the phase work. If you can't get the assigned model, you can't get the model diversity that justifies the pipeline.
- **Timeout protocol:** max 3 retries at 60s intervals. If the assigned model cannot respond after 3 attempts, mark the phase as BLOCKING and escalate to Phase EX. Do not leave the pipeline hanging indefinitely.

---

## FM-4: Skip Review, Implement Directly

**The problem with flow:** Scout finds the affected files, Establish designs the solution — feels "done enough." The orchestrator skips Review and goes straight to Implement. The implementation is clean, tests pass. But a design flaw that Review would have caught ships to production.

**Symptoms:**
- No REVIEW.md artifact in the phase archive
- Implement phase includes design decisions that weren't in the plan
- Later: "we should have caught this earlier"

**Root cause:** Review feels like overhead when the design seems solid. But that's exactly when it matters most — when the design looks right to the same model family that produced it.

**Fix:**
- **Review is not optional.** The entire pipeline exists because one model's blind spots need another model to catch them.
- If the plan is obvious and clean, Review should be quick (PASS with minor findings). If there's nothing to find — good, that's the best outcome. But the check must happen.
- The Review phase in the real deployment caught a fundamental architecture mistake ("add a consciousness/ layer") that would have been costly to undo. Skipping Review means that fix doesn't happen.

---

## FM-5: Constraints Added by Designer, Not User

**The problem with creative design:** The Establish phase model adds a design constraint — "don't modify the framework, use an external wrapper" — that seems reasonable. The constraint propagates through all downstream phases. No one questions its origin. The user later asks "who said we can't modify the framework?"

**Symptoms:**
- Downstream phases produce valid work that solves an artificially constrained problem
- User discovers the real constraint after implementation
- "That's not what I asked for — I never said that"

**Root cause:** The designer model, trying to be helpful, self-imposed a limit that seemed safe. The orchestrator didn't validate it because it came from an upstream phase. The constraint propagated like an axiom that was never stated.

**Fix:**
- After every phase, validate each design constraint against its source:
  - **[User requirement]** → pass through
  - **[System limitation]** → annotate and pass
  - **[Designer assumption]** → **pause, confirm with user, then pass**
- The orchestrator must check: "Where did this constraint come from? Did the user say this, or did the designer invent it?"

---

## FM-6: Model ID Rot

**The problem with rapid iteration:** Model slugs change. Google `gemini-3.1-pro-preview` was available. Then Google released `gemini-3.1-pro-preview-05`. Then that one stopped working. The orchestrator specifies the old slug, the API returns a grace response (fuzzy matching catches it), but eventually the old slug returns an error.

**Symptoms:**
- OT dispatch returns 400/404 occasionally
- Some pipeline runs work, some don't
- The fuzzy match buys time but degrades performance

**Root cause:** Model IDs in the TOF config are hardcoded strings. No one audits them regularly. The model ecosystem moves faster than the framework.

**Fix:**
- Verify model IDs before each TOF session: check the provider's model list for your target model
- If an ID is expired, don't guess the replacement — check docs
- Add a `MODEL_ASSIGNMENT.md` freshness date

---

## FM-7: Delegate_Task Model Cache (Framework-Level Bug)

**The problem with delegation APIs:** The sub-agent delegation API caches model/provider config at gateway startup. Runtime config changes are invisible. This isn't a TOF-level bug — it's a framework-level design issue where configuration is read once and never refreshed.

**Symptoms:**
- Setting `delegation.model: newest-model` in config → children still run old-model
- Only resolvable by full gateway restart
- Works locally but fails in CI/long-running deployments

**Root cause:** The delegation system follows a "snapshot at startup" pattern. This is fine for stable configs but fatal for dynamic multi-model routing.

**Fix (workaround):** Use OT subprocesses for all multi-model routing. The subprocess pattern reads fresh config on each invocation.

**Fix (upstream):** Add a config-watch mechanism or API endpoint to invalidate the delegation cache without full restart.

---

## FM-8: Metrics Creep — The Framework Becomes Self-Referential

**The problem with meta-complexity:** TOF becomes complex enough that modifying it requires running the full TOF pipeline on itself. New rules are added faster than old rules are validated. The framework becomes heavier than the problems it solves.

**Symptoms:**
- SKILL.md exceeds 500 lines
- More than 5 hard enforcement mechanisms
- Each mechanism requires >20 lines of Python to verify
- Adding a new rule requires running the full pipeline

**Root cause:** Every real failure adds a rule. But rule accumulation has diminishing returns — each additional rule has lower marginal benefit and higher cognitive load.

**Fix:**
- Before adding a new rule: "Is this rule simpler than the failure it prevents?"
- Periodically audit: rules → fix ratio. If rules exceed fixes, prune.
- Constraints limit: 500 lines per design doc, 5 hard mechanisms, 20-line verification per mechanism.

---

## Summary Table

| FM | Name | Severity | Prevention |
|----|------|----------|------------|
| 1 | Orchestrator does everything | 🔴 Critical | Who-before-How; verify session records |
| 2 | Delegation config cache | 🔴 Critical | Use OT subprocesses; not delegation APIs |
| 3 | Silent fallback on timeout | 🔴 Critical | Report timeouts; never self-execute |
| 4 | Skip Review | 🟠 High | Review is mandatory; not skippable |
| 5 | Constraints from designer, not user | 🟠 High | Validate constraint origin after every phase |
| 6 | Model ID rot | 🟡 Medium | Verify ID freshness per session |
| 7 | Framework delegation bug | 🟡 Medium | Workaround: OT subprocesses |
| 8 | Metrics creep | 🟡 Medium | Rules <500 lines; 5 mechanism cap |
