from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4


@dataclass(frozen=True)
class Lease:
    id: str = field(default_factory=lambda: str(uuid4()))
    holder: str = "local"
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    heartbeat_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_seconds: int = 300

    def is_stale(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(timezone.utc)
        return current - self.heartbeat_at > timedelta(seconds=self.ttl_seconds)

    def heartbeat(self, now: datetime | None = None) -> "Lease":
        return Lease(
            id=self.id,
            holder=self.holder,
            acquired_at=self.acquired_at,
            heartbeat_at=now or datetime.now(timezone.utc),
            ttl_seconds=self.ttl_seconds,
        )
