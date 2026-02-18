from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentDefinition:
    """Canonical component payload for the Components drawer."""

    component_id: str
    title: str
    subtitle: str
    content: str
