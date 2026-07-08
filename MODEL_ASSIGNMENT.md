# Model Assignment Matrix

> Which model for which phase — and the reasoning behind each choice.

## Philosophy

This is not a "best model" list. It's a **phase-to-capability** mapping. The question isn't "which model is strongest overall" — it's "which model is strongest for *this specific cognitive load* at *this point in the pipeline*."

**The key insight:** Multi-model pipelines fail not because the wrong models are chosen, but because the same model ends up doing everything. Phase separation is more important than model perfection.

## Recommended Assignments

| Phase | Recommended Model Class | Why | Key Quality |
|-------|-----------------------|-----|-------------|
| **Clarify** | Fast, cheap, strong in user's primary language | User-facing iteration; cost efficiency matters here; no heavy reasoning needed | Low cost, fast response, good multi-turn conversation |
| **Scout** | Highest SWE-bench score | Needs to understand codebases, find edge cases, identify what it doesn't know | Code understanding, comprehensive analysis |
| **Establish** | Strongest architectural reasoning | Design decisions compound across the entire pipeline; this is where getting it right matters most | Architecture quality, constraint awareness |
| **Review** | Highest factual accuracy / benchmark (different family from Establish) | Needs to find what the designer missed; same-family models share blind spots | Independence + accuracy |
| **Implement** | Highest terminal/execution benchmark | Needs to turn plans into working code; test execution; error handling | Code generation, tool use, debugging |
| **Verify** | Dual models: one from each family | Two passes: orchestrator checks plan adherence, independent model does deep review | Plan adherence + independent judgment |

## The Golden Rule: Model Family Diversity

**The Review model must be from a different model family than the Establish model.**

Why: Models in the same family (same architecture, similar training data, similar alignment approach) share blind spots. When the designer misses something, a same-family reviewer is likely to miss the same thing. The entire point of a multi-model pipeline is to catch each model's blind spots — which requires diversity at the architectural level.

**Good:** Establish = Model Family A, Review = Model Family B
**Bad:** Establish = Model A v1, Review = Model A v2 (same family, same blind spots)

## Provider Abstraction

The matrix above says "Model Family X" not "Provider Y." This is intentional. The model routing should be independent of the provider layer:

```
┌────────────────────────────────────────┐
│           TOF Pipeline                 │
│  Phase → Model Class → Model Instance  │
└──────────┬─────────────────────────────┘
           │ routing
           ▼
┌────────────────────────────────────────┐
│          Provider Abstraction Layer     │
│  Routes model → provider → API call    │
│  Handles: tunneling, fallback, auth    │
└────────────────────────────────────────┘
```

The pipeline shouldn't care whether your provider is a direct API, a proxy service, or a local inference server. It should only care that the assigned model class actually executes.

## Model ID Freshness

**Model slugs change.** A model ID that worked yesterday may error today. Always verify before dispatching to an unfamiliar model:

```bash
# Quick freshness check
curl -s "https://<provider-endpoint>/v1/models" | grep "model-name-fragment"
```

If the model ID is stale, **report it** — don't substitute with a guess. The substitution might have different capabilities.

## Why Not Just One Model?

| Phase | If you use one model for everything |
|-------|------------------------------------|
| Scout | Misses edge cases, over-confident about unknowns |
| Establish | Designs within its blind spots |
| Review | Approves designs within its blind spots |
| Verify | Finds no issues within its blind spots |
| **Result** | Looks like a pipeline, is actually self-review |

One model for everything degrades the pipeline to a more expensive version of single-shot prompting. The cost of running N different models is real — but the cost of a missed architecture flaw that takes weeks to discover is orders of magnitude higher.
