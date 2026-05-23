from __future__ import annotations

from uuid import UUID

from backend.schemas import AgentEvent, LaunchRun


class InMemoryRunStore:
    def __init__(self) -> None:
        self._runs: dict[UUID, LaunchRun] = {}
        self._events: dict[UUID, list[AgentEvent]] = {}

    def clear(self) -> None:
        self._runs.clear()
        self._events.clear()

    def upsert_run(self, run: LaunchRun) -> LaunchRun:
        self._runs[run.run_id] = run
        self._events.setdefault(run.run_id, [])
        return run

    def get_run(self, run_id: UUID) -> LaunchRun | None:
        return self._runs.get(run_id)

    def add_event(self, run_id: UUID, event: AgentEvent) -> AgentEvent:
        self._events.setdefault(run_id, []).append(event)
        self._events[run_id].sort(key=lambda item: item.timestamp)
        return event

    def set_events(self, run_id: UUID, events: list[AgentEvent]) -> None:
        self._events[run_id] = sorted(events, key=lambda item: item.timestamp)

    def get_events(self, run_id: UUID) -> list[AgentEvent]:
        return list(self._events.get(run_id, []))


run_store = InMemoryRunStore()
