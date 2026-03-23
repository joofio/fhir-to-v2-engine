"""
In-memory storage for ConceptMaps.

For production use, replace this with a persistent database (e.g. SQLite/PostgreSQL).
"""
from __future__ import annotations

from app.models import ConceptMap

_store: dict[str, ConceptMap] = {}


def save(cm: ConceptMap) -> ConceptMap:
    _store[cm.id] = cm
    return cm


def get(cm_id: str) -> ConceptMap | None:
    return _store.get(cm_id)


def list_all() -> list[ConceptMap]:
    return list(_store.values())


def delete(cm_id: str) -> bool:
    if cm_id in _store:
        del _store[cm_id]
        return True
    return False


def clear() -> None:
    """Remove all stored concept maps (used in tests)."""
    _store.clear()
