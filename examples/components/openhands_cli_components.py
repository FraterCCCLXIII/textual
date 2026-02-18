from __future__ import annotations

from pathlib import Path

from .models import ComponentDefinition


def _title_from_relative_path(relative_path: str) -> str:
    stem = Path(relative_path).stem.replace("_", " ").strip()
    return stem.title() if stem else relative_path


def _component_id_from_relative_path(relative_path: str) -> str:
    base = relative_path.replace("/", "-").replace(".", "-").replace("_", "-")
    return f"ohcli-{base.lower()}"


def _build_rendered_preview(relative_path: str) -> str:
    """Render a UI preview for imported OpenHands components.

    We intentionally show component behavior mockups (not source code), so the
    prototype drawer acts like a component gallery you can restyle.
    """

    key = relative_path.replace("\\", "/").lower()

    if "widgets/status_line.py" in key:
        return (
            "### Status Line\n\n"
            "OpenHands CLI   <> agent-workbench   ⎇ feature/component-theme   ✦ Model: gpt-4.1"
        )

    if "widgets/input_area.py" in key or "widgets/user_input" in key:
        return (
            "### Input Area\n\n"
            "```text\n"
            "Type a request (or @path/to/file), then press Enter\n"
            "─────────────────────────────────────────────────────\n"
            "/settings\n"
            "```\n\n"
            "Autocomplete, slash parsing, and submit interactions."
        )

    if "widgets/richlog_visualizer.py" in key or "widgets/main_display.py" in key:
        return (
            "### Main Display\n\n"
            "```text\n"
            "Agent running...\n"
            "$ rg --files | rg settings\n"
            "Found 12 files. Narrowing to tui/modals/settings.\n"
            "```\n\n"
            "Rendered stream output with step-by-step logs."
        )

    if "widgets/collapsible.py" in key:
        return (
            "### Collapsible Task Output\n\n"
            "```text\n"
            "Read author-sidebar.module.css\n"
            "(Ctrl-S to show details)\n"
            "```\n\n"
            "Expandable output component for long terminal actions."
        )

    if "panels/history_side_panel.py" in key:
        return (
            "### History Side Panel\n\n"
            "```text\n"
            "Conversations\n"
            "• Onboarding Flow\n"
            "• Local Repository Setup\n"
            "• Cloud Repository Session\n"
            "```\n\n"
            "Conversation navigation drawer."
        )

    if "panels/plan_side_panel.py" in key:
        return (
            "### Plan Side Panel\n\n"
            "```text\n"
            "Agent Updated Plan\n"
            "1. Analyze current TUI architecture\n"
            "2. Import OpenHands components\n"
            "3. Validate component previews\n"
            "```\n\n"
            "Progress tracking and plan visualization."
        )

    if "panels/mcp_side_panel.py" in key:
        return (
            "### MCP Side Panel\n\n"
            "```text\n"
            "MCP Servers\n"
            "- github (connected)\n"
            "- browser (connected)\n"
            "- figma (disconnected)\n"
            "```\n\n"
            "Resource and tool integration status."
        )

    if "panels/confirmation_panel.py" in key:
        return (
            "### Confirmation Panel\n\n"
            "```text\n"
            "Proceed with action?\n"
            "1. Yes, allow once\n"
            "2. No\n"
            "3. Always\n"
            "```\n\n"
            "Safety gate for tool execution."
        )

    if "modals/settings" in key:
        return (
            "### Settings Modal\n\n"
            "```text\n"
            "Settings\n"
            "• Model: gpt-4.1\n"
            "• Confirmation mode: medium\n"
            "• Theme: monochrome\n"
            "• Icon set: Nerd Font\n"
            "```\n\n"
            "Modal-based environment and CLI preferences."
        )

    if "modals/exit_modal.py" in key:
        return (
            "### Exit Modal\n\n"
            "```text\n"
            "Exit OpenHands CLI?\n"
            "[Cancel]   [Exit]\n"
            "```\n\n"
            "Graceful shutdown confirmation."
        )

    if "modals/confirmation_modal.py" in key:
        return (
            "### Confirmation Modal\n\n"
            "```text\n"
            "Tool action requires confirmation.\n"
            "Allow this action?\n"
            "[Allow once]  [Deny]  [Always allow]\n"
            "```\n\n"
            "Modal fallback for explicit confirmation flows."
        )

    if "modals/switch_conversation_modal.py" in key:
        return (
            "### Switch Conversation Modal\n\n"
            "```text\n"
            "Switch conversation\n"
            "• Onboarding Flow\n"
            "• Local Repository Setup\n"
            "• Cloud Repository Session\n"
            "```\n\n"
            "Quick conversation jump dialog."
        )

    if "content/splash.py" in key or "widgets/splash.py" in key:
        return (
            "### Splash / Onboarding\n\n"
            "```text\n"
            "OpenHands CLI v0.57.0\n"
            "No settings found — let's set you up!\n"
            "[Connect to OpenHands]  [Use your own provider]\n"
            "```\n\n"
            "Startup flow and first-run setup."
        )

    if "textual_app.py" in key or "textual_app.tcss" in key:
        return (
            "### App Shell\n\n"
            "```text\n"
            "Left drawer | Main conversation | Input + status row\n"
            "Slash command menu + modal overlays + side panels\n"
            "```\n\n"
            "Top-level layout orchestration and styling."
        )

    return (
        f"### {Path(relative_path).name}\n\n"
        "Imported OpenHands component.\n\n"
        "```text\n"
        "Preview template loaded.\n"
        "Use this slot to map exact runtime state + interactions.\n"
        "```\n\n"
        f"Source: `{relative_path}`"
    )


def build_openhands_cli_component_definitions(
    openhands_cli_root: str,
) -> list[ComponentDefinition]:
    root = Path(openhands_cli_root).expanduser().resolve()
    tui_root = root / "openhands_cli" / "tui"
    if not tui_root.exists():
        return [
            ComponentDefinition(
                component_id="ohcli-root-missing",
                title="OpenHands CLI Source Missing",
                subtitle=str(tui_root),
                content=(
                    "```text\nOpenHands CLI source directory was not found.\n"
                    "Set OPENHANDS_CLI_ROOT to your local OpenHands-CLI path.\n```"
                ),
            )
        ]

    ui_globs = [
        "widgets/**/*.py",
        "panels/**/*.py",
        "modals/**/*.py",
        "textual_app.py",
        "textual_app.tcss",
        "content/**/*.py",
    ]
    component_files: list[Path] = []
    for pattern in ui_globs:
        component_files.extend(sorted(tui_root.glob(pattern)))
    component_files = [
        file
        for file in component_files
        if file.suffix in {".py", ".tcss"} and file.name != "__init__.py"
    ]
    components: list[ComponentDefinition] = []
    for source_file in component_files:
        relative_path = str(source_file.relative_to(root))
        components.append(
            ComponentDefinition(
                component_id=_component_id_from_relative_path(relative_path),
                title=_title_from_relative_path(relative_path),
                subtitle=relative_path,
                content=_build_rendered_preview(relative_path),
            )
        )
    return components
