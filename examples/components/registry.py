from __future__ import annotations

import os

from .metrics_components import build_cost_component, build_todo_component
from .models import ComponentDefinition
from .openhands_cli_components import build_openhands_cli_component_definitions
from .prompt_components import build_approval_component, build_process_component
from .task_components import build_task_collapsed_component, build_task_expanded_component


def build_component_registry(
    *, todo_content: str, cost_content: str
) -> list[ComponentDefinition]:
    """Build component definitions from modular component files.

    This is intentionally simple so we can replace mock content with real
    OpenHands component payloads incrementally.
    """

    openhands_root = os.getenv(
        "OPENHANDS_CLI_ROOT", "/Users/paulbloch/Documents/github/OpenHands-CLI"
    )
    mock_components = [
        build_task_collapsed_component(),
        build_task_expanded_component(),
        build_approval_component(),
        build_todo_component(todo_content),
        build_cost_component(cost_content),
        build_process_component(),
    ]
    imported_components = build_openhands_cli_component_definitions(openhands_root)
    return imported_components + mock_components
