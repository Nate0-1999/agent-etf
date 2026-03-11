from __future__ import annotations

import json
import os
from collections import deque
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

from agent_etf_contracts.models import DevEvent

_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
_test_run_id_ctx: ContextVar[str | None] = ContextVar("test_run_id", default=None)


def current_request_id() -> str | None:
    return _request_id_ctx.get()


def current_test_run_id() -> str | None:
    return _test_run_id_ctx.get()


def set_request_context(request_id: str | None, test_run_id: str | None) -> tuple[object, object]:
    request_token = _request_id_ctx.set(request_id)
    test_run_token = _test_run_id_ctx.set(test_run_id)
    return request_token, test_run_token


def reset_request_context(tokens: tuple[object, object]) -> None:
    request_token, test_run_token = tokens
    _request_id_ctx.reset(request_token)  # type: ignore[arg-type]
    _test_run_id_ctx.reset(test_run_token)  # type: ignore[arg-type]


@dataclass
class DevEventRecorder:
    max_events: int = 1000
    _events: deque[DevEvent] = field(default_factory=deque)
    _lock: Lock = field(default_factory=Lock)

    def record(
        self,
        *,
        category: str,
        action: str,
        request_id: str | None = None,
        test_run_id: str | None = None,
        route: str | None = None,
        status_code: int | None = None,
        payload: dict[str, object] | None = None,
    ) -> DevEvent:
        event = DevEvent(
            id=str(uuid4()),
            category=category,
            action=action,
            request_id=request_id or current_request_id(),
            test_run_id=test_run_id or current_test_run_id(),
            route=route,
            status_code=status_code,
            payload={} if payload is None else dict(payload),
        )
        with self._lock:
            self._events.append(event)
            while len(self._events) > self.max_events:
                self._events.popleft()
        if os.getenv("AGENTIC_TEST_JSON_LOGS", "1") == "1":
            print(json.dumps({"type": "dev_event", **event.model_dump(mode="json")}), flush=True)
        return event

    def list_events(self, test_run_id: str | None = None) -> list[DevEvent]:
        with self._lock:
            events = list(self._events)
        if test_run_id is None:
            return events
        return [event for event in events if event.test_run_id == test_run_id]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


recorder = DevEventRecorder()


def make_request_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    return f"req-{timestamp}-{uuid4().hex[:8]}"
