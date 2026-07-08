# Phases — Full Specification

> Each phase is an independent workflow node. Node inputs are always upstream .md files. Node outputs are always structured .md files consumed by the next node. No conversation history is shared between nodes.

---

## Phase 0: Clarify

**Purpose:** Align on what the task actually is — before any research, design, or execution.

**Model:** The orchestrator's main conversational model (fast/cheap tier)

**Output:** `TASK.md`

**Required fields:**
```markdown
## Scope — what this task covers
## Success Criteria — verifiable outcomes
## Explicit Exclusions — what is NOT in scope
## Constraints — must-adhere limits
```

**User signal handling:**

| User says | Framework action |
|-----------|-----------------|
| "Start from scratch" / "Don't build on existing code" | **Immediate clean-slate switch** — don't discuss existing code |
| "Just give me the result, skip confirmations" | Compress checkpoints, but **never skip Review** |
| "I'm getting impatient" | Pause, restate the problem from essence |

**Door:** max 3 rounds of clarification. User explicit confirmation to proceed.

---

## Phase 1: Scout

**Purpose:** Research before design. Understand the landscape before choosing a solution.

**Model:** A model strong in structured analysis and identifying edge cases (high SWE-bench score)

**Execution:** Dispatch to a dedicated subprocess or subagent running in an isolated session

**Output:** `RESEARCH.md`

**Required fields (frontmatter dotted paths):**
```yaml
scout.affected_files        — files that need to change
scout.dependency_graph      — inter-file dependency DAG
scout.verification_functions — verifiable checks for each step
scout.risk_areas            — high-risk modules
scout.unknowns              — things we don't know yet (MUST be non-empty)
scout.implicit_dependencies — dependencies that aren't in the code
```

**Quality gate:**
- `scout.affected_files` empty? → Scout FAILED, retry once
- `scout.unknowns` empty or non-list, or `scout.unknowns.min_items=1` fails → INVALID
- `scout.risk_areas` present? → continue; if absent → WEAKNESS_FOUND

**Mode decision point (after Scout automatically):**

If `unknowns` ≥ 3 with keywords like "architectural assumption", "dependency uncertainty", "black box module", the orchestrator should propose switching to **exploration mode**:

> "Detected {N} high-uncertainty black boxes ({list 2-3}). Propose switching to **guided exploration mode**: run A/B parallel probes (Scout → quick Implement) on both directions, converge based on empirical results, then proceed."

---

## Phase 2: Establish

**Purpose:** Design the solution. Produce a plan that can be reviewed, challenged, and verified independently.

**Model:** A model with strong architectural reasoning

**Execution:** Dedicated subprocess or subagent, fresh session

**Output:** `PLAN.md`

**Required fields (frontmatter dotted paths):**
```yaml
establish.architecture          — description of the approach
establish.steps[]               — per step: file path + change description
establish.verification_functions — executable verification checks
establish.rollback              — rollback strategy
establish.out_of_scope          — what is explicitly NOT being done now
establish.execution_mode        — sync | async | split
```

**`execution_mode` decides how Implement runs:**

| Mode | When | How |
|------|------|-----|
| **sync** (default) | L1-L2, estimated <120s | Dispatch synchronously |
| **async** | Single task >120s, crash-resistance matters | Dispatch asynchronously, result returned when done |
| **split** | >50K tokens or high concurrency risk | Split into 2+ parallel tasks, each independently verified |

**Quality gate:**
- Plan ≤ minimum verifiable complexity (over-engineering = FAIL)
- User confirms plan before proceeding to Review

---

## Phase 3: Review

**Purpose:** Find the blind spots. The review model must be from a **different model family** than the design model — same-family models share architecture biases and tend to miss the same things.

**Model:** A model from a different family than Establish (e.g., if Establish used a transformer-encoder model, Review should use a different architecture)

**Execution:** Dedicated subprocess or subagent, fresh session

**Output:** `REVIEW.md`

