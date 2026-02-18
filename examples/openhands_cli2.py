from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, Static

try:
    # Module-style execution: python -m examples.openhands_cli2
    from .openhands_cli import DashboardScreen, OpenHandsDemoApp, WorkspaceScreen
    from .components.splitter import PaneSplitter
except ImportError:
    # Script-style execution: python examples/openhands_cli2.py
    from openhands_cli import DashboardScreen, OpenHandsDemoApp, WorkspaceScreen
    from components.splitter import PaneSplitter


class LoginScreenCLI2(Screen):
    """Centered provider login screen for CLI2 demo."""

    ASCII_MARK = (
        "             │\n"
        "   _ - _  \\  │  /  _ - _\n"
        " _│ │ │ │  \\ │ /  │ │ │ │_\n"
        "│ │ │ │ │         │ │ │ │ │\n"
        "│ │_│_│ │ __   __ │ │_│_│ │\n"
        "│       │/ /   \\ \\│       │\n"
        "│       / /     \\ \\       │\n"
        "│        /       \\        │\n"
        " \\______/         \\______/"
    )

    def compose(self) -> ComposeResult:
        with Container(id="cli2-login-shell"):
            with Vertical(id="cli2-login-card"):
                yield Static(self.ASCII_MARK, id="cli2-login-mark")
                yield Static("Let's get started", id="cli2-login-title")
                yield Button("Log in with GitHub", id="cli2-login-github", classes="oauth-btn")
                yield Button("Log in with GitLab", id="cli2-login-gitlab", classes="oauth-btn")
                yield Button(
                    "Log in with Bitbucket",
                    id="cli2-login-bitbucket",
                    classes="oauth-btn",
                )
                yield Static(
                    "By signing up, you agree to our Terms of Service and Privacy Policy.",
                    id="cli2-login-legal",
                )

    def on_mount(self) -> None:
        sequence = [
            "#cli2-login-mark",
            "#cli2-login-title",
            "#cli2-login-github",
            "#cli2-login-gitlab",
            "#cli2-login-bitbucket",
            "#cli2-login-legal",
        ]
        for index, selector in enumerate(sequence):
            widget = self.query_one(selector)
            widget.styles.opacity = 0.0
            widget.styles.animate(
                "opacity",
                value=1.0,
                duration=0.22,
                delay=0.06 * index,
                easing="out_cubic",
            )

    @on(Button.Pressed, ".oauth-btn")
    def on_provider_pressed(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLI2App)
        app.show_dashboard()


class WorkspaceScreenCLI2(WorkspaceScreen):
    """CLI2 workspace with simplified single-line conversation header."""

    def compose(self) -> ComposeResult:
        with Container(id="workspace-shell"):
            with Horizontal(id="workspace-header"):
                yield Static(id="workspace-title")
                with Horizontal(id="workspace-top-tabs"):
                    yield Button("Changes", id="tab-changes", classes="canvas-tab top-nav-tab")
                    yield Button("Tasks", id="tab-tasks", classes="canvas-tab top-nav-tab")
                    yield Button("Plans", id="tab-plans", classes="canvas-tab top-nav-tab")
                    yield Button("Files", id="tab-files", classes="canvas-tab top-nav-tab")
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
                    yield Static(id="canvas-content")

    def on_mount(self) -> None:
        super().on_mount()
        self._render_cli2_header()

    def _render_canvas(self) -> None:
        super()._render_canvas()
        self._render_cli2_header()

    def _render_cli2_header(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLI2App)
        self.query_one("#workspace-title", Static).update(
            f"[bold #32d74b]●[/] [bold #ffffff]{app.active_conversation.title}[/]"
        )


class OpenHandsCLI2App(OpenHandsDemoApp):
    """OpenHands-CLI2 prototype using the latest monochrome UI system."""

    CSS_PATH = "openhands_cli2.tcss"
    TITLE = "OpenHands-CLI2"
    SUB_TITLE = "Monochrome AI IDE prototype"
    SCREENS = {
        "login": LoginScreenCLI2,
        "dashboard": DashboardScreen,
        "workspace": WorkspaceScreenCLI2,
    }


if __name__ == "__main__":
    app = OpenHandsCLI2App()
    app.run()
