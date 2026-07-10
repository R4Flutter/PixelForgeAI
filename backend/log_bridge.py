"""
log_bridge.py
-------------
A *non-invasive* logging handler that observes the AI pipeline's own log
records and forwards them to the UI.

Why this and not modifications to pipeline.py? The AI scripts emit status
through Python's logging (loggers ``PIPELINE``, ``UPSCALE``, ``REMOVE_BG``,
``scripts.resize``). Attaching a handler here is a pure observer: it reads
exactly what the AI already prints and never alters its behaviour.

``StageMapper`` maps that raw text into the friendly stage labels the UI shows
(Loading AI model / Removing Background / Upscaling / Resizing / Saving /
Completed). The mapping is presentation, not AI logic.
"""

from __future__ import annotations

import logging
from typing import Callable, Iterable

RecordSink = Callable[[str, str, str], None]


# Logger names the existing backend writes to. Anything not in this set (or
# not under ``scripts.``) is ignored, so only genuine AI output reaches the UI.
AI_LOGGER_PREFIXES: tuple[str, ...] = ("PIPELINE", "UPSCALE", "REMOVE_BG", "scripts.")


class _ForwardingHandler(logging.Handler):
    """Pushes selected AI log records to a sink callback."""

    def __init__(self, sink: RecordSink) -> None:
        super().__init__(level=logging.INFO)
        self._sink = sink
        self._prefixes = AI_LOGGER_PREFIXES

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            if not (record.name in ("PIPELINE", "UPSCALE", "REMOVE_BG")
                    or record.name.startswith("scripts.")):
                return
            self._sink(record.levelname, record.name, self.format(record))
        except Exception:
            # A logging handler must never raise into the host application.
            return


class LogBridge:
    """Installable/uninstallable bridge from AI loggers to a UI sink."""

    def __init__(self, sink: RecordSink) -> None:
        self._handler = _ForwardingHandler(sink)

    def install(self) -> "LogBridge":
        logging.getLogger().addHandler(self._handler)
        return self

    def uninstall(self) -> None:
        logging.getLogger().removeHandler(self._handler)


class StageMapper:
    """Stateful mapper: raw AI log text -> friendly UI stage label."""

    DEFAULT_STAGE = "Loading AI model…"

    def __init__(self) -> None:
        self._current: str | None = None

    def reset(self) -> None:
        self._current = None

    @staticmethod
    def _normalize(text: str) -> str:
        t = text.lower()
        if "removing background" in t:
            return "Removing Background…"
        if "detected photo" in t or "applying upscale" in t or "upscaled" in t or "upscaler" in t:
            return "Upscaling…"
        if "detected design" in t or "skipping upscale" in t:
            return "Optimizing Design…"
        if "resizing" in t or "resized" in t:
            return "Resizing…"
        if "success" in t and "final" not in t:
            return "Saving…"
        if "finished" in t or "pipe" in t:
            return "Completed"
        return ""

    def map(self, text: str) -> str | None:
        """Return a friendly stage label for the UI, or None if unchanged."""
        label = self._normalize(text)
        if not label:
            return None
        if label == self._current:
            return None
        self._current = label
        return label
