# TOF Adapter Contract (P0)

TOF separates orchestration authority from factual observation:

```text
pipeline.yaml → CODEX (DAG + schema + transition rules)
artifact chain → EVIDENCE (structured frontmatter + content)
tof validate → JUDGE (reads codex + evidence, outputs receipt)
adapters → INVESTIGATORS (narrow capability, no orchestration logic)
```

Adapters **do not** depend on `pipeline.yaml`, **do not** understand the DAG, and **do not** decide the next phase. They are narrow interfaces that return facts about what happened, not what should happen next.

P0 uses fake adapters: the `tof` script constructs dispatch/session facts from artifact frontmatter directly. Real adapters can replace that evidence source later without changing the validator’s authority model.

## Minimal Python Interfaces

```python
from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass
class DispatchResult:
    dispatch_id: str
    assigned_model: str
    claimed_model: str  # what the model says it is (may differ)
    actual_family: Optional[str]  # None if unverifiable
    status: str  # "completed" | "timeout" | "failed" | "fallback"
    raw_log_ref: Optional[str]
    started_at: str
    ended_at: str


class DispatchAdapter(Protocol):
    def dispatch(self, *, phase: str, model_id: str, prompt: str, tags: dict) -> DispatchResult: ...


@dataclass
class SessionMetadata:
    actual_model: str
    actual_family: Optional[str]
    verification_method: str  # "adapter_confirmed" | "log_parsed" | "self_reported" | "unverified"
    confidence: float  # 0.0-1.0
    fallback_detected: bool
    duration_s: float


class SessionAuditAdapter(Protocol):
    def audit(self, *, dispatch_id: str) -> Optional[SessionMetadata]: ...
    # Returns None if dispatch_id not found or audit unavailable


@dataclass
class ArtifactRef:
    phase: str
    path: str  # absolute path
    sha256: str


@dataclass
class Artifact:
    ref: ArtifactRef
    frontmatter: dict
    content: str  # body after frontmatter


@dataclass
class ValidationReceipt:
    validation_id: str
    artifact_path: str
    phase: str
    verdict: str
    status: str
    next_allowed: list[str]
    reasons: list[str]
    checks: dict[str, str]  # check_name → PASS/FAIL/BLOCKING


class ArtifactStore(Protocol):
    def list_artifacts(self, *, run_dir: str) -> list[ArtifactRef]: ...
    def read_artifact(self, *, ref: ArtifactRef) -> Optional[Artifact]: ...
    def write_validation_receipt(self, *, run_dir: str, receipt: ValidationReceipt) -> None: ...
```

## Authority Boundaries

- `pipeline.yaml` is the only source of truth for phase ordering, verdict routing, retry exhaustion, and transition rules.
- Artifact frontmatter is evidence only. In particular, `next_allowed` or transition claims in frontmatter are ignored by `tof validate`.
- `tof validate` is the judge: it reads the codex (`pipeline.yaml`) and evidence (artifacts + model facts), then emits a validation receipt.
- Adapters are investigators: they report dispatch outcomes, session audit facts, and artifact contents.
- Adapters must not contain orchestration logic such as “go to implement next”, “retry establish”, or “approve this phase”.

## Future Adapter Interfaces

The following are intentionally out of scope for P0 and reserved for future versions:

- `KnowledgeDepositionAdapter`
- `ApprovalAdapter`
- `ModelRegistryAdapter`
