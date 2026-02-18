from __future__ import annotations

from .models import ComponentDefinition


def build_task_collapsed_component() -> ComponentDefinition:
    return ComponentDefinition(
        component_id="task-collapsed",
        title="Task (Collapsed)",
        subtitle="Compact task object",
        content="```text\nRead author-sidebar.module.css\n(Ctrl-S to show details)\n```",
    )


def build_task_expanded_component() -> ComponentDefinition:
    return ComponentDefinition(
        component_id="task-expanded",
        title="Task (Expanded)",
        subtitle="Detailed task output",
        content=(
            "Now let me look at the **author-sidebar.module.css** component:\n\n"
            "┌ Read `author-sidebar.module.css` ⋮\n\n"
            "Here's the result of running `cat -n` on\n"
            "`/workspace/project/seedit/src/components/author-sidebar/author-sidebar.module.css`:\n\n"
            "```text\n"
            "1  .sidebar {\n"
            "2      float: right;\n"
            "3      width: 300px;\n"
            "4      position: relative;\n"
            "5      z-index: 5;\n"
            "6      background-color: var(--background);\n"
            "7      padding-left: 5px;\n"
            "8      padding-bottom: 5px;\n"
            "9  }\n"
            "10\n"
            "11 .avatar {\n"
            "12     width: 70px;\n"
            "13     height: 70px;\n"
            "14     margin-bottom: 5px;\n"
            "15     border: 1px solid var(--border-text);\n"
            "16 }\n"
            "```\n\n"
            "(esc to cancel • 32s, Ctrl-S to hide details)"
        ),
    )