**Required fields:**
```yaml
review.verdict: PASS | WEAKNESS_FOUND | BLOCKING
review.findings:
  - type: "design_flaw | security_issue | missing_edge_case | over_engineering | assumption_error"
    severity: "high | medium | low"
    description: "specific problem description"
review.blocking:
  - "item that must be fixed before proceeding"
```

**Adversarial Review (L3 + high risk):**

For high-stakes tasks, a two-sided review:
1. **Red Team** attacks the plan — finds security holes, edge cases, failure modes
2. **Blue Team** defends the plan — checks fixes, validates mitigations
3. **Judge** adjudicates — decides which findings are real

All three must be actual model calls from independent sessions, not the same model self-dialoguing.

**Quality gate:**
- BLOCKING → bounce back to Establish (max 2 rounds)
- 2 rounds still BLOCKING → Phase EX (escalation)

---

## Phase 4: Implement

**Purpose:** Execute the reviewed plan. Strictly — no redesign, no scope creep.

**Model:** The model with the highest terminal/execution benchmark score

**Execution:** Dedicated subprocess or subagent

**Output:** Code diff + test results + `IMPLEMENTATION_LOG.md`

**Self-check before Implement:**
> "The assigned implementer beats me by 20% on terminal benchmarks. Am I dispatching this, or defaulting to myself?"

**Rules:**
- Deliver in batches, not one massive diff
- **Execute only** — if the plan is wrong, bounce to Establish; don't redesign mid-execution
- Max 2 retry rounds for execution errors

**Quality gate:**
- Each batch independently verified
- All tests pass before declaring done

---

## Phase 5: Verify

**Purpose:** Two independent verification passes. The orchestrator checks plan adherence; a separate model does a deep independent review.

**Step 1 — Orchestrator verification:**
- Read `PLAN.md`, the diff, and `IMPLEMENTATION_LOG.md`
- Check each `verification_function` in the plan
- Report mismatches

**Step 2 — Independent verification:**
- Fresh session, different model
- Independently review the implementation against the plan

**Output:** `VERIFICATION.md`
```markdown
verify.verdict: PASS | FAIL
verify.mismatches:
  - expected: "what the plan said"
    actual: "what was implemented"
verify.vf_results:
  - vf_name: "name of verification check"
    passed: true | false
    output: "actual output"
```

**Quality gate:**
- FAIL → back to Implement (max 2 rounds)
- 2 rounds still FAIL → Phase EX (escalation)

---

## Phase 5.5: Knowledge Deposition (Optional)

**Purpose:** After methodology-level work (new patterns, bug workarounds, design decisions), optionally persist the knowledge for future sessions.

**Status in P0 runtime:** Deposition is an **optional terminal phase** in `pipeline.yaml` (`deposition.optional: true`). It is NOT a correctness gate — a `VERIFY PASS` result means the primary task is complete regardless of deposition status. Channel failures are logged but do not block task completion.

The five conceptual channels are:

| Channel | Consumer | Verification |
|---------|----------|-------------|
| Skill/procedure file | Future sessions | File exists |
| Memory system | Every turn | Memory tool recorded it |
| Wiki/Knowledge base | Manual search | Note exists |
| Raw/Diary | Nightly archive | File in raw directory |
| DT Hub / Public API | Semantic diff | Pushed and indexed |

Future versions may implement pluggable `KnowledgeDepositionAdapter` implementations. In the current runtime, deposition is a terminal phase that can be marked DONE, PARTIAL, or SKIPPED — all three exit normally.

---

## Phase EX: Escalation

**Trigger:** Any phase fails its quality gate after all retries.

**Escalation contract (four elements):**
1. **Precise conflict point** — which step, which assumption, which file
2. **Both sides' positions** — reproducing the disagreement
3. **Judge's assessment** — the orchestrator's own position
4. **User options** — minimal-choice menu (2-4 options)

**Post-escalation:** Archive the full conflict trace to `TOF Records/YYYY-MM-DD Task/postmortem/`.
