from __future__ import annotations

import logging
from typing import Any, Dict


class PipelineFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        extra = getattr(record, "extra", None)
        if extra:
            extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
            record.msg = f"{record.msg}  [{extra_str}]"
        return super().format(record)
