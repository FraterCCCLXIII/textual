from __future__ import annotations

from .models import ComponentDefinition


def build_approval_component() -> ComponentDefinition:
    return ComponentDefinition(
        component_id="approval",
        title="Approval Prompt",
        subtitle="Permission selection object",
        content="```text\nProceed with action?\n1. Yes, allow once\n2. No\n3. Always\n```",
    )


def build_process_component() -> ComponentDefinition:
    return ComponentDefinition(
        component_id="process",
        title="Process Status",
        subtitle="Agent progress component",
        content=(
            "```text\nAgent running...\n"
            "Step 1/3 scan files -> Step 2/3 refactor -> Step 3/3 verify tests\n"
            "Status: in progress\n```"
        ),
    )
