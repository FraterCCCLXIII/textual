from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static
from textual.widgets.option_list import Option

try:
    # Module-style execution: python -m examples.openhands_cli
    from .components.splitter import PaneSplitter
except ImportError:
    # Script-style execution: python examples/openhands_cli.py
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.append(str(_Path(__file__).resolve().parent))
    from components.splitter import PaneSplitter


@dataclass
class Conversation:
    conversation_id: str
    title: str
    preview: str
    updated_at: str
    messages: list[tuple[str, str]] = field(default_factory=list)


class LoginScreen(Screen):
    BINDINGS = [("enter", "continue_to_dashboard", "Continue")]

    def compose(self) -> ComposeResult:
        with Container(id="login-shell"):
            with Vertical(id="login-card"):
                yield Static("OpenHands", id="login-title")
                yield Static("Monochrome IDE Demo", id="login-subtitle")
                yield Input(placeholder="Email", id="login-email")
                yield Input(password=True, placeholder="Password", id="login-password")
                with Horizontal(id="login-actions"):
                    yield Button("Sign In", id="login-signin")
                    yield Button("Continue as Guest", id="login-guest")
                yield Static(
                    "Visual prototype only. No auth calls are performed.",
                    id="login-note",
                )

    def action_continue_to_dashboard(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.show_dashboard()

    @on(Button.Pressed, "#login-signin")
    def on_sign_in_pressed(self) -> None:
        self.action_continue_to_dashboard()

    @on(Button.Pressed, "#login-guest")
    def on_guest_pressed(self) -> None:
        self.action_continue_to_dashboard()


class DashboardScreen(Screen):
    BINDINGS = [
        ("n", "new_conversation", "New Conversation"),
        ("enter", "open_workspace", "Open"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dashboard-shell"):
            with Vertical(id="dashboard-hero"):
                yield Static("Dashboard", classes="section-title")
                yield Static(
                    "Pick a conversation or start a new one.",
                    id="dashboard-subtitle",
                )
                with Horizontal(id="dashboard-actions"):
                    yield Button("New Conversation", id="dashboard-new")
                    yield Button("Open Selected", id="dashboard-open")
            with Horizontal(id="dashboard-grid"):
                with Vertical(classes="panel", id="dashboard-conversations-panel"):
                    yield Static("Recent Conversations", classes="panel-title")
                    yield OptionList(id="dashboard-conversations")
                with Vertical(classes="panel", id="dashboard-summary-panel"):
                    yield Static("Workspace Summary", classes="panel-title")
                    yield Static(id="dashboard-summary")

    def on_mount(self) -> None:
        self._render_conversations()
        self._render_summary()

    def _render_conversations(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        options = [
            Option(
                f"{conv.title}\n{conv.preview}\n{conv.updated_at}",
                id=conv.conversation_id,
            )
            for conv in app.conversations
        ]
        option_list = self.query_one("#dashboard-conversations", OptionList)
        option_list.clear_options()
        option_list.add_options(options)
        option_list.highlighted = app.active_conversation_index

    def _render_summary(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        active = app.active_conversation
        summary = (
            "Mode: full featured AI IDE (demo)\n\n"
            f"Conversations: {len(app.conversations)}\n"
            "Layout: left drawer + chat + canvas\n"
            "Theme: monochrome black/white\n"
            f"Selected: {active.title}"
        )
        self.query_one("#dashboard-summary", Static).update(summary)

    @on(OptionList.OptionSelected, "#dashboard-conversations")
    def on_conversation_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.set_active_conversation(event.option_id)
        self._render_summary()

    def action_new_conversation(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.create_conversation()
        app.show_workspace()

    def action_open_workspace(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.show_workspace()

    @on(Button.Pressed, "#dashboard-new")
    def on_dashboard_new(self) -> None:
        self.action_new_conversation()

    @on(Button.Pressed, "#dashboard-open")
    def on_dashboard_open(self) -> None:
        self.action_open_workspace()


class WorkspaceScreen(Screen):
    BINDINGS = [
        ("ctrl+b", "back_to_dashboard", "Back"),
        ("1", "show_changes", "Changes"),
        ("2", "show_tasks", "Tasks"),
        ("3", "show_plans", "Plans"),
        ("4", "show_files", "Files"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.active_canvas_tab = "changes"
        self.conversations_visible = True

    def compose(self) -> ComposeResult:
        with Container(id="workspace-shell"):
            with Horizontal(id="workspace-header"):
                yield Static("OpenHands IDE", id="workspace-title")
                yield Static("Login > Dashboard > New Conversation", id="workspace-crumbs")
                yield Button("Back", id="workspace-back")
            with Horizontal(id="workspace-columns"):
                with Vertical(id="conversations-pane", classes="panel"):
                    with Horizontal(classes="panel-head"):
                        yield Static(
                            "Conversations",
                            classes="panel-title",
                            id="conversations-head-title",
                        )
                        yield Button("←", id="workspace-hide-conversations")
                    yield OptionList(id="workspace-conversations")
                yield PaneSplitter(
                    target_pane_id="conversations-pane",
                    min_width=24,
                    max_width=56,
                    id="splitter-left",
                )
                with Vertical(id="chat-pane", classes="panel"):
                    yield Static("Chat", classes="panel-title")
                    yield VerticalScroll(id="chat-scroll")
                    with Horizontal(id="chat-composer"):
                        yield Input(
                            placeholder="Type your request... (demo only)",
                            id="chat-input",
                        )
                        yield Button("Send", id="chat-send")
                yield PaneSplitter(
                    target_pane_id="chat-pane",
                    min_width=40,
                    max_width=96,
                    id="splitter-right",
                )
                with Vertical(id="canvas-pane", classes="panel"):
                    yield Static("Canvas", classes="panel-title")
                    with Horizontal(id="canvas-tabs"):
                        yield Button("Changes", id="tab-changes", classes="canvas-tab")
                        yield Button("Tasks", id="tab-tasks", classes="canvas-tab")
                        yield Button("Plans", id="tab-plans", classes="canvas-tab")
                        yield Button("Files", id="tab-files", classes="canvas-tab")
                    yield Static(id="canvas-content")

    def on_mount(self) -> None:
        self._apply_conversations_visibility()
        self._render_conversations()
        self._render_chat()
        self._render_canvas()
        self.query_one("#chat-input", Input).focus()

    def action_back_to_dashboard(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.show_dashboard()

    def action_show_changes(self) -> None:
        self._set_canvas_tab("changes")

    def action_show_tasks(self) -> None:
        self._set_canvas_tab("tasks")

    def action_show_plans(self) -> None:
        self._set_canvas_tab("plans")

    def action_show_files(self) -> None:
        self._set_canvas_tab("files")

    @on(Button.Pressed, "#workspace-back")
    def on_back_pressed(self) -> None:
        self.action_back_to_dashboard()

    @on(Button.Pressed, "#workspace-hide-conversations")
    def on_hide_conversations_pressed(self) -> None:
        self._set_conversations_visible(False)

    @on(OptionList.OptionSelected, "#workspace-conversations")
    def on_workspace_conversation_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        app.set_active_conversation(event.option_id)
        self._render_chat()
        self._render_canvas()

    @on(Input.Submitted, "#chat-input")
    def on_chat_submitted(self, event: Input.Submitted) -> None:
        self._send_message(event.value)
        event.input.clear()

    @on(Button.Pressed, "#chat-send")
    def on_chat_send_pressed(self) -> None:
        input_widget = self.query_one("#chat-input", Input)
        self._send_message(input_widget.value)
        input_widget.clear()
        input_widget.focus()

    @on(Button.Pressed, ".canvas-tab")
    def on_canvas_tab_pressed(self, event: Button.Pressed) -> None:
        tab_id = event.button.id or ""
        self._set_canvas_tab(tab_id.replace("tab-", ""))

    def _send_message(self, text: str) -> None:
        content = text.strip()
        if not content:
            return
        if self._run_workspace_command(content):
            return
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        active = app.active_conversation
        active.messages.append(("user", content))
        active.messages.append(
            (
                "assistant",
                "Demo response: drafting plan, inspecting files, and preparing changes.",
            )
        )
        active.preview = content[:42] + ("..." if len(content) > 42 else "")
        active.updated_at = "Updated just now"
        self._render_chat()
        self._render_conversations()
        self._render_canvas()

    def _run_workspace_command(self, content: str) -> bool:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        if not content.startswith("/"):
            return False

        parts = content[1:].split()
        command = parts[0].lower() if parts else ""
        arg = parts[1].lower() if len(parts) > 1 else ""

        if command != "conversations":
            return False

        if arg in {"show", "on", "open"}:
            visible = True
        elif arg in {"hide", "off", "close"}:
            visible = False
        else:
            visible = not self.conversations_visible

        self._set_conversations_visible(visible)
        state = "visible" if self.conversations_visible else "hidden"
        app.active_conversation.messages.append(
            ("assistant", f"Conversation drawer is now {state}.")
        )
        self._render_chat()
        self._render_canvas()
        return True

    def _set_conversations_visible(self, visible: bool) -> None:
        self.conversations_visible = visible
        self._apply_conversations_visibility()

    def _apply_conversations_visibility(self) -> None:
        pane = self.query_one("#conversations-pane", Vertical)
        splitter = self.query_one("#splitter-left", PaneSplitter)
        hide_button = self.query_one("#workspace-hide-conversations", Button)
        pane.styles.display = "block" if self.conversations_visible else "none"
        splitter.styles.display = "block" if self.conversations_visible else "none"
        hide_button.styles.display = "block" if self.conversations_visible else "none"

    def _render_conversations(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        option_list = self.query_one("#workspace-conversations", OptionList)
        option_list.clear_options()
        option_list.add_options(
            [
                Option(
                    f"{conv.title}\n{conv.preview}\n{conv.updated_at}",
                    id=conv.conversation_id,
                )
                for conv in app.conversations
            ]
        )
        option_list.highlighted = app.active_conversation_index

    def _render_chat(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        chat_scroll.remove_children()
        for role, content in app.active_conversation.messages:
            bubble_class = "chat-bubble-user" if role == "user" else "chat-bubble-assistant"
            chat_scroll.mount(Static(content, classes=f"chat-bubble {bubble_class}"))
        chat_scroll.scroll_end(animate=False)

    def _set_canvas_tab(self, tab_name: str) -> None:
        self.active_canvas_tab = tab_name
        self._render_canvas()

    def _render_canvas(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsDemoApp)
        content_map = {
            "changes": (
                "Changes\n\n"
                "[] Update monochrome shell spacing\n"
                "[] Add draggable divider component\n"
                "[] Refine login and dashboard transitions\n"
            ),
            "tasks": (
                "Tasks\n\n"
                "1. Analyze requested UX flow\n"
                "2. Build static pane architecture\n"
                "3. Present final visual polish pass\n"
            ),
            "plans": (
                "Plans\n\n"
                "Phase A: Login shell\n"
                "Phase B: Dashboard + conversation picker\n"
                "Phase C: Workspace tri-pane with canvas tabs\n"
            ),
            "files": (
                "Files\n\n"
                "examples/openhands_cli.py\n"
                "examples/components/splitter.py\n"
                "examples/openhands_cli.tcss\n"
            ),
        }
        tab_ids = {
            "changes": "#tab-changes",
            "tasks": "#tab-tasks",
            "plans": "#tab-plans",
            "files": "#tab-files",
        }
        for tab_name, selector in tab_ids.items():
            button = self.query_one(selector, Button)
            button.set_class(tab_name == self.active_canvas_tab, "-active")

        header = f"Active Conversation: {app.active_conversation.title}\n\n"
        self.query_one("#canvas-content", Static).update(
            header + content_map.get(self.active_canvas_tab, "")
        )


class OpenHandsDemoApp(App):
    CSS_PATH = "openhands_cli.tcss"
    TITLE = "OpenHands Monochrome IDE Demo"
    SUB_TITLE = "Login -> dashboard -> tri-pane workspace"

    SCREENS = {
        "login": LoginScreen,
        "dashboard": DashboardScreen,
        "workspace": WorkspaceScreen,
    }

    def __init__(self) -> None:
        super().__init__()
        self.conversation_counter = 0
        self.conversations = self._seed_conversations()
        self.active_conversation_id = self.conversations[0].conversation_id

    @property
    def active_conversation(self) -> Conversation:
        for conversation in self.conversations:
            if conversation.conversation_id == self.active_conversation_id:
                return conversation
        return self.conversations[0]

    @property
    def active_conversation_index(self) -> int:
        for index, conversation in enumerate(self.conversations):
            if conversation.conversation_id == self.active_conversation_id:
                return index
        return 0

    def _seed_conversations(self) -> list[Conversation]:
        now = datetime.now().strftime("%b %d")
        return [
            Conversation(
                conversation_id=str(uuid4()),
                title="Onboarding Polish",
                preview="Build a cleaner first-run experience.",
                updated_at=f"Updated {now}",
                messages=[
                    ("assistant", "Welcome. This is a monochrome full-UI prototype."),
                    ("user", "Show me login, dashboard, and workspace panes."),
                    ("assistant", "Done. Layout is visual and interaction-light by design."),
                ],
            ),
            Conversation(
                conversation_id=str(uuid4()),
                title="UI System Tokens",
                preview="Switch to white lines on black only.",
                updated_at=f"Updated {now}",
                messages=[
                    ("assistant", "Tokens set: background black, text white, muted gray."),
                    ("user", "Keep all buttons outlined and rounded."),
                ],
            ),
            Conversation(
                conversation_id=str(uuid4()),
                title="Canvas Behavior",
                preview="Add Changes / Tasks / Plans / Files tabs.",
                updated_at=f"Updated {now}",
                messages=[
                    ("assistant", "Canvas tabs are now available in the right pane."),
                ],
            ),
        ]

    def set_active_conversation(self, conversation_id: str) -> None:
        self.active_conversation_id = conversation_id

    def create_conversation(self) -> None:
        self.conversation_counter += 1
        conversation = Conversation(
            conversation_id=str(uuid4()),
            title=f"New Conversation {self.conversation_counter}",
            preview="Fresh workspace context.",
            updated_at="Updated just now",
            messages=[
                (
                    "assistant",
                    "New conversation created. Ask for changes, tasks, plans, or files.",
                )
            ],
        )
        self.conversations.insert(0, conversation)
        self.active_conversation_id = conversation.conversation_id

    def on_mount(self) -> None:
        self.push_screen("login")

    def show_dashboard(self) -> None:
        self.switch_screen("dashboard")

    def show_workspace(self) -> None:
        self.switch_screen("workspace")


if __name__ == "__main__":
    app = OpenHandsDemoApp()
    app.run()
