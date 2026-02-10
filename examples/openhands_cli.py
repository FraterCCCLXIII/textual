from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial

from textual import on
from textual.app import App, ComposeResult
from textual.command import Hit, Hits, Provider
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Input, Markdown, OptionList, Static
from textual.widgets.option_list import Option

LOGO = r"""
    ███████                                  █████   █████                          █████        
  ███░░░░░███                               ░░███   ░░███                          ░░███         
 ███     ░░███ ████████   ██████  ████████   ░███    ░███   ██████   ████████    ███████   █████ 
░███      ░███░░███░░███ ███░░███░░███░░███  ░███████████  ░░░░░███ ░░███░░███  ███░░███  ███░░  
░███      ░███ ░███ ░███░███████  ░███ ░███  ░███░░░░░███   ███████  ░███ ░███ ░███ ░███ ░░█████ 
░░███     ███  ░███ ░███░███░░░   ░███ ░███  ░███    ░███  ███░░███  ░███ ░███ ░███ ░███  ░░░░███
 ░░░███████░   ░███████ ░░██████  ████ █████ █████   █████░░████████ ████ █████░░████████ ██████ 
   ░░░░░░░     ░███░░░   ░░░░░░  ░░░░ ░░░░░ ░░░░░   ░░░░░  ░░░░░░░░ ░░░░ ░░░░░  ░░░░░░░░ ░░░░░░  
               ░███                                                                              
               █████                                                                             
              ░░░░░                                                                              
"""


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ConversationThread:
    thread_id: str
    title: str
    repository: str
    messages: list[ChatMessage] = field(default_factory=list)


class OpenHandsCommandProvider(Provider):
    """Mock commands for command lookup in the prototype."""

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)

        for command_id, label, help_text in app.command_entries:
            score = matcher.match(label)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(label),
                    partial(app.execute_mock_command, command_id),
                    help=help_text,
                )


