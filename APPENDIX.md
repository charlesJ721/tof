# Appendix

## Glossary

| Term | Definition |
|------|------------|
| **TOF** | Task Orchestration Framework — the pipeline described in this directory |
| **OT** | Orchestrator Thread — a subprocess invocation of an agent with an explicit model assignment |
| **SERI** | Scout → Establish → Review → Implement — the core four-phase pipeline |
| **A-SRE** | Analyze → Adversarial Review → Synthesize — for pure analysis tasks |
| **Phase EX** | Escalation — triggered when a phase fails quality gate after all retries |
| **Quality Gate** | A set of mandatory output fields for each phase; missing fields block progression |
| **STATE_LOCKER** | A state-machine prefix declaring the current phase, next action, and risk warning |
| **Knowledge Deposition** | The final step: persisting methodology-level knowledge across channels (skill files, memory, wiki) |
| **Model diversity** | Using models from different families in different phases to catch each other's blind spots |
| **Core Dump** | An output that contains code without a preceding STATE_LOCKER block — rolls back to Phase 0 |

## Changelog

### v2.0 — Current (Structured Enforcement)

**Previous state:** v1 was a 526-line behavioral manifesto with zero hard enforcement. The framework described what the orchestrator *should* do — it never ensured the orchestrator *actually did* it.

**v2 changes:**
- Replaced behavioral suggestions with structured mechanisms (5 hard mechanisms)
- Added STATE_LOCKER protocol with hard interception
- Added mandatory quality gates for all phase artifacts
- Added constraint source validation between phases
- Added OT subprocess verification protocol
- Reduced rule volume while increasing enforceability

### v1.0 — Original Design (Behavioral Manifesto)

The first version of TOF described the pipeline in detail — phases, models, routing — but relied entirely on the orchestrator's self-awareness. It failed because the orchestrator's default behavior (self-execute, skip review, silent fallback) overrode every rule that existed only as text in a prompt.

## External References

This framework was shaped by the following sources:

| Source | Key Contribution |
|--------|-----------------|
| **VeriMAP** (Purdue/Megagon, arXiv 2510.17109) | DAG-based task decomposition + verification functions; reduced error rate from 15% to <3% |
| **Tyler Burleigh "Research, Plan, Implement, Review"** (Feb 2026) | Written artifact chain + per-phase independent sessions |
| **MoltBot "LLM Orchestration in 2026"** | Routing tables; 60-90% cost reduction via phase-appropriate model selection |
| **OpenSquilla** | Three-layer sandbox (Standard/Strict/Locked) for security; XML escaping; Denial Ledger |
| **SkillOps** (arXiv 2605.13716v1) | P/O/A/V/F skill contract format |
| **Real Deployments (June-July 2026)** | All 8 failure modes documented in FAILURE_MODES.md were discovered in production |

## Related Work

If TOF's patterns resonate with your problems, you may also find value in:

- **Anthropic's Claude Code** — sub-agent auto-selection research (and their admission that it's unreliable — confirming the Who-before-How principle)
- **OpenAI's Codex CLI** — profile-based model routing at the CLI level
- **LangGraph** — graph-based pipeline orchestration (TOF uses a fixed topology as a deliberate simplification)
- **OpenSquilla** — sandboxed execution; the security layer inspiration for TOF §safety
