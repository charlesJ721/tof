# TOF — Task Orchestration Framework

> **The first multi-model trust chain you can verify.**

TOF doesn't ask "what should the agent do next?" — it asks **"who should do this, and can we prove they actually did it?"**

Every pipeline phase runs as an isolated subprocess with an explicitly assigned model. Every artifact goes through five automatic checks. One broken link → all downstream phases invalidated. Nothing rots silently.

[![Tests](https://img.shields.io/badge/tests-48_PASS-brightgreen)]()
[![Pipeline](https://img.shields.io/badge/lint-0_errors_0_warnings-success)]()
[![License](https://img.shields.io/badge/license-MIT-orange)]()

---

## Why this exists

Most agent frameworks operate on trust. You ask the orchestrator to use a different model for review — it says it did. **How do you verify?**

In production, orchestrators have a built-in bias: they default to doing everything themselves. They skip delegations. They reuse the same model for "review" that they used for "planning." The failure is silent — the output looks fine, and you never know the pipeline was fake.

TOF was built to fix this. Every mechanism — the 5 checks, cascade invalidation, session audit, provenance hash — was added to fix a real failure observed during development. The failures are documented alongside the fixes in [FAILURE_MODES.md](FAILURE_MODES.md).

> **"An unverifiable pipeline is a fake pipeline."**

---

## Architecture: Dual-Layer Defense

```
                      ┌─────────────────────────────┐
                      │       TRIGGER LAYER          │  ← WHY would you use TOF?
                      │  tof triage → ledger → CI    │     (five steps, all mechanical)
                      └──────────────┬──────────────┘
                                     │ decides to dispatch
                      ┌──────────────▼──────────────┐
                      │      VERIFICATION LAYER      │  ← DID the pipeline actually run?
                      │  5 checks → cascade → audit  │     (four lines of defense)
                      └──────────────────────────────┘
```

### Trigger Layer (Five Steps)

The hardest problem isn't verifying the pipeline — it's remembering to start it. TOF's trigger layer is a forcing function that removes the orchestrator's ability to silently skip the pipeline:

| Step | Mechanism | What It Does |
|------|-----------|--------------|
| 1 | `tof run --only review` | Single-phase dispatch. Cost: 1/6th of full pipeline. Breaks the "all or nothing" deadlock. |
| 2 | `tof triage` | Adversarial routing advisor (~$0.001). A cheap model decides "should I delegate?" — before the orchestrator can rationalize doing it alone. |
| 3 | Execution ledger + `triage-stats` | Every run logged. Self-91%? The number tells the truth even when you won't. |
| 4 | CI guardrail | Core file changes require a family-different REVIEW.md in the diff. No fallback to stale reviews. |
| 5 | Recursive bootstrap | The CI guardrail's first enforced review (GPT-5.5 on DeepSeek-authored trigger layer) found a quoting crash the author would have shipped. **The loop turned, and it caught a real blind spot.** |

### Verification Layer (Four Lines of Defense)

Once the pipeline runs, TOF proves it ran honestly:

```
artifact A ──SHA256──▶ artifact B ──SHA256──▶ artifact C
     │                      │                      │
     │  1. Schema check     │  1. Schema check     │
     │  2. Input lineage    │  2. Input lineage    │
     │  3. Staleness        │  3. Staleness        │
     │  4. Model family     │  4. Model family     │
     │  5. Session audit    │  5. Session audit    │
     └──────────────────────┴──────────────────────┘
                    Any INVALID → cascade all downstream
```

| Defense | What it catches | Why it's hard |
|---------|----------------|---------------|
| **Provenance gate** | Fake/fixture/self-reported audit evidence | Session_audit used to trust any outcome field — now rejects untrusted sources |
| **actual-vs-assigned cross-check** | Model-swap without audit flagging it | Metadata says `verified_match` but `actual≠assigned` → BLOCKING |
| **Family pre-audit consumption** | Self-validating family check | Family validation now reads log-derived facts, not the artifact's self-report |
| **Provenance hash** | Orchestrator wrote artifact without dispatching (FM-1) | Artifact body must appear in OT subprocess stdout |

These four defenses were hardened through three rounds of independent adversarial review. The full response is documented in [REVIEW.md](REVIEW.md).

---

## One Minute

```bash
pip install pyyaml
git clone https://github.com/charlesJ721/tof.git
cd tof

# Validate a sample pipeline run
./tof validate test-fixtures/test-smoke-full-pipeline \
  --pipeline pipeline.yaml --models models.yaml

# Should I delegate this task?
./tof triage "Refactor the auth module to support OIDC"

# What does my delegation pattern look like?
./tof triage-stats
```

---

## Five Automatic Checks

Every artifact passes five independent checks:

| Check | What it catches |
|-------|----------------|
| **schema** | Missing required fields, wrong types, echo artifacts (`{{FIELD:}}` residuals) |
| **input linkage** | SHA256 mismatch between declared upstream reference and actual artifact |
| **staleness** | Downstream artifact not rebuilt after upstream changed |
| **model family** | Review model family == Establish model family (defeats diversity) |
| **session audit** | Agent log shows a different model ran than what was assigned |

One INVALID → cascade. Fail-closed.

---

## SERI Self-Audit

TOF audits itself using its own pipeline. Four model families, zero overlapping findings:

| Phase | Model | Family | Result |
|-------|-------|--------|--------|
| Scout | Claude Opus 4.8 | claude | verified_match |
| Establish | GPT-5.5 | gpt | verified_match |
| Review | Gemini 3.1 Pro | gemini | verified_match |
| Verify | DeepSeek v4 Pro | deepseek | verified_match |

The same pipeline that found three real blind spots in TOF's own trigger layer (including a quoting crash the original author missed) is here to find blind spots in yours.

---

## Why Not LangChain / CrewAI / AutoGen

| | LangChain/CrewAI | TOF |
|---|:-:|:-:|
| Multi-model pipeline | ✅ | ✅ |
| Independent phase isolation | ❌ shared context | ✅ isolated OT subprocesses |
| Can you prove model X actually ran? | ❌ trust-based | ✅ session audit + provenance hash |
| Fail-closed by default | ❌ silent degradation | ✅ cascade invalidation |
| Self-audit (framework auditing itself) | ❌ | ✅ SERI, 4 family, 0 overlap |
| Dependency footprint | 30+ packages | 1 (pyyaml) |
| Adversarial review history | N/A | 3 rounds, 18 gaps → 15 closed |

---

## Project Structure

```
tof                         # Validator + CLI (1633 lines): 5 checks + cascade
orchestrator.py             # State machine: OT dispatch, receipt loop, provenance
session_audit_adapter.py    # Agent log parser: model identity verification
model_registry_adapter.py   # Provider endpoint checker: slug freshness
pipeline.yaml               # 7-phase DAG + transition rules + model assignment
models.yaml                 # Model registry
tests_expected.py           # 17 fixture semantics validator
test_orchestrator_unit.py   # 30 unit tests
test_orchestrator_integration.py  # 4 integration tests
test-fixtures/              # 17 synthetic pipeline runs
phases/                     # Prompt templates per phase (7 phases)
docs/                       # Design rationale, failure modes, architecture
```

---

## Documentation

| Document | What's in it |
|----------|-------------|
| [CORE_CONCEPTS.md](CORE_CONCEPTS.md) | Problem space, trust chain model, mechanical vs behavioral constraints |
| [PHASES.md](PHASES.md) | Complete 7-phase pipeline specification |
| [OT.md](OT.md) | Orchestrator Thread subprocess routing design |
| [FAILURE_MODES.md](FAILURE_MODES.md) | 8 real failure patterns, root causes, and fixes |
| [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) | What's mechanical, what's documented, known gaps |
| [REVIEW.md](REVIEW.md) | Adversarial review history: 3 rounds, 18 gaps |
| [adapter-contract.md](adapter-contract.md) | CODEX/EVIDENCE/JUDGE/INVESTIGATOR architecture |

---

## Design Philosophy

1. **Concrete over aspirational.** Every mechanism was added to fix a real failure. The failure is documented alongside the fix.
2. **Auditable over efficient.** If you can't verify which model ran, the pipeline is fake.
3. **Who before how.** Before deciding *how* to execute, decide *who* should execute. Defaulting to "I'll do it" is the single most expensive bias in agent orchestration.
4. **Modular models.** No single model is the bottleneck. Each phase uses the model best suited for its cognitive load. Swap models without redesigning the pipeline.

---

## License

MIT — take what's useful, leave what isn't.
