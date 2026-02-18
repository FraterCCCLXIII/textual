from __future__ import annotations

from .models import ComponentDefinition


def build_todo_component(todo_content: str) -> ComponentDefinition:
    return ComponentDefinition(
        component_id="todo",
        title="Plan / Todo",
        subtitle="Task list component",
        content=todo_content,
    )


def build_cost_component(cost_content: str) -> ComponentDefinition:
    return ComponentDefinition(
        component_id="cost",
        title="Cost Feed",
        subtitle="Credit usage component",
        content=cost_content,
    )
