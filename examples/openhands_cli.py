from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import partial
import math
from pathlib import Path
import random
import re
from uuid import uuid4

from textual import events, on
from textual.actions import SkipAction
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.containers import Container, Grid, Horizontal, Vertical, VerticalScroll
from textual.geometry import Region
from textual.screen import ModalScreen, Screen
from textual.strip import Strip
from textual.widgets import Button, Footer, Input, Label, Markdown, OptionList, Select, Static, Tab, Tabs
from textual.widgets._select import SelectCurrent, SelectOverlay
from textual.widgets.option_list import Option
from rich.segment import Segment
from rich.style import Style as RichStyle


class CheckmarkSelectOverlay(SelectOverlay):
    """SelectOverlay base that renders a right-aligned ✓ on the active option row.

    The checkmark is injected into the rendered strip so the label stored in
    Select._options (and displayed by SelectCurrent) stays clean.
    """

    _CHECK_CHAR = "✓"
    _CHECK_COLOR = "#5faf5f"

    def _selected_option_index(self) -> int | None:
        """Return the OptionList index matching the parent Select's current value."""
        parent = self.parent
        if parent is None or not hasattr(parent, "_options") or not hasattr(parent, "value"):
            return None
        value = parent.value
        if value is Select.BLANK:
            return None
        for idx, (_, opt_value) in enumerate(parent._options):
            if opt_value == value:
                return idx
        return None

    def _inject_check(self, strip: Strip) -> Strip:
        """Replace the last content cell of *strip* with the checkmark character."""
        width = strip.cell_length
        if width < 3:
            return strip
        left_part = list(strip.crop(0, width - 2))
        right_border = list(strip)[-1]
        base_style = left_part[-1].style if left_part else RichStyle.null()
        check_seg = Segment(
            self._CHECK_CHAR,
            (base_style or RichStyle.null()) + RichStyle(color=self._CHECK_COLOR),
        )
        return Strip(left_part + [check_seg, right_border], width)

    def _option_widget_y(self, option_index: int, crop: Region) -> int | None:
        """Convert an option index to a crop-relative y coordinate, or None."""
        try:
            content_y = self._index_to_line[option_index] - self.scroll_offset.y
        except KeyError:
            return None
        local_y = content_y + self.styles.gutter.top - crop.y
        return local_y if 0 <= local_y < crop.height else None

    def render_lines(self, crop: Region) -> list[Strip]:
        self._update_lines()
        strips = super().render_lines(crop)
        sel_idx = self._selected_option_index()
        if sel_idx is not None:
            local_y = self._option_widget_y(sel_idx, crop)
            if local_y is not None:
                strips[local_y] = self._inject_check(strips[local_y])
        return strips


class ModelPickerOverlay(CheckmarkSelectOverlay):
    """Overlay for the model picker — adds the active-option checkmark."""


class ModelPickerSelect(Select[str]):
    """Select widget that uses ModelPickerOverlay."""

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield ModelPickerOverlay(type_to_search=self._type_to_search).data_bind(
            compact=Select.compact
        )

    def _on_mouse_down(self, event: events.MouseDown) -> None:
        """Backup: if the SelectCurrent toggle mechanism doesn't fire, open from mouse-down."""
        if not self.expanded:
            def _open_if_still_closed() -> None:
                if not self.expanded:
                    self.focus()
                    self.action_show_overlay()
            self.call_after_refresh(_open_if_still_closed)


class CloudPickerOverlay(CheckmarkSelectOverlay):
    """CheckmarkSelectOverlay that also renders the separator row as border T-junctions
    (├ / ┤) and skips the separator on arrow-key navigation."""

    def _sep_index(self) -> int | None:
        """Return the index of the separator option, or None if absent."""
        for i, option in enumerate(self.options):
            prompt = option.prompt
            if isinstance(prompt, str) and prompt.startswith("─"):
                return i
        return None

    def action_cursor_down(self) -> None:
        super().action_cursor_down()
        if self.highlighted == self._sep_index():
            super().action_cursor_down()

    def action_cursor_up(self) -> None:
        super().action_cursor_up()
        if self.highlighted == self._sep_index():
            super().action_cursor_up()

    def render_lines(self, crop: Region) -> list[Strip]:
        # super() runs CheckmarkSelectOverlay.render_lines which handles ✓ injection
        strips = super().render_lines(crop)

        sep_index = self._sep_index()
        if sep_index is None:
            return strips

        local_y = self._option_widget_y(sep_index, crop)
        if local_y is None:
            return strips

        # Swap │ → ├ / ┤ and unify border color across the entire separator row.
        segments = list(strips[local_y])
        if len(segments) >= 2:
            border_style = segments[0].style
            new_segments: list[Segment] = []
            for idx, seg in enumerate(segments):
                if idx == 0:
                    new_segments.append(Segment("├" if seg.text == "│" else seg.text, border_style))
                elif idx == len(segments) - 1:
                    new_segments.append(Segment("┤" if seg.text == "│" else seg.text, border_style))
                else:
                    new_segments.append(Segment(seg.text, border_style))
            strips[local_y] = Strip(new_segments, strips[local_y].cell_length)

        return strips


class CloudPickerSelect(Select[str]):
    """Select widget whose overlay renders separators as proper border T-junctions."""

    def compose(self) -> ComposeResult:
        yield SelectCurrent(self.prompt)
        yield CloudPickerOverlay(type_to_search=self._type_to_search).data_bind(
            compact=Select.compact
        )

    def _on_mouse_down(self, event: events.MouseDown) -> None:
        """Backup: if the SelectCurrent toggle mechanism doesn't fire, open from mouse-down."""
        if not self.expanded:
            def _open_if_still_closed() -> None:
                if not self.expanded:
                    self.focus()
                    self.action_show_overlay()
            self.call_after_refresh(_open_if_still_closed)


class ConversationTabs(Tabs):
    """Tabs for conversations. Focus returns to chat input after tab switch."""


from markdown_it import MarkdownIt
from rich.text import Text

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


def markdown_parser_no_linkify() -> MarkdownIt:
    """Create a markdown parser that does not require linkify-it-py."""
    return MarkdownIt("commonmark", {"linkify": False})


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


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str


@dataclass
class OnboardingOption:
    label: str
    detail: str = ""


@dataclass
class TodoItem:
    title: str
    todo_id: str
    status: str
    reason: str = ""


