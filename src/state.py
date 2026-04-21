from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ExperimentStatus(Enum):
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    DRY_RUN = "DRY_RUN"
    INJECTING = "INJECTING"
    OBSERVING = "OBSERVING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


@dataclass
class ExperimentPlan:
    namespace: str
    target: str
    fault_type: str
    duration_sec: int = 30
    threshold: float = 10.0


@dataclass
class ExperimentState:
    status: ExperimentStatus = ExperimentStatus.PENDING
    plan: Optional[ExperimentPlan] = None
    started_at: Optional[datetime] = None
    events: list = field(default_factory=list)

    def transition(self, new_status: ExperimentStatus, message: str = "") -> None:
        self.status = new_status
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}][{new_status.value}] {message}" if message else f"[{ts}][{new_status.value}]"
        self.events.append(entry)

    def abort(self, reason: str) -> None:
        self.transition(ExperimentStatus.ABORTED, f"ABORT: {reason}")

    def reset(self) -> None:
        self.status = ExperimentStatus.PENDING
        self.plan = None
        self.started_at = None
        self.events.clear()

    def timeline(self) -> str:
        return "\n".join(self.events) if self.events else "(no events)"
