from __future__ import annotations

from typing import Any

from persistence_layer import KnowledgePayload, KnowledgeRepository

_repo = KnowledgeRepository()


def ingest_data(new_data: Any) -> dict[str, Any]:
    if isinstance(new_data, dict):
        payload = KnowledgePayload(
            content=str(new_data.get("content") or new_data.get("text") or str(new_data)).strip(),
            source=str(new_data.get("source") or "manual").strip() or "manual",
            content_type=str(new_data.get("content_type") or new_data.get("type") or "note").strip() or "note",
            weight=float(new_data.get("weight", 1.0) or 1.0),
            metadata={k: v for k, v in new_data.items() if k not in {"content", "text", "source", "content_type", "type", "weight"}},
        )
    else:
        payload = KnowledgePayload(content=str(new_data).strip(), source="manual", content_type="note")
    return _repo.add(payload)


def retrieve_knowledge(query: str) -> str:
    rows = _repo.search(query=query, limit=3)
    return "\n".join(row["content"] for row in rows)