class ModalDialogScreen(ModalScreen[None]):
    """Modal dialog with buttons, shown via /modal command."""

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("Modal Dialog", id="modal-title"),
            Button("OK", id="modal-ok"),
            Button("Cancel", id="modal-cancel"),
            id="modal-dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class CloudConnectModalScreen(ModalScreen[None]):
    """Minimal cloud connect dialog launched from the status bar dropdown."""

    def compose(self) -> ComposeResult:
        with Vertical(id="cloud-connect-modal"):
            yield Static("Sign in with OpenHands Cloud", id="cloud-connect-title")
            yield Static("Browser opened. Complete login in your browser.", id="cloud-connect-body")
            yield Static(
                "https://app.all-hands.dev/oauth/device?code=NXYZ5678",
                id="cloud-connect-link",
            )
            yield Static(
                "Waiting for authentication to complete...",
                id="cloud-connect-waiting",
            )
            yield Button("Cancel", id="cloud-connect-cancel")

    @on(Button.Pressed, "#cloud-connect-cancel")
    def on_cloud_connect_cancel(self) -> None:
        self.dismiss()

    @on(events.Click, "#cloud-connect-link")
    def on_cloud_connect_link_clicked(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.cloud_connected = True
        self.notify("Cloud authentication confirmed.")
        self.dismiss()


class CloudDisconnectConfirmScreen(ModalScreen[bool]):
    """Confirmation dialog before disconnecting from OpenHands Cloud."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(id="cloud-disconnect-modal"):
            yield Static("Disconnect from Cloud?", id="cloud-disconnect-title")
            yield Static(
                "This will switch your repository source back to Local.",
                id="cloud-disconnect-body",
            )
            with Horizontal(id="cloud-disconnect-buttons"):
                yield Button("Disconnect", id="cloud-disconnect-confirm", variant="error")
                yield Button("Cancel", id="cloud-disconnect-cancel")

    @on(Button.Pressed, "#cloud-disconnect-confirm")
    def on_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cloud-disconnect-cancel")
    def action_cancel(self) -> None:
        self.dismiss(False)


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


class OnboardingScreen(Screen):
    """Startup + onboarding flow screen."""

    BINDINGS = [
        ("up,k", "cursor_up", "Up"),
        ("down,j", "cursor_down", "Down"),
        ("enter", "confirm", "Select"),
        ("space", "confirm", "Select"),
        ("ctrl+p", "app.command_palette", "Commands"),
    ]

    STEP_ONE_OPTIONS = [
        OnboardingOption(
            "Connect to OpenHands ($20 free credits for new users)",
            "Available models: claude-sonnet-4, gpt-5, gemini-2.5-pro, and more",
        ),
        OnboardingOption(
            "Use your own LLM Provider",
            "Available providers: anthropic, openai, mistral",
        ),
        OnboardingOption("Exit", "See you later!"),
    ]

    STEP_TWO_OPTIONS = [
        OnboardingOption("Yes, proceed (Y)"),
        OnboardingOption("No, exit (N)"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.step = 1
        self.selected_index = 0
        self.logo_time = 0.0
        rng = random.Random(57)
        self.logo_blobs: list[dict[str, float]] = [
            {
                "phase": rng.uniform(0.0, math.tau),
                "speed_x": rng.uniform(0.55, 1.1),
                "speed_y": rng.uniform(0.45, 1.0),
                "radius": rng.uniform(0.16, 0.34),
                "strength": rng.uniform(0.9, 1.4),
            }
            for _ in range(6)
        ]

    def compose(self) -> ComposeResult:
        with Container(id="startup-shell"):
            yield Static(LOGO, id="startup-logo")
            yield Static("OpenHands CLI v0.57.0", id="startup-version")
            yield Static("No settings found — let's set you up!", id="startup-pill")
            yield Static(id="onboarding-main-card")
            yield Static(id="onboarding-choice-card")
            yield Static("Use ↑/↓ to navigate and Enter to continue", id="startup-call-to-action")

    def on_mount(self) -> None:
        self._update_logo_animation()
        self.logo_timer = self.set_interval(1 / 20, self._update_logo_animation)
        self._render_step()

    def on_unmount(self) -> None:
        self.logo_timer.stop()

    def action_cursor_up(self) -> None:
        options = self.STEP_ONE_OPTIONS if self.step == 1 else self.STEP_TWO_OPTIONS
        self.selected_index = (self.selected_index - 1) % len(options)
        self._render_step()

    def action_cursor_down(self) -> None:
        options = self.STEP_ONE_OPTIONS if self.step == 1 else self.STEP_TWO_OPTIONS
        self.selected_index = (self.selected_index + 1) % len(options)
        self._render_step()

    def action_confirm(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        if self.step == 1:
            if self.selected_index == 2:
                app.exit()
                return
            app.provider_choice = (
                "OpenHands" if self.selected_index == 0 else "Custom Provider"
            )
            self.step = 2
            self.selected_index = 0
            self.query_one("#startup-pill", Static).update("Step 1 complete")
            self._render_step()
            return

        if self.selected_index == 1:
            app.exit()
            return

        app.complete_onboarding()
        self.query_one("#startup-pill", Static).update("All set up!")
        app.show_main_screen()

    def _render_step(self) -> None:
        if self.step == 1:
            self._render_step_one()
        else:
            self._render_step_two()

    def _render_step_one(self) -> None:
        card = (
            "Step 1\n\n"
            "Select your LLM Provider\n\n"
            f"{self._format_options(self.STEP_ONE_OPTIONS)}"
        )
        self.query_one("#onboarding-main-card", Static).update(card)
        self.query_one("#onboarding-choice-card", Static).update("")
        self.query_one("#onboarding-choice-card", Static).remove_class("-visible")

    def _render_step_two(self) -> None:
        cwd = str(Path.cwd())
        main_card = (
            "Step 2\n\n"
            "Do you trust the files in this folder?\n\n"
            f"{cwd}\n\n"
            "OpenHands may read and execute files in this folder with your permission."
        )
        choice_card = "Do you wish to continue?\n\n" + self._format_options(
            self.STEP_TWO_OPTIONS
        )
        self.query_one("#onboarding-main-card", Static).update(main_card)
        self.query_one("#onboarding-choice-card", Static).update(choice_card)
        self.query_one("#onboarding-choice-card", Static).add_class("-visible")

    def _update_logo_animation(self) -> None:
        lines = LOGO.splitlines()
        max_width = max(len(line) for line in lines) if lines else 1
        max_height = max(len(lines), 1)
        animated_logo = Text()
        for line_index, line in enumerate(lines):
            for char_index, char in enumerate(line):
                if char.isspace():
                    animated_logo.append(char)
                    continue
                nx = char_index / max(max_width - 1, 1)
                ny = line_index / max(max_height - 1, 1)

                # Add fluid motion so color blobs appear to intersect organically.
                wx = nx + 0.08 * math.sin(self.logo_time * 0.8 + ny * 8.5)
                wy = ny + 0.08 * math.cos(self.logo_time * 0.65 + nx * 7.2)

                luminance_mix = 0.0
                weight_total = 0.0

                for blob in self.logo_blobs:
                    cx = 0.5 + 0.38 * math.sin(self.logo_time * blob["speed_x"] + blob["phase"])
                    cy = 0.5 + 0.32 * math.cos(
                        self.logo_time * blob["speed_y"] + blob["phase"] * 1.13
                    )
                    dx = wx - cx
                    dy = wy - cy
                    dist2 = dx * dx + dy * dy
                    radius = blob["radius"]
                    influence = math.exp(-dist2 / max(radius * radius, 1e-5))
                    weight = influence * blob["strength"]

                    pulse = 0.55 + 0.45 * math.sin(
                        self.logo_time * 1.1 + blob["phase"] + nx * 4.5 - ny * 3.8
                    )
                    luminance_mix += pulse * weight
                    weight_total += weight

                if weight_total == 0:
                    luminance = 0.74
                else:
                    luminance = min(max(0.35 + 0.65 * (luminance_mix / weight_total), 0.24), 1.0)

                # Keep organic movement while remaining monochrome.
                luminance *= 0.9 + 0.18 * (
                    0.5
                    + 0.5
                    * math.sin(self.logo_time * 2.3 + char_index * 0.67 + line_index * 0.91)
                )
                gray = int(min(max(luminance, 0.0), 1.0) * 255)
                animated_logo.append(
                    char,
                    style=f"bold rgb({gray},{gray},{gray})",
                )
            animated_logo.append("\n")

        self.logo_time += 0.06
        self.query_one("#startup-logo", Static).update(animated_logo)

    def _format_options(self, options: list[OnboardingOption]) -> str:
        lines: list[str] = []
        for index, option in enumerate(options, start=1):
            prefix = ">" if (index - 1) == self.selected_index else " "
            lines.append(f"{prefix} {index}. {option.label}")
            if option.detail:
                lines.append(f"   {option.detail}")
            if index < len(options):
                lines.append("")
        return "\n".join(lines)


class _ModelFooterLabel(Static):
    """Status-footer label that opens the model picker when clicked."""

    async def on_click(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_cycle_model"):
            await screen.action_cycle_model()


class _CloudFooterLabel(Static):
    """Status-footer label that opens the cloud picker when clicked."""

    def on_click(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_expand_cloud_picker"):
            screen.action_expand_cloud_picker()


class MainShellScreen(Screen):
    """Main shell with thread list, conversation view, and bottom input."""

    BINDINGS = [
        Binding("super+c", "screen.copy_text", "Copy", show=False),
        ("ctrl+p", "app.command_palette", "Commands"),
        ("ctrl+l", "toggle_thread_drawer", "Drawer"),
        ("ctrl+n", "new_thread", "New Thread"),
        ("ctrl+r", "cycle_repo_source", "Repo"),
        ("ctrl+s", "toggle_task_output_details", "Details"),
        ("ctrl+d,ctrl+w", "toggle_tips_drawer", "Tips"),
        ("ctrl+t", "app.toggle_dark", "Theme"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="main-shell"):
            yield ConversationTabs(id="conversation-tabs")
            with Horizontal(id="workspace"):
                with Horizontal(id="workspace-columns"):
                    with Vertical(id="thread-panel"):
                        yield Static("Conversations", classes="panel-title")
                        yield OptionList(id="threads", compact=True)
                    with Vertical(id="chat-panel"):
                        with VerticalScroll(id="chat-view"):
                            pass
                        with Horizontal(id="chat-input-row"):
                            yield Static(">", id="chat-input-prefix")
                            yield Input(
                                placeholder="Type a request or / to access command menu",
                                id="chat-input",
                            )
                        with Horizontal(id="status-footer"):
                            yield Static(id="status-left")
                            yield _ModelFooterLabel("✦", id="model-icon")
                            yield _ModelFooterLabel("Model:", id="model-label")
                            yield ModelPickerSelect(
                                (
                                    (model, model)
                                    for model in OpenHandsCLIApp.DEFAULT_MODELS
                                ),
                                value=OpenHandsCLIApp.DEFAULT_MODELS[0],
                                allow_blank=False,
                                compact=True,
                                id="model-picker",
                            )
                            yield _ModelFooterLabel("^m     ⛁", id="model-shortcut")
                            yield CloudPickerSelect(
                                (
                                    (" Local", "local"),
                                    (" Connect to Cloud", "connect_cloud"),
                                ),
                                value="local",
                                allow_blank=False,
                                compact=True,
                                id="cloud-picker",
                            )
                            yield _CloudFooterLabel("^c", id="cloud-shortcut")
                with Container(id="board-view"):
                    with Horizontal(id="board-columns"):
                        with Vertical(classes="board-column"):
                            yield Static("OPEN", classes="board-column-title")
                            yield OptionList(id="board-open-list", classes="board-list", compact=True)
                        with Vertical(classes="board-column"):
                            yield Static("REVIEW", classes="board-column-title")
                            yield OptionList(
                                id="board-review-list", classes="board-list", compact=True
                            )
                        with Vertical(classes="board-column"):
                            yield Static("MERGED", classes="board-column-title")
                            yield OptionList(
                                id="board-merged-list", classes="board-list", compact=True
                            )
                yield Static(id="fly-view")
            yield Static(id="tips-drawer")
            yield Static("Proceed with action?", id="approval-title")
            yield OptionList(id="approval-options", compact=True)
            yield OptionList(id="slash-menu", compact=True)
            yield Static(id="slash-submenu-title")
            yield OptionList(id="slash-submenu", compact=True)

    async def on_mount(self) -> None:
        self.query_one("#chat-view", VerticalScroll).anchor()
        self.slash_matches: list[SlashCommand] = []
        self.slash_selected_index = 0
        self.slash_submenu_command: str | None = None
        self.drawer_visible = False
        self.tips_visible = False
        self.approval_visible = False
        self.task_output_expanded = True
        self.last_task_prompt = ""
        self.last_task_message: ChatMessage | None = None
        self.code_city_visible = False
        self.kanban_visible = False
        self._is_rendering_tabs = False
        self.code_city_phase = 0.0
        self.code_city_timer = None
        self.code_city_towers = self._build_code_city_towers()
        self.board_task_to_thread: dict[str, str] = {}
        self._updating_cloud_picker = False
        self.code_city_loop_length = max(
            (tower["z"] + tower["depth"] for tower in self.code_city_towers),
            default=240.0,
        ) + 12.0
        await self.sync_from_app_state()
        self.query_one("#chat-input", Input).focus()
        self._hide_slash_menu()
        self._hide_slash_submenu()
        self._setup_approval_options()
        self._render_kanban_board()
        self._apply_thread_drawer_visibility()
        self._apply_workspace_mode()
        self._render_code_city_scene()
        self._set_alternate_scroll_mode(True)

    def on_unmount(self) -> None:
        self._set_alternate_scroll_mode(False)
        if self.code_city_timer is not None:
            self.code_city_timer.stop()
            self.code_city_timer = None

    def _set_alternate_scroll_mode(self, enabled: bool) -> None:
        """Hint supported terminals to route wheel events to the app in alt-screen."""
        driver = self.app._driver
        if driver is None:
            return
        driver.write("\x1b[?1007h" if enabled else "\x1b[?1007l")
        driver.flush()

    @on(events.ScreenResume)
    async def _on_screen_resume_refresh(self) -> None:
        """Refresh state when returning from modals (e.g. command palette)."""
        await self.sync_from_app_state()

    async def sync_from_app_state(self, *, include_tabs: bool = True) -> None:
        if include_tabs:
            await self._render_conversation_tabs()
        self._render_thread_list()
        self._render_status_line()
        self._render_tips_drawer()
        self._render_approval_prompt()
        self._render_kanban_board()
        await self._render_active_thread()
        if not self.approval_visible:
            self.query_one("#chat-input", Input).focus()

    async def _render_conversation_tabs(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        self._is_rendering_tabs = True
        try:
            tabs = self.query_one("#conversation-tabs", ConversationTabs)
            await tabs.clear()
            for thread in app.ordered_threads:
                await tabs.add_tab(Tab(thread.title, id=thread.thread_id))
            tabs.active = app.active_thread_id
        finally:
            self._is_rendering_tabs = False

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
        repo_name = thread.repository.rstrip("/").split("/")[-1] or thread.repository
        branch_name = app.branch_name
        repo_display = repo_name if len(repo_name) <= 12 else f"{repo_name[:11]}…"
        branch_display = branch_name if len(branch_name) <= 12 else f"{branch_name[:11]}…"
        self.query_one("#status-left", Static).update(f"[#8a8a8a]<>[/] {repo_display}   [#8a8a8a]⎇[/] {branch_display}   ")
        model_picker = self.query_one("#model-picker", Select)
        model_picker.set_options((model, model) for model in app.models)
        model_picker.value = app.model_name
        cloud_picker = self.query_one("#cloud-picker", Select)
        self._updating_cloud_picker = True
        try:
            cloud_picker.set_options((label, value) for label, value in app.cloud_picker_options)
            cloud_picker.value = "cloud" if app.repo_source == "cloud" else "local"
        finally:
            self._updating_cloud_picker = False

    def _render_tips_drawer(self) -> None:
        drawer = self.query_one("#tips-drawer", Static)
        if not self.tips_visible:
            drawer.update("")
            drawer.remove_class("-visible")
            return

        tips = (
            "Tips (Ctrl-D/Ctrl-W to dismiss)\n\n"
            "• Use /help or / to browse available commands.\n\n"
            "• Use Ctrl+P for command lookup and fuzzy actions.\n\n"
            "• Mention a file path like @src/app.py to scope analysis.\n\n"
            "• Use /tips to toggle this drawer."
        )
        drawer.update(tips)
        drawer.add_class("-visible")

    def _apply_thread_drawer_visibility(self) -> None:
        if self.code_city_visible or self.kanban_visible:
            return
        panel = self.query_one("#thread-panel", Vertical)
        panel.styles.display = "block" if self.drawer_visible else "none"

    def _apply_workspace_mode(self) -> None:
        columns = self.query_one("#workspace-columns", Horizontal)
        board = self.query_one("#board-view", Container)
        flythrough = self.query_one("#fly-view", Static)
        if self.code_city_visible:
            columns.styles.display = "none"
            board.remove_class("-visible")
            flythrough.add_class("-visible")
            return
        if self.kanban_visible:
            columns.styles.display = "none"
            flythrough.remove_class("-visible")
            board.add_class("-visible")
            self.query_one("#board-open-list", OptionList).focus()
            return
        columns.styles.display = "block"
        board.remove_class("-visible")
        flythrough.remove_class("-visible")
        self._apply_thread_drawer_visibility()

    def _setup_approval_options(self) -> None:
        option_list = self.query_one("#approval-options", OptionList)
        option_list.clear_options()
        option_list.add_options(
            [
                Option("Yes, allow once (Y)", id="allow_once"),
                Option("No (N)", id="deny"),
                Option("Always (A)", id="always"),
            ]
        )
        option_list.highlighted = 0

    def _render_approval_prompt(self) -> None:
        title = self.query_one("#approval-title", Static)
        options = self.query_one("#approval-options", OptionList)
        if self.approval_visible:
            title.add_class("-visible")
            options.add_class("-visible")
        else:
            title.remove_class("-visible")
            options.remove_class("-visible")

    def _set_code_city_scene_enabled(self, enabled: bool) -> None:
        self.code_city_visible = enabled
        if enabled:
            self.kanban_visible = False
        self._apply_workspace_mode()
        if enabled:
            if self.code_city_timer is None:
                self.code_city_timer = self.set_interval(
                    1 / 12, self._advance_code_city_scene
                )
            self._render_code_city_scene()
            return

        if self.code_city_timer is not None:
            self.code_city_timer.stop()
            self.code_city_timer = None
        self._render_code_city_scene()

    def _set_kanban_board_enabled(self, enabled: bool) -> None:
        self.kanban_visible = enabled
        if enabled:
            self.code_city_visible = False
            if self.code_city_timer is not None:
                self.code_city_timer.stop()
                self.code_city_timer = None
            self._render_kanban_board()
        self._apply_workspace_mode()

    def _build_kanban_cards(self) -> dict[str, list[dict[str, str]]]:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        threads = app.ordered_threads
        status_order = ["OPEN", "REVIEW", "MERGED"]
        templates = [
            ("PR #431", "Onboarding trust flow polish"),
            ("PR #432", "Command submenu keyboard fixes"),
            ("PR #433", "Monochrome theme token pass"),
            ("PR #434", "Tips drawer interaction polish"),
            ("PR #435", "Cost and todo thread components"),
            ("PR #436", "Workspace fly mode renderer"),
        ]
        status_cards: dict[str, list[dict[str, str]]] = {key: [] for key in status_order}
        if not threads:
            return status_cards

        for index, (pr_id, title) in enumerate(templates):
            thread = threads[index % len(threads)]
            status = status_order[index % len(status_order)]
            status_cards[status].append(
                {
                    "task_id": f"board-{status.lower()}-{index}",
                    "pr": pr_id,
                    "title": title,
                    "thread_id": thread.thread_id,
                    "thread_title": thread.title,
                    "repo": thread.repository,
                }
            )
        return status_cards

    def _render_kanban_board(self) -> None:
        cards = self._build_kanban_cards()
        self.board_task_to_thread = {}
        column_map = [
            ("OPEN", "#board-open-list"),
            ("REVIEW", "#board-review-list"),
            ("MERGED", "#board-merged-list"),
        ]
        for status, selector in column_map:
            option_list = self.query_one(selector, OptionList)
            option_list.clear_options()
            options: list[Option] = []
            for card in cards[status]:
                self.board_task_to_thread[card["task_id"]] = card["thread_id"]
                label = (
                    f"┌ {card['pr']}\n"
                    f"│ {card['title']}\n"
                    f"│ conv: {card['thread_title']}\n"
                    f"│ repo: {card['repo']}\n"
                    "└"
                )
                options.append(Option(label, id=card["task_id"]))
            if not options:
                options.append(Option("┌ No PRs\n└", id=f"{status.lower()}-none"))
            option_list.add_options(options)
            option_list.highlighted = 0

    def _advance_code_city_scene(self) -> None:
        if not self.code_city_visible:
            return
        self.code_city_phase += 0.38
        self._render_code_city_scene()

    def _build_code_city_towers(self) -> list[dict[str, float]]:
        rng = random.Random(2112)
        towers: list[dict[str, float]] = []
        for index in range(44):
            side = -1.0 if index % 2 == 0 else 1.0
            z = 10.0 + index * 7.2 + rng.uniform(-1.4, 1.8)
            width = rng.uniform(2.2, 5.2)
            depth = rng.uniform(2.6, 5.6)
            height = rng.uniform(8.0, 36.0)
            setback = rng.uniform(7.0, 15.0)
            x_center = side * (setback + width * 0.5 + rng.uniform(-1.2, 1.2))
            towers.append(
                {
                    "x0": x_center - width / 2,
                    "x1": x_center + width / 2,
                    "z": z,
                    "depth": depth,
                    "height": height,
                }
            )
        return towers

    def _render_code_city_scene(self) -> None:
        scene = self.query_one("#fly-view", Static)
        if not self.code_city_visible:
            scene.update("")
            scene.remove_class("-visible")
            return
        # Render as plain text because the frame intentionally contains [] and <> glyphs.
        scene.update(Text(self._build_code_city_frame()))
        scene.add_class("-visible")

    def _build_code_city_frame(self) -> str:
        scene = self.query_one("#fly-view", Static)
        frame_width = scene.size.width if scene.size.width else 0
        frame_height = scene.size.height if scene.size.height else 0
        width = max(72, frame_width if frame_width > 0 else 108)
        height = max(16, frame_height if frame_height > 0 else 20)
        center = width // 2
        travel = self.code_city_phase
        grid = [[" "] * width for _ in range(height)]
        horizon = max(2, int(height * 0.30))
        near_plane = 1.1
        far_plane = 120.0
        focal = width * 0.95
        camera_y = 2.0

        def put(x: int, y: int, ch: str) -> None:
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = ch

        def draw_line(x1: int, y1: int, x2: int, y2: int, ch: str) -> None:
            steps = max(abs(x2 - x1), abs(y2 - y1), 1)
            steps = min(steps, (width + height) * 2)
            for step in range(steps + 1):
                t = step / steps
                x = int(round(x1 + (x2 - x1) * t))
                y = int(round(y1 + (y2 - y1) * t))
                put(x, y, ch)

        def project(x: float, y_world: float, z: float) -> tuple[int, int] | None:
            if z <= near_plane or z >= far_plane:
                return None
            y = y_world - camera_y
            scale = focal / z
            sx = int(round(center + x * scale))
            sy = int(round(horizon - y * scale))
            return sx, sy

        def depth_char(z: float) -> str:
            if z < 12:
                return "#"
            if z < 26:
                return "|"
            if z < 48:
                return ":"
            return "."

        # Distant skyline stars.
        for x in range(width):
            if (x * 11 + int(travel * 19)) % 29 == 0:
                put(x, max(0, horizon - 2), ".")

        # Ground grid / lane traces with perspective projection.
        road_half_world = 5.4
        stride = 3.2
        z_cursor = near_plane + 0.8
        grid_phase = (travel * 2.7) % stride
        while z_cursor < far_plane:
            z = z_cursor + (stride - grid_phase)
            left = project(-road_half_world, 0.0, z)
            right = project(road_half_world, 0.0, z)
            if left and right:
                draw_line(left[0], left[1], right[0], right[1], ".")
            z_cursor += stride

        for x in (-3.6, -2.0, 0.0, 2.0, 3.6):
            prev = None
            z = near_plane + 0.9
            while z < far_plane:
                point = project(x, 0.0, z)
                if prev and point:
                    draw_line(prev[0], prev[1], point[0], point[1], "|")
                prev = point
                z += 2.6

        # Draw tower cuboids far-to-near for stable layering.
        wrapped_towers: list[dict[str, float]] = []
        loop_length = max(self.code_city_loop_length, 120.0)
        for tower in self.code_city_towers:
            z_near = ((tower["z"] - travel) % loop_length) + near_plane + 1.8
            z_far = z_near + tower["depth"]
            if z_near >= far_plane:
                continue
            wrapped_towers.append(
                {
                    "x0": tower["x0"],
                    "x1": tower["x1"],
                    "height": tower["height"],
                    "z_near": z_near,
                    "z_far": z_far,
                }
            )

        wrapped_towers.sort(key=lambda item: item["z_near"], reverse=True)

        for index, tower in enumerate(wrapped_towers):
            x0 = tower["x0"]
            x1 = tower["x1"]
            h = tower["height"]
            z0 = tower["z_near"]
            z1 = tower["z_far"]
            edge = depth_char(z0)

            # 8 cuboid corners: bottom ring then top ring.
            corners_world = [
                (x0, 0.0, z0),
                (x1, 0.0, z0),
                (x1, 0.0, z1),
                (x0, 0.0, z1),
                (x0, h, z0),
                (x1, h, z0),
                (x1, h, z1),
                (x0, h, z1),
            ]
            corners = [project(*corner) for corner in corners_world]
            if any(corner is None for corner in corners):
                continue

            points = [corner for corner in corners if corner is not None]
            if len(points) != 8:
                continue

            # Edges for a cuboid (wireframe).
            edges = [
                (0, 1),
                (1, 2),
                (2, 3),
                (3, 0),
                (4, 5),
                (5, 6),
                (6, 7),
                (7, 4),
                (0, 4),
                (1, 5),
                (2, 6),
                (3, 7),
            ]
            for a, b in edges:
                pa = points[a]
                pb = points[b]
                draw_line(pa[0], pa[1], pb[0], pb[1], edge)

            # Window/facade glyphs on near face for depth cues.
            window_cols = max(2, int((x1 - x0) * 2.0))
            window_rows = max(3, int(h / 3.0))
            for c in range(1, window_cols):
                for r in range(1, window_rows):
                    wx = x0 + (x1 - x0) * (c / window_cols)
                    wy = h * (r / window_rows)
                    wp = project(wx, wy, z0)
                    if wp is None:
                        continue
                    marker_roll = (c * 7 + r * 11 + int(travel * 13) + index) % 6
                    marker = "1" if marker_roll in {0, 1} else "0" if marker_roll == 2 else "."
                    put(wp[0], wp[1], marker)

        # Return a full-frame buffer (no header/footer) so the animation fills the container.
        lines = ["".join(row) for row in grid]
        return "\n".join(lines)

    async def _render_active_thread(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        chat_view = self.query_one("#chat-view", VerticalScroll)
        await chat_view.remove_children()
        for message in app.active_thread.messages:
            await chat_view.mount(self._make_bubble(message))
        chat_view.scroll_end(animate=False)

    def _make_bubble(self, message: ChatMessage) -> Markdown:
        return Markdown(
            message.content,
            classes=f"chat-line {message.role}",
            parser_factory=markdown_parser_no_linkify,
        )

    @on(ConversationTabs.TabActivated, "#conversation-tabs")
    async def on_conversation_tab_activated(self, event: Tabs.TabActivated) -> None:
        if self._is_rendering_tabs or event.tab is None or event.tab.id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.set_active_thread(event.tab.id)
        await self.sync_from_app_state(include_tabs=False)

    @on(Tab.Clicked)
    async def on_conversation_tab_clicked(self, event: Tab.Clicked) -> None:
        """Handle direct tab clicks even when activation event is missed."""
        tabs = self.query_one("#conversation-tabs", ConversationTabs)
        if tabs not in event.tab.ancestors:
            return
        if self._is_rendering_tabs or event.tab.id is None:
            return
        event.stop()
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.set_active_thread(event.tab.id)
        await self.sync_from_app_state(include_tabs=False)

    @on(OptionList.OptionSelected, "#threads")
    async def on_thread_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.set_active_thread(event.option_id)
        await self.sync_from_app_state()

    @on(OptionList.OptionSelected, "#board-open-list")
    async def on_board_open_selected(self, event: OptionList.OptionSelected) -> None:
        await self._open_kanban_card(event.option_id)

    @on(OptionList.OptionSelected, "#board-review-list")
    async def on_board_review_selected(self, event: OptionList.OptionSelected) -> None:
        await self._open_kanban_card(event.option_id)

    @on(OptionList.OptionSelected, "#board-merged-list")
    async def on_board_merged_selected(self, event: OptionList.OptionSelected) -> None:
        await self._open_kanban_card(event.option_id)

    async def _open_kanban_card(self, option_id: str | None) -> None:
        if option_id is None or option_id.endswith("-none"):
            return
        thread_id = self.board_task_to_thread.get(option_id)
        if thread_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.set_active_thread(thread_id)
        self._set_kanban_board_enabled(False)
        await self.sync_from_app_state()
        self.query_one("#chat-input", Input).focus()
        self.notify("Opened related conversation from Kanban task.")

    @on(Input.Submitted, "#chat-input")
    async def on_chat_submitted(self, event: Input.Submitted) -> None:
        content = event.value.strip()
        if not content:
            return

        app = self.app
        assert isinstance(app, OpenHandsCLIApp)

        if content.startswith("/"):
            handled = await self._run_slash_command(content)
            if handled:
                event.input.clear()
                self._hide_slash_menu()
            return

        event.input.clear()
        self._hide_slash_menu()

        user_message = ChatMessage("user", content)
        app.active_thread.messages.append(user_message)

        processing_message = ChatMessage("assistant", app.build_processing_preview(content))
        app.active_thread.messages.append(processing_message)
        await self.sync_from_app_state()
        await asyncio.sleep(0.9)

        self.task_output_expanded = True
        self.last_task_prompt = content
        self.last_task_message = processing_message
        processing_message.content = app.build_completed_task_result(
            prompt=content, expanded=self.task_output_expanded
        )
        app.increment_credit_cost(content)
        app.active_thread.messages.append(
            ChatMessage("assistant", app.build_cost_component())
        )
        app.advance_todo_progress()
        await self.sync_from_app_state()

    @on(Input.Changed, "#chat-input")
    def on_chat_input_changed(self, event: Input.Changed) -> None:
        value = event.value.strip()
        if not value.startswith("/"):
            self._hide_slash_menu()
            self._hide_slash_submenu()
            return

        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        query = value[1:].strip().lower()
        commands = app.slash_commands
        matches = [
            command
            for command in commands
            if not query
            or command.name.startswith(query)
            or query in command.description.lower()
        ]

        if not matches:
            self._show_slash_menu_no_results()
            self.slash_matches = []
            self.slash_selected_index = 0
            return

        self.slash_matches = matches
        self.slash_selected_index = 0
        self._render_slash_menu()

    async def action_new_thread(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        app.create_thread()
        await self.sync_from_app_state()
        self.notify("Created a new mock conversation thread.")

    def action_expand_cloud_picker(self) -> None:
        cloud_picker = self.query_one("#cloud-picker", Select)
        if cloud_picker.expanded:
            cloud_picker.expanded = False
            self.query_one("#chat-input", Input).focus()
        else:
            cloud_picker.focus()
            cloud_picker.action_show_overlay()

    async def action_cycle_repo_source(self) -> None:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        changed = app.cycle_repo_source()
        await self.sync_from_app_state()
        if changed:
            self.notify(f"Repository source set to {app.repo_source}.")
        else:
            self.notify("Connect to Cloud before switching to cloud source.")

    async def action_cycle_model(self) -> None:
        model_picker = self.query_one("#model-picker", Select)
        if model_picker.expanded:
            model_picker.expanded = False
            self.query_one("#chat-input", Input).focus()
            return
        model_picker.focus()
        model_picker.action_show_overlay()

    async def action_toggle_tips_drawer(self) -> None:
        self.tips_visible = not self.tips_visible
        self._render_tips_drawer()

    async def action_toggle_thread_drawer(self) -> None:
        self.drawer_visible = not self.drawer_visible
        self._apply_thread_drawer_visibility()
        state = "shown" if self.drawer_visible else "hidden"
        self.notify(f"Conversation drawer {state}.")

    async def on_key(self, event: events.Key) -> None:
        chat_input = self.query_one("#chat-input", Input)
        # Some terminals/input states can intercept Ctrl bindings; keep a direct fallback.
        if event.key == "super+c":
            event.stop()
            try:
                self.action_copy_text()
            except SkipAction:
                self.notify("Select text first, then press Cmd+C.")
            else:
                self.notify("Copied selected text.")
            return
        if event.key in {"ctrl+d", "ctrl+w"}:
            event.stop()
            await self.action_toggle_tips_drawer()
            return
        if event.key == "ctrl+c":
            event.stop()
            self.action_expand_cloud_picker()
            return
        if event.key == "ctrl+m":
            event.stop()
            await self.action_cycle_model()
            return

        if (
            event.key == "enter"
            and "ctrl+m" in event.aliases
            and chat_input.has_focus
            and chat_input.value.strip() == ""
        ):
            event.stop()
            await self.action_cycle_model()
            return
        input_value = chat_input.value.strip()
        slash_visible = "-visible" in self.query_one("#slash-menu", OptionList).classes
        if not (input_value.startswith("/") and slash_visible and self.slash_matches):
            return

        if event.key == "up":
            event.stop()
            self.slash_selected_index = max(0, self.slash_selected_index - 1)
            self._render_slash_menu()
        elif event.key == "down":
            event.stop()
            self.slash_selected_index = min(
                len(self.slash_matches) - 1, self.slash_selected_index + 1
            )
            self._render_slash_menu()

    async def action_toggle_task_output_details(self) -> None:
        if self.last_task_message is None:
            self.notify("No completed task output to toggle yet.")
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        self.task_output_expanded = not self.task_output_expanded
        self.last_task_message.content = app.build_completed_task_result(
            prompt=self.last_task_prompt, expanded=self.task_output_expanded
        )
        await self.sync_from_app_state()

    @on(OptionList.OptionSelected, "#approval-options")
    async def on_approval_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        decision_map = {
            "allow_once": "Yes, allow once",
            "deny": "No",
            "always": "Always",
        }
        app.active_thread.messages.append(
            ChatMessage("assistant", f"Approval decision: **{decision_map[event.option_id]}**.")
        )
        self.approval_visible = False
        await self.sync_from_app_state()
        self.query_one("#chat-input", Input).focus()

    @on(Select.Changed, "#model-picker")
    async def on_model_picker_changed(self, event: Select.Changed[str]) -> None:
        if event.value is Select.BLANK:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        selected_model = event.value
        if selected_model not in app.models:
            return
        previous_index = app.model_index
        app.model_index = app.models.index(selected_model)
        await self.sync_from_app_state(include_tabs=False)
        if app.model_index != previous_index:
            self.notify(f"Model switched to {app.model_name}.")

    @on(Select.Changed, "#cloud-picker")
    async def on_cloud_picker_changed(self, event: Select.Changed[str]) -> None:
        if event.value is Select.BLANK or self._updating_cloud_picker:
            return
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)
        value = event.value
        cloud_picker = self.query_one("#cloud-picker", Select)
        if value == "connect_cloud":
            self.app.push_screen(CloudConnectModalScreen())
            cloud_picker.value = "local"
            return
        if value == "separator":
            cloud_picker.value = "cloud" if app.repo_source == "cloud" else "local"
            return
        if value == "disconnect_cloud":
            cloud_picker.value = "cloud"

            async def _on_disconnect_confirmed(confirmed: bool) -> None:
                if not confirmed:
                    return
                app.cloud_connected = False
                app.set_repo_source("local")
                await self.sync_from_app_state(include_tabs=False)
                self.notify("Disconnected from Cloud.")

            self.app.push_screen(CloudDisconnectConfirmScreen(), _on_disconnect_confirmed)
            return
        if value == "cloud":
            if not app.set_repo_source("cloud"):
                cloud_picker.value = "local"
                self.notify("Connect to Cloud first.")
                return
            await self.sync_from_app_state(include_tabs=False)
            self.notify("Repository source set to cloud.")
            return
        if value == "local":
            if app.set_repo_source("local"):
                await self.sync_from_app_state(include_tabs=False)
                self.notify("Repository source set to local.")

    async def _run_slash_command(self, raw_text: str) -> bool:
        app = self.app
        assert isinstance(app, OpenHandsCLIApp)

        parts = raw_text[1:].strip().split()
        command_name = parts[0].lower() if parts else ""
        command_arg = parts[1].lower() if len(parts) > 1 else ""
        selected_from_menu = False
        if not command_name:
            if self.slash_matches:
                selected = self.slash_matches[
                    max(0, min(self.slash_selected_index, len(self.slash_matches) - 1))
                ]
                command_name = selected.name
                selected_from_menu = True
            else:
                self._render_slash_menu()
                return True

        if command_name in {"$", "credits", "cost"}:
            cost_text = app.format_credit_cost()
            self.notify(f"Current credit cost: {cost_text}")
            app.active_thread.messages.append(
                ChatMessage("assistant", app.build_cost_component())
            )
        elif command_name == "help":
            command_help = "\n".join(
                f"- `/{command.name}` - {command.description}"
                for command in app.slash_commands
            )
            app.active_thread.messages.append(
                ChatMessage("assistant", f"Available slash commands:\n{command_help}")
            )
        elif command_name == "init":
            app.create_thread()
            self.notify("Initialized a new repository context (mock).")
        elif command_name == "status":
            app.active_thread.messages.append(
                ChatMessage(
                    "assistant",
                    "Session status:\n"
                    f"- Repo source: `{app.repo_source}`\n"
                    f"- Model: `{app.model_name}`\n"
                    f"- Threads: `{len(app.threads)}`\n"
                    f"- Todo: `{app.todo_summary()}`",
                )
            )
        elif command_name == "todo":
            app.active_thread.messages.append(
                ChatMessage("assistant", app.build_todo_component())
            )
        elif command_name == "tips":
            self.tips_visible = not self.tips_visible
            state = "shown" if self.tips_visible else "hidden"
            app.active_thread.messages.append(
                ChatMessage("assistant", f"Tips drawer is now **{state}**.")
            )
        elif command_name in {"fly", "hackers", "city"}:
            if command_arg in {"on", "show", "start"}:
                self._set_code_city_scene_enabled(True)
            elif command_arg in {"off", "hide", "stop"}:
                self._set_code_city_scene_enabled(False)
            else:
                self._set_code_city_scene_enabled(not self.code_city_visible)
            state = "running" if self.code_city_visible else "hidden"
            app.active_thread.messages.append(
                ChatMessage(
                    "assistant",
                    "Workspace simulation is now "
                    f"**{state}**.\n\nUse `/fly on`, `/fly off`, or `/fly toggle`.",
                )
            )
        elif command_name in {"board", "kanban", "prs"}:
            if command_arg in {"on", "show", "start"}:
                self._set_kanban_board_enabled(True)
            elif command_arg in {"off", "hide", "stop"}:
                self._set_kanban_board_enabled(False)
            else:
                self._set_kanban_board_enabled(not self.kanban_visible)
            state = "visible" if self.kanban_visible else "hidden"
            app.active_thread.messages.append(
                ChatMessage(
                    "assistant",
                    "PR Kanban board is now "
                    f"**{state}**.\n\nUse `/board on`, `/board off`, or `/board toggle`.",
                )
            )
        elif command_name == "components":
            app.active_thread.messages.append(
                ChatMessage("assistant", app.build_components_gallery())
            )
        elif command_name in {"drawer", "threads"}:
            if selected_from_menu and not command_arg:
                self._show_slash_submenu(
                    command_name="drawer",
                    subtitle="Drawer options",
                    options=[
                        ("show", "Show left conversation drawer"),
                        ("hide", "Hide left conversation drawer"),
                        ("toggle", "Toggle drawer"),
                    ],
                )
                return True
            if command_arg in {"show", "open", "on"}:
                self.drawer_visible = True
            elif command_arg in {"hide", "close", "off"}:
                self.drawer_visible = False
            else:
                self.drawer_visible = not self.drawer_visible
            self._apply_thread_drawer_visibility()
            state = "shown" if self.drawer_visible else "hidden"
            app.active_thread.messages.append(
                ChatMessage(
                    "assistant",
                    f"Conversation drawer is now **{state}**.\n\n"
                    "Usage: `/drawer show`, `/drawer hide`, `/drawer toggle`.",
                )
            )
        elif command_name == "sample":
            app.active_thread.messages.append(
                ChatMessage(
                    "user",
                    "> Enhance get_value in dict_helpers.py to support accessing nested dictionary values using a\n"
                    "dot-separated string for the key (e.g., 'user.address.city'). If any part of the path\n"
                    "doesn't exist, it should return the default value.",
                )
            )
            app.active_thread.messages.append(
                ChatMessage(
                    "assistant",
                    "Agent running...\n\n"
                    "$ rg --files | rg dict_helpers.py\n\n"
                    "I'll help you enhance `get_value` to support dot-separated nested paths.\n"
                    "First, let's locate and inspect the implementation.",
                )
            )
            self.approval_visible = True
            self.query_one("#approval-options", OptionList).highlighted = 0
        elif command_name == "repo":
            if selected_from_menu and not command_arg:
                self._show_slash_submenu(
                    command_name="repo",
                    subtitle="Repository source",
                    options=[
                        ("local", "Set repository source to local"),
                        ("cloud", "Set repository source to cloud"),
                        ("toggle", "Toggle repository source"),
                    ],
                )
                return True
            if command_arg in {"local", "cloud"}:
                changed = app.set_repo_source(command_arg)
                if command_arg == "cloud" and not changed and app.repo_source != "cloud":
                    self.notify("Connect to Cloud before switching to cloud source.")
                else:
                    self.notify(f"Repository source set to {app.repo_source}.")
            else:
                changed = app.cycle_repo_source()
                if changed:
                    self.notify(f"Repository source set to {app.repo_source}.")
                else:
                    self.notify("Connect to Cloud before switching to cloud source.")
        elif command_name == "model":
            if selected_from_menu and not command_arg:
                self._show_slash_submenu(
                    command_name="model",
                    subtitle="Model options",
                    options=[
                        ("gpt", "Use GPT model"),
                        ("claude", "Use Claude model"),
                        ("gemini", "Use Gemini model"),
                        ("toggle", "Cycle to next model"),
                    ],
                )
                return True
            if command_arg in {"gpt", "claude", "gemini"}:
                app.model_index = {"gpt": 0, "claude": 1, "gemini": 2}[command_arg]
            else:
                app.cycle_model()
            self.notify(f"Model switched to {app.model_name}.")
        elif command_name == "new":
            app.create_thread()
            self.notify("Created a new conversation thread.")
        elif command_name == "modal":
            self.app.push_screen(ModalDialogScreen())
        elif command_name == "exit":
            app.exit()
            return True
        else:
            self.notify(f"Unknown command: /{command_name}")
            return True

        await self.sync_from_app_state()
        if self.approval_visible:
            self.query_one("#approval-options", OptionList).focus()
        return True

    def _render_slash_menu(self) -> None:
        option_list = self.query_one("#slash-menu", OptionList)
        option_list.clear_options()

        if not self.slash_matches:
            self._hide_slash_menu()
            return

        for command in self.slash_matches:
            option_list.add_option(
                Option(f"/{command.name} - {command.description}", id=command.name)
            )
        option_list.highlighted = self.slash_selected_index
        option_list.add_class("-visible")

    def _show_slash_menu_no_results(self) -> None:
        option_list = self.query_one("#slash-menu", OptionList)
        option_list.clear_options()
        option_list.add_option(Option("No commands found", id="none"))
        option_list.highlighted = 0
        option_list.add_class("-visible")

    def _hide_slash_menu(self) -> None:
        menu = self.query_one("#slash-menu", OptionList)
        menu.clear_options()
        menu.remove_class("-visible")

    def _show_slash_submenu(
        self, command_name: str, subtitle: str, options: list[tuple[str, str]]
    ) -> None:
        self.slash_submenu_command = command_name
        title = self.query_one("#slash-submenu-title", Static)
        title.update(subtitle)
        title.add_class("-visible")

        option_list = self.query_one("#slash-submenu", OptionList)
        option_list.clear_options()
        for option_id, text in options:
            option_list.add_option(Option(text, id=option_id))
        option_list.highlighted = 0
        option_list.add_class("-visible")

    def _hide_slash_submenu(self) -> None:
        self.slash_submenu_command = None
        title = self.query_one("#slash-submenu-title", Static)
        title.update("")
        title.remove_class("-visible")
        option_list = self.query_one("#slash-submenu", OptionList)
        option_list.clear_options()
        option_list.remove_class("-visible")

    @on(OptionList.OptionSelected, "#slash-menu")
    async def on_slash_menu_selected(self, event: OptionList.OptionSelected) -> None:
        command_name = event.option_id
        if command_name in {None, "none"}:
            return

        if command_name in {"drawer", "threads"}:
            self._show_slash_submenu(
                command_name="drawer",
                subtitle="Drawer options",
                options=[
                    ("show", "Show left conversation drawer"),
                    ("hide", "Hide left conversation drawer"),
                    ("toggle", "Toggle drawer"),
                ],
            )
            return

        if command_name == "repo":
            self._show_slash_submenu(
                command_name="repo",
                subtitle="Repository source",
                options=[
                    ("local", "Set repository source to local"),
                    ("cloud", "Set repository source to cloud"),
                    ("toggle", "Toggle repository source"),
                ],
            )
            return

        if command_name == "model":
            self._show_slash_submenu(
                command_name="model",
                subtitle="Model options",
                options=[
                    ("gpt", "Use GPT model"),
                    ("claude", "Use Claude model"),
                    ("gemini", "Use Gemini model"),
                    ("toggle", "Cycle to next model"),
                ],
            )
            return

        await self._run_slash_command(f"/{command_name}")
        self._hide_slash_menu()
        self.query_one("#chat-input", Input).focus()

    @on(OptionList.OptionSelected, "#slash-submenu")
    async def on_slash_submenu_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None or self.slash_submenu_command is None:
            return
        option_arg = event.option_id
        command_name = self.slash_submenu_command
        if option_arg == "toggle":
            await self._run_slash_command(f"/{command_name}")
        else:
            await self._run_slash_command(f"/{command_name} {option_arg}")
        self._hide_slash_submenu()
        self._hide_slash_menu()
        self.query_one("#chat-input", Input).focus()


class OpenHandsCLIApp(App):
    """Interactive OpenHands CLI prototype with no external dependencies."""

    CSS_PATH = "openhands_cli.tcss"
    TITLE = "OpenHands CLI"

    COMMANDS = App.COMMANDS | {OpenHandsCommandProvider}
    SCREENS = {"startup": OnboardingScreen, "main": MainShellScreen}
    DEFAULT_MODELS = [
        "gpt-4.1",
        "claude-sonnet",
        "gemini-2.5-pro",
        "o3-mini",
        "claude-opus",
        "gpt-4.1-mini",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.repo_sources = ["local", "cloud"]
        self.repo_source_index = 0
        self.cloud_connected = False
        self.branch_name = "feature/kanban-interactive-board"
        self.models = self.DEFAULT_MODELS.copy()
        self.model_index = 0
        self.thread_count = 0
        self.threads = self._build_seed_threads()
        self.active_thread_id = next(iter(self.threads))
        self.onboarding_complete = False
        self.provider_choice: str | None = None
        self.conversation_id: str | None = None
        self.todo_items = self._build_seed_todos()
        self.credit_cost = 0.065

    @property
    def repo_source(self) -> str:
        return self.repo_sources[self.repo_source_index]

    @property
    def cloud_picker_options(self) -> list[tuple[str, str]]:
        if self.cloud_connected:
            return [
                ("Local", "local"),
                ("Cloud", "cloud"),
                ("─" * 40, "separator"),
                ("Disconnect Cloud", "disconnect_cloud"),
            ]
        return [("Local", "local"), ("Connect to Cloud", "connect_cloud")]

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

    @property
    def slash_commands(self) -> list[SlashCommand]:
        return [
            SlashCommand("$", "Show current credit use"),
            SlashCommand("cost", "Display current credit cost"),
            SlashCommand("exit", "Exit the application"),
            SlashCommand("help", "Display available commands"),
            SlashCommand("init", "Initialize a new repository"),
            SlashCommand("status", "Display conversation details and usage metrics"),
            SlashCommand("todo", "Show task list summary"),
            SlashCommand("tips", "Show or hide the tips drawer"),
            SlashCommand("fly", "Toggle 3D code-city fly-through workspace simulation"),
            SlashCommand("board", "Show/hide PR Kanban board linked to conversations"),
            SlashCommand("components", "Show sample conversation components gallery"),
            SlashCommand("drawer", "Show, hide, or toggle the left conversation drawer"),
            SlashCommand("sample", "Show multiline prompt + approval selection sample"),
            SlashCommand("repo", "Switch repository source local/cloud"),
            SlashCommand("model", "Switch active model"),
            SlashCommand("modal", "Show a modal dialog with buttons"),
            SlashCommand("new", "Create a new conversation thread"),
        ]

    def on_mount(self) -> None:
        self.push_screen("startup")

    def show_main_screen(self) -> None:
        if isinstance(self.screen, OnboardingScreen):
            self.pop_screen()
        if not isinstance(self.screen, MainShellScreen):
            self.push_screen("main")

    def complete_onboarding(self) -> None:
        self.onboarding_complete = True
        self.conversation_id = str(uuid4())

    def build_todo_render(self) -> str:
        lines = [
            "Agent Updated Plan",
            f"Task List ({len(self.todo_items)} items)",
            "",
        ]
        for index, item in enumerate(self.todo_items, start=1):
            icon = {
                "done": "✓",
                "in_progress": "⋯",
                "blocked": "x",
                "todo": "□",
            }.get(item.status, "□")
            status_text = item.status.replace("_", " ").upper()
            lines.append(f"{icon} {index}. {status_text}")
            lines.append(item.title)
            if item.reason:
                lines.append(f"Reason: {item.reason}")
            lines.append(f"ID: {item.todo_id}")
            if index < len(self.todo_items):
                lines.append("")
        return "\n".join(lines)

    def build_todo_component(self) -> str:
        return f"```text\n{self.build_todo_render()}\n```"

    def todo_summary(self) -> str:
        totals = {"done": 0, "in_progress": 0, "blocked": 0, "todo": 0}
        for item in self.todo_items:
            totals[item.status] = totals.get(item.status, 0) + 1
        return (
            f"{totals['done']} done, "
            f"{totals['in_progress']} in progress, "
            f"{totals['blocked']} blocked, "
            f"{totals['todo']} todo"
        )

    def advance_todo_progress(self) -> None:
        for item in self.todo_items:
            if item.status == "in_progress":
                item.status = "done"
                break
        for item in self.todo_items:
            if item.status == "todo":
                item.status = "in_progress"
                break

    def increment_credit_cost(self, prompt: str) -> None:
        # Lightweight mock cost model to make the UI feel alive.
        self.credit_cost += 0.006 + min(len(prompt), 180) * 0.00003

    def format_credit_cost(self) -> str:
        return f"${self.credit_cost:.3f}"

    def build_cost_component(self) -> str:
        return f"```text\nCurrent Credit Cost: {self.format_credit_cost()}\n```"

    def build_components_gallery(self) -> str:
        return (
            "### Conversation Components Gallery\n\n"
            "**Task (collapsed)**\n"
            "```text\n"
            "Read author-sidebar.module.css\n"
            "(Ctrl-S to show details)\n"
            "```\n\n"
            "**Task (expanded output)**\n"
            "```text\n"
            "$ cat -n src/components/author-sidebar/author-sidebar.module.css\n"
            "1 .sidebar { width: 300px; }\n"
            "2 .avatar { width: 70px; }\n"
            "...\n"
            "(esc to cancel • 32s, Ctrl-S to hide details)\n"
            "```\n\n"
            "**Approval Prompt**\n"
            "```text\n"
            "Proceed with action?\n"
            "1. Yes, allow once\n"
            "2. No\n"
            "3. Always\n"
            "```\n\n"
            "**Plan / Todo Object**\n"
            f"{self.build_todo_component()}\n\n"
            "**Cost Object**\n"
            f"{self.build_cost_component()}\n\n"
            "**Process Object**\n"
            "```text\n"
            "Agent running...\n"
            "Step 1/3 scan files → Step 2/3 refactor → Step 3/3 verify tests\n"
            "Status: in progress\n"
            "```"
        )

    def set_active_thread(self, thread_id: str) -> None:
        if thread_id in self.threads:
            self.active_thread_id = thread_id

    def cycle_repo_source(self) -> bool:
        target = "cloud" if self.repo_source == "local" else "local"
        return self.set_repo_source(target)

    def set_repo_source(self, source: str) -> bool:
        """Set the repo source. Returns True on success, False if cloud is not connected."""
        if source == "cloud" and not self.cloud_connected:
            self.repo_source_index = 0
            return False
        self.repo_source_index = 0 if source == "local" else 1
        return True

    def cycle_model(self) -> None:
        self.model_index = (self.model_index + 1) % len(self.models)

    def create_thread(self) -> None:
        self.thread_count += 1
        thread_id = f"thread-{self.thread_count + len(self.threads)}"
        title = "New Session"
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

    def build_processing_preview(self, prompt: str) -> str:
        target = self._get_lookup_target(prompt)
        return (
            f"Now let me look at the **{target}** component:\n\n"
            f"┌ Read `{target}` ⋮\n\n"
            "(esc to cancel • 3s, Ctrl-S to show details)"
        )

    def build_completed_task_result(self, prompt: str, expanded: bool) -> str:
        target = self._get_lookup_target(prompt)
        path = self._get_lookup_path(target)
        header = (
            f"Now let me look at the **{target}** component:\n\n"
            f"┌ Read `{target}` ⋮\n\n"
            f"Here's the result of running `cat -n` on\n`{path}`:"
        )

        if not expanded:
            return f"{header}\n\n(Ctrl-S to show details)"

        output = (
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
            "```"
        )
        return f"{header}\n\n{output}\n\n(esc to cancel • 32s, Ctrl-S to hide details)"

    def _get_lookup_target(self, prompt: str) -> str:
        at_path = re.search(r"@([\w./-]+)", prompt)
        if at_path:
            return at_path.group(1)

        file_like = re.search(r"([\w./-]+\.(?:py|ts|tsx|js|jsx|css|tcss|md))", prompt)
        if file_like:
            return file_like.group(1)

        component = re.search(r"([a-zA-Z0-9_-]+(?:\\s+[a-zA-Z0-9_-]+){0,2})", prompt.strip())
        if component:
            return component.group(1).replace(" ", "-")

        return "project-files"

    def _get_lookup_path(self, target: str) -> str:
        if "/" in target:
            return f"/workspace/project/{target}"
        return f"/workspace/project/seedit/src/components/{target.replace('.module.css', '')}/{target}"

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
            if not isinstance(self.screen, OnboardingScreen):
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

    def _build_seed_todos(self) -> list[TodoItem]:
        return [
            TodoItem(
                title="Convert search bar form, dropdown, infobar with animations and responsive behavior",
                todo_id="convert_search_bar",
                status="done",
            ),
            TodoItem(
                title="Convert small components (tooltip, feed-toggle, error-display, sticky-header, flair, label)",
                todo_id="convert_small_components",
                status="in_progress",
            ),
            TodoItem(
                title="Convert reply form with textarea, buttons, markdown help table, options",
                todo_id="convert_reply_form",
                status="blocked",
                reason="dependency on markdown lib upgrade",
            ),
            TodoItem(
                title="Convert complex markdown rendering with nested selectors using Tailwind classes",
                todo_id="convert_markdown_rendering",
                status="todo",
            ),
        ]


if __name__ == "__main__":
    app = OpenHandsCLIApp()
    app.run(inline=False, mouse=True)