class StartupScreen(Screen):
    """Startup / onboarding screen."""

    BINDINGS = [
        ("enter", "start_prototype", "Start"),
        ("space", "start_prototype", "Start"),
        ("ctrl+p", "app.command_palette", "Commands"),
    ]

    def compose(self) -> ComposeResult:
        tips = (
            "Tips for getting started:\n"
            "1. Press Enter to open the interactive shell.\n"
            "2. Use Ctrl+P to open command lookup.\n"
            "3. Type messages to simulate software-building tasks.\n"
            "4. Switch between local and cloud repository contexts."
        )
        with Container(id="startup-shell"):
            yield Static(LOGO, id="startup-logo")
            yield Static("Welcome to OpenHands CLI (design prototype)", id="startup-title")
            yield Static(tips, id="startup-tips")
            yield Static("Press Enter to start", id="startup-call-to-action")

    def action_start_prototype(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.show_main_screen()


class MainShellScreen(Screen):
    """Main shell with thread list, conversation view, and bottom input."""

    BINDINGS = [
        ("ctrl+p", "app.command_palette", "Commands"),
        ("ctrl+n", "new_thread", "New Thread"),
        ("ctrl+r", "cycle_repo_source", "Repo"),
        ("ctrl+m", "cycle_model", "Model"),
        ("ctrl+d", "app.toggle_dark", "Theme"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="main-shell"):
            yield Static(id="status-line")
            with Horizontal(id="workspace"):
                with Vertical(id="thread-panel"):
                    yield Static("Conversation Threads", classes="panel-title")
                    yield OptionList(id="threads", compact=True)
                with Vertical(id="chat-panel"):
                    yield Static("Active Conversation", classes="panel-title")
                    with VerticalScroll(id="chat-view"):
                        pass
            yield Input(
                placeholder="Type a request (or @path/to/file), then press Enter",
                id="chat-input",
            )
            yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#chat-view", VerticalScroll).anchor()
        await self.sync_from_app_state()
        self.query_one("#chat-input", Input).focus()

    async def sync_from_app_state(self) -> None:
        self._render_thread_list()
        self._render_status_line()
        await self._render_active_thread()

    def _render_thread_list(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        option_list = self.query_one("#threads", OptionList)
        option_list.clear_options()
        options = [
            Option(f"{thread.title}\n{thread.repository}", id=thread.thread_id)
            for thread in app.ordered_threads
        ]
        option_list.add_options(options)
        option_list.highlighted = app.active_thread_index

    def _render_status_line(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        thread = app.active_thread
        self.query_one("#status-line", Static).update(
            "OpenHands CLI  |  "
            f"Repo source: {app.repo_source}  |  "
            f"Model: {app.model_name}  |  "
            f"Thread: {thread.title}"
        )

    async def _render_active_thread(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        chat_view = self.query_one("#chat-view", VerticalScroll)
        await chat_view.remove_children()
        for message in app.active_thread.messages:
            await chat_view.mount(self._make_bubble(message))
        chat_view.scroll_end(animate=False)

    def _make_bubble(self, message: ChatMessage) -> Markdown:
        widget = Markdown(message.content, classes=f"bubble {message.role}")
        if message.role == "assistant":
            widget.border_title = "OpenHands"
        elif message.role == "user":
            widget.border_title = "You"
        return widget

    @on(OptionList.OptionSelected, "#threads")
    async def on_thread_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.set_active_thread(event.option_id)
        await self.sync_from_app_state()

    @on(Input.Submitted, "#chat-input")
    async def on_chat_submitted(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        if not content:
            return

        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        event.input.clear()

        user_message = ChatMessage("user", content)
        app.active_thread.messages.append(user_message)

        assistant_message = ChatMessage("assistant", app.build_mock_response(content))
        app.active_thread.messages.append(assistant_message)

        await self.sync_from_app_state()

    async def action_new_thread(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.create_thread()
        await self.sync_from_app_state()
        self.notify("Created a new mock conversation thread.")

    async def action_cycle_repo_source(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.cycle_repo_source()
        await self.sync_from_app_state()
        self.notify(f"Repository source set to {app.repo_source}.")

    async def action_cycle_model(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.cycle_model()
        await self.sync_from_app_state()
        self.notify(f"Model switched to {app.model_name}.")


class OpenHandsCLIApp(App):
    """Interactive OpenHands CLI prototype with no external dependencies."""

    CSS_PATH = "openhands_cli.tcss"
    TITLE = "OpenHands CLI"
    SUB_TITLE = "Clickable design prototype"

    COMMANDS = App.COMMANDS | {OpenHandsCommandProvider}
    SCREENS = {"startup": StartupScreen, "main": MainShellScreen}

    def __init__(self) -> None:
        super().__init__()
        self.repo_sources = ["local", "cloud"]
        self.repo_source_index = 0
        self.models = ["gpt-4.1", "claude-sonnet", "gemini-2.5-pro"]
        self.model_index = 0
        self.thread_count = 0
        self.threads = self._build_seed_threads()
        self.active_thread_id = next(iter(self.threads))

    @property
    def repo_source(self) -> str:
        return self.repo_sources[self.repo_source_index]

    @property
    def model_name(self) -> str:
        return self.models[self.model_index]

    @property
    def ordered_threads(self) -> list[ConversationThread]:
        return list(self.threads.values())

    @property
    def active_thread_index(self) -> int:
        ids = list(self.threads.keys())
        return ids.index(self.active_thread_id)

    @property
    def active_thread(self) -> ConversationThread:
        return self.threads[self.active_thread_id]

    @property
    def command_entries(self) -> list[tuple[str, str, str]]:
        return [
            ("connect_local", "Connect local repository", "Switch repo source to local"),
            ("connect_cloud", "Connect cloud repository", "Switch repo source to cloud"),
            ("new_thread", "Create new conversation thread", "Start a fresh planning thread"),
            ("switch_model", "Switch active model", "Rotate to next mocked LLM"),
            ("show_examples", "Load conversation examples", "Focus on pre-seeded examples"),
            ("go_startup", "Return to startup screen", "Navigate back to splash/start page"),
        ]

    def on_mount(self) -> None:
        self.push_screen("startup")

    def show_main_screen(self) -> None:
        if isinstance(self.screen, StartupScreen):
            self.pop_screen()
        if not isinstance(self.screen, MainShellScreen):
            self.push_screen("main")

    def set_active_thread(self, thread_id: str) -> None:
        if thread_id in self.threads:
            self.active_thread_id = thread_id

    def cycle_repo_source(self) -> None:
        self.repo_source_index = (self.repo_source_index + 1) % len(self.repo_sources)

    def cycle_model(self) -> None:
        self.model_index = (self.model_index + 1) % len(self.models)

    def create_thread(self) -> None:
        self.thread_count += 1
        thread_id = f"thread-{self.thread_count + len(self.threads)}"
        title = f"Prototype Flow {self.thread_count}"
        repository = (
            "./workspace/new-product"
            if self.repo_source == "local"
            else "github.com/acme/new-product"
        )
        self.threads[thread_id] = ConversationThread(
            thread_id=thread_id,
            title=title,
            repository=repository,
            messages=[
                ChatMessage(
                    "assistant",
                    "New thread ready. Describe the feature and I'll draft an implementation plan.",
                )
            ],
        )
        self.active_thread_id = thread_id

    def build_mock_response(self, prompt: str) -> str:
        if "repo" in prompt.lower():
            return (
                f"Connected context: **{self.repo_source}** repository.\n\n"
                "I can now inspect files, propose architecture, and scaffold feature work."
            )
        if "test" in prompt.lower():
            return (
                "Suggested test plan:\n"
                "1. Add unit tests for command parsing.\n"
                "2. Add integration test for thread switching.\n"
                "3. Verify browser serve interaction flow."
            )
        if "design" in prompt.lower() or "ui" in prompt.lower():
            return (
                "UI pattern proposal:\n"
                "- Startup hero with clear CTA.\n"
                "- Persistent bottom input.\n"
                "- Command lookup via Ctrl+P.\n"
                "- Multi-thread conversation context."
            )
        return (
            "Mock assistant response:\n"
            "I can break this request into tasks, generate scaffold code, and propose tests.\n"
            f"Current model: `{self.model_name}`."
        )

    def execute_mock_command(self, command_id: str) -> None:
        if command_id == "connect_local":
            self.repo_source_index = 0
            self.notify("Connected to local repositories (mock).")
        elif command_id == "connect_cloud":
            self.repo_source_index = 1
            self.notify("Connected to cloud repositories (mock).")
        elif command_id == "new_thread":
            self.create_thread()
            self.notify("Created new conversation thread.")
        elif command_id == "switch_model":
            self.cycle_model()
            self.notify(f"Model switched to {self.model_name}.")
        elif command_id == "show_examples":
            self.active_thread_id = "thread-onboarding"
            self.notify("Loaded example conversation thread.")
        elif command_id == "go_startup":
            if not isinstance(self.screen, StartupScreen):
                self.push_screen("startup")
            return

        if isinstance(self.screen, MainShellScreen):
            self.run_worker(self.screen.sync_from_app_state(), exclusive=True, group="ui-sync")
        else:
            self.show_main_screen()

    def _build_seed_threads(self) -> dict[str, ConversationThread]:
        return {
            "thread-onboarding": ConversationThread(
                thread_id="thread-onboarding",
                title="Onboarding Flow",
                repository="./repos/openhands-cli",
                messages=[
                    ChatMessage(
                        "assistant",
                        "Welcome. I can help you scaffold a CLI architecture for OpenHands.",
                    ),
                    ChatMessage(
                        "user",
                        "Start with startup screen, command lookup, and a bottom input pattern.",
                    ),
                    ChatMessage(
                        "assistant",
                        "Plan ready. I will build reusable screens and mock thread data first.",
                    ),
                ],
            ),
            "thread-local-repo": ConversationThread(
                thread_id="thread-local-repo",
                title="Local Repository Setup",
                repository="./repos/agent-workbench",
                messages=[
                    ChatMessage("user", "Connect to my local repository and scan structure."),
                    ChatMessage(
                        "assistant",
                        "Connected to local path and indexed key modules (mock preview).",
                    ),
                ],
            ),
            "thread-cloud-repo": ConversationThread(
                thread_id="thread-cloud-repo",
                title="Cloud Repository Session",
                repository="github.com/team/agent-console",
                messages=[
                    ChatMessage("user", "Open cloud repo and prepare task breakdown."),
                    ChatMessage(
                        "assistant",
                        "Cloud workspace linked. I can now draft milestones and PR slices.",
                    ),
                ],
            ),
        }


if __name__ == "__main__":
    app = OpenHandsCLIApp()
    app.run()
