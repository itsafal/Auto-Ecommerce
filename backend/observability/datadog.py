"""Datadog wrapper.

No-ops cleanly when DATADOG_API_KEY is missing so every other workstream
can call these helpers without a key during the hackathon.

Exposed surface:
  emit_count(metric, value=1, tags=None)
  emit_histogram(metric, value, tags=None)
  emit_gauge(metric, value, tags=None)
  trace_activity(name, tags=None)  -> context manager
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger(__name__)


def datadog_enabled() -> bool:
    return bool(os.environ.get("DATADOG_API_KEY"))


_initialized = False
_statsd = None
_tracer = None


def _init() -> None:
    """Lazy init the Datadog statsd + tracer. Safe to call repeatedly."""
    global _initialized, _statsd, _tracer
    if _initialized:
        return
    _initialized = True

    if not datadog_enabled():
        return

    try:
        from datadog import initialize, statsd  # type: ignore

        initialize(
            api_key=os.environ.get("DATADOG_API_KEY"),
            app_key=os.environ.get("DATADOG_APP_KEY"),
            statsd_host=os.environ.get("DATADOG_STATSD_HOST", "127.0.0.1"),
            statsd_port=int(os.environ.get("DATADOG_STATSD_PORT", "8125")),
        )
        _statsd = statsd
    except Exception as exc:
        logger.warning("Datadog statsd init failed; metrics will no-op: %s", exc)
        _statsd = None

    try:
        from ddtrace import tracer  # type: ignore

        _tracer = tracer
    except Exception as exc:
        logger.warning("ddtrace not available; spans will no-op: %s", exc)
        _tracer = None


def _format_tags(tags: dict[str, str] | None) -> list[str]:
    if not tags:
        return []
    return [f"{k}:{v}" for k, v in tags.items()]


def emit_count(metric: str, value: float = 1, tags: dict[str, str] | None = None) -> None:
    _init()
    if _statsd is None:
        return
    try:
        _statsd.increment(metric, value=value, tags=_format_tags(tags))
    except Exception as exc:  # never let metrics break the demo
        logger.debug("emit_count failed for %s: %s", metric, exc)


def emit_histogram(metric: str, value: float, tags: dict[str, str] | None = None) -> None:
    _init()
    if _statsd is None:
        return
    try:
        _statsd.histogram(metric, value=value, tags=_format_tags(tags))
    except Exception as exc:
        logger.debug("emit_histogram failed for %s: %s", metric, exc)


def emit_gauge(metric: str, value: float, tags: dict[str, str] | None = None) -> None:
    _init()
    if _statsd is None:
        return
    try:
        _statsd.gauge(metric, value=value, tags=_format_tags(tags))
    except Exception as exc:
        logger.debug("emit_gauge failed for %s: %s", metric, exc)


@contextmanager
def trace_activity(name: str, tags: dict[str, str] | None = None) -> Iterator[None]:
    """Wrap a block of work with a Datadog span + a latency histogram.

    Works (silently) even when Datadog is disabled — callers don't need to branch.
    """
    _init()
    span_ctx = None
    if _tracer is not None:
        try:
            span_ctx = _tracer.trace(name)
            span = span_ctx.__enter__()
            if tags:
                for key, value in tags.items():
                    span.set_tag(key, value)
        except Exception as exc:
            logger.debug("trace_activity span start failed for %s: %s", name, exc)
            span_ctx = None

    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        emit_histogram(f"{name}.latency_ms", elapsed_ms, tags=tags)
        if span_ctx is not None:
            try:
                span_ctx.__exit__(None, None, None)
            except Exception as exc:
                logger.debug("trace_activity span close failed for %s: %s", name, exc)
