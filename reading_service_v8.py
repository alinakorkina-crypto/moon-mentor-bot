"""Process-local adapter for the three Telegram question modes.

Operations live until process exit so a redelivered message cannot regenerate a
reading. No credentials or model response diagnostics are exposed to Telegram.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any


FAILURE_MESSAGE = "Сейчас не удалось подготовить трактовку. Попробуйте немного позже."
MODE_TOPICS = {"question": "general", "love": "love", "career": "career"}


def v8_enabled() -> bool:
    return os.getenv("READING_ENGINE", "legacy") == "v8"


def _generate(question: str, cards: list[dict], mode: str) -> dict[str, Any]:
    # Lazy imports: main.load_dotenv() runs before v8 configuration is read.
    from ai_reader_openai_v8 import ask_openai_v8
    from reading_engine_v8 import generate_reading_v8

    return generate_reading_v8(
        question=question, cards=cards, topic=MODE_TOPICS[mode],
        model_call=ask_openai_v8,
    )


async def _run(question: str, cards: list[dict], mode: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(_generate, question, cards, mode)
    except Exception:
        # Cache failure too; never retry a potentially completed model request.
        return {"status": "error", "text": None}


@dataclass
class ReadingOperation:
    mode: str
    question: str
    cards: list[dict]
    task: asyncio.Task
    delivery_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    progress_sent: bool = False
    images_sent: bool = False
    history_recorded: bool = False
    delivered: bool = False

    async def result(self) -> dict[str, Any]:
        # A cancelled Telegram handler must not cancel or restart generation.
        return await asyncio.shield(self.task)


class ReadingServiceV8:
    def __init__(self) -> None:
        self.operations: dict[tuple[int, int], ReadingOperation] = {}

    def get(self, key: tuple[int, int]) -> ReadingOperation | None:
        return self.operations.get(key)

    def start(self, key: tuple[int, int], *, mode: str, question: str,
              cards: list[dict]) -> ReadingOperation:
        if key not in self.operations:
            if mode not in MODE_TOPICS:
                raise ValueError("Unsupported reading mode")
            self.operations[key] = ReadingOperation(
                mode=mode, question=question, cards=cards,
                task=asyncio.create_task(_run(question, cards, mode)),
            )
        return self.operations[key]
