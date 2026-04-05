from __future__ import annotations

import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from openai import OpenAI

from router import route_task

from agent.parser import clamp_confidence, parse_llm_json

logger = logging.getLogger("xalvion")

load_dotenv(override=True)

API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_CHEAP = os.getenv("MODEL_CHEAP", "gpt-4o-mini")
MODEL_EXPENSIVE = os.getenv("MODEL_EXPENSIVE", "gpt-4o-mini")

client = OpenAI(api_key=API_KEY, timeout=14.0) if API_KEY else None


def choose_model(message: str) -> str:
    tier = route_task(message)
    return MODEL_CHEAP if tier == "cheap" else MODEL_EXPENSIVE


def _trace(step: str, status: str, detail: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"step": step, "status": status}
    if detail:
        payload["detail"] = detail
    return payload


def sovereign_llm_attempt(
    clean: str,
    brain: dict[str, Any],
    prompt: str,
    thinking_trace: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str, float, float, bool]:
    parsed = None
    mode = "sovereign-local"
    confidence = 0.9
    quality = 0.94
    llm_used = False

    if client is not None:
        try:
            model = choose_model(clean)
            completion = client.chat.completions.create(
                model=model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": brain.get("system_prompt", "You are Xalvion.")},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = completion.choices[0].message.content or ""
            parsed = parse_llm_json(raw)
            mode = f"sovereign-{model}"
            confidence = clamp_confidence(parsed.get("confidence", 0.92), 0.92)
            quality = 0.97
            llm_used = True
            thinking_trace.append(_trace("llm_response", "done", model))
        except Exception:
            parsed = None
            thinking_trace.append(_trace("llm_response", "error", "provider_failure"))

    return parsed, mode, confidence, quality, llm_used
