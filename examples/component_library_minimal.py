"""Textual Component Library — Minimal Edition.

Same interactive showcase as component_library.py but with a deliberately
minimalist, monochromatic aesthetic: outlined ghost buttons, no colour fills,
sparse spacing, and a stripped-back sidebar.

Run:
    python examples/component_library_minimal.py
"""

from __future__ import annotations

import json
from pathlib import Path
from time import monotonic

from rich.text import Text

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.color import Color
from textual.containers import (
    Container,
    Grid,
    Horizontal,
    ScrollableContainer,
    Vertical,
    VerticalScroll,
)
from textual.css.query import DOMQuery
from textual.reactive import reactive, var
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Collapsible,
    ContentSwitcher,
    DataTable,
    Digits,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Markdown,
    MarkdownViewer,
    OptionList,
    Placeholder,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Select,
    SelectionList,
    Static,
    Switch,
    Tab,
    TabbedContent,
    TabPane,
    TextArea,
    Tree,
)
from textual.widgets._masked_input import MaskedInput
from textual.widgets._toggle_button import ToggleButton
from textual.widgets.option_list import Option
from textual.widgets.selection_list import Selection
from textual.widgets.text_area import Selection as TextSelection

# ---------------------------------------------------------------------------
# Shared sample data
# ---------------------------------------------------------------------------

_SWIM_HEADERS = ("Lane", "Swimmer", "Country", "Time")
_SWIM_ROWS = [
    (4, "Joseph Schooling", "Singapore", 50.39),
    (2, "Michael Phelps", "United States", 51.14),
    (5, "Chad le Clos", "South Africa", 51.14),
    (6, "László Cseh", "Hungary", 51.14),
    (3, "Li Zhuhao", "China", 51.26),
    (8, "Mehdy Metella", "France", 51.58),
    (7, "Tom Shields", "United States", 51.73),
    (1, "Aleksandr Sadovnikov", "Russia", 51.84),
]

_SAMPLE_MARKDOWN = """\
# Markdown Support

Textual renders GitHub-flavoured Markdown natively.

## Typography

Regular paragraph with *italic*, **bold**, `inline code`, and ~~strikethrough~~.

## Lists

- Bullet item one
- Bullet item two
    - Nested item

1. Ordered item one
2. Ordered item two

## Code Block

```python
from textual.app import App
app = App()
app.run()
```

## Table

| Widget | Category | Interactive |
|--------|----------|-------------|
| Button | Action   | ✓           |
| Input  | Form     | ✓           |
| Label  | Display  | —           |
"""

_SAMPLE_JSON = {
    "name": "Textual Component Library",
    "version": "1.0.0",
    "widgets": {
        "display": ["Label", "Static", "Digits", "Markdown"],
        "input": ["Button", "Input", "TextArea", "Select"],
        "layout": ["Horizontal", "Vertical", "Grid", "Container"],
    },
    "themes": ["textual-dark", "textual-light", "dracula", "nord", "tokyo-night"],
}


# ---------------------------------------------------------------------------
# Section: Section header helper
# ---------------------------------------------------------------------------


class SectionTitle(Static):
    """A decorative section heading inside a panel."""

    DEFAULT_CSS = """
    SectionTitle {
        color: $text;
        text-style: bold;
        padding: 0 0;
        margin-top: 1;
        margin-bottom: 0;
    }
    """


class SectionDivider(Static):
    """A thin horizontal rule used between sub-sections."""

    DEFAULT_CSS = """
    SectionDivider {
        height: 1;
        border-bottom: solid $panel;
        margin: 1 0;
    }
    """


class CodeHint(Static):
    """Displays an inline code hint below a demo."""

    DEFAULT_CSS = """
    CodeHint {
        color: $text-disabled;
        padding: 0 0;
        margin-bottom: 1;
    }
    """


# ---------------------------------------------------------------------------
# Section panels
# ---------------------------------------------------------------------------


class ButtonsPanel(VerticalScroll):
    """Demonstrates all Button variants and states."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Buttons")
        yield CodeHint("Button(label, variant='default|primary|success|warning|error')")

        with Horizontal(id="btn-variants"):
            yield Button("Default")
            yield Button("Primary", variant="primary")
            yield Button("Success", variant="success")
            yield Button("Warning", variant="warning")
            yield Button("Error", variant="error")

        yield SectionDivider()
        yield SectionTitle("Disabled & Reactive State")
        with Horizontal(id="btn-states"):
            yield Button("Enabled", id="btn-enabled", variant="primary")
            yield Button("Disabled", id="btn-disabled", variant="primary", disabled=True)
            yield Button("Toggle Me", id="btn-toggle", variant="warning")

        yield SectionDivider()
        yield SectionTitle("Action Counter")
        yield Label("Presses: 0", id="press-counter")
        with Horizontal(id="btn-counter-row"):
            yield Button("Increment", id="btn-inc", variant="success")
            yield Button("Decrement", id="btn-dec", variant="error")
            yield Button("Reset", id="btn-reset")

    _count: reactive[int] = reactive(0)

    def watch__count(self, value: int) -> None:
        self.query_one("#press-counter", Label).update(f"Presses: {value}")

    @on(Button.Pressed, "#btn-inc")
    def on_increment(self) -> None:
        self._count += 1

    @on(Button.Pressed, "#btn-dec")
    def on_decrement(self) -> None:
        self._count -= 1

    @on(Button.Pressed, "#btn-reset")
    def on_reset(self) -> None:
        self._count = 0

    @on(Button.Pressed, "#btn-toggle")
    def on_toggle(self) -> None:
        btn = self.query_one("#btn-disabled", Button)
        btn.disabled = not btn.disabled
        btn.label = "Enabled!" if not btn.disabled else "Disabled"


class InputsPanel(VerticalScroll):
    """Demonstrates Input, MaskedInput, and TextArea."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Text Input")
        yield CodeHint("Input(placeholder='...', password=False)")

        yield Input(placeholder="Plain text input", id="plain-input")
        yield Input(placeholder="Password input", password=True, id="pw-input")
        yield Label("", id="input-echo")

        yield SectionDivider()
        yield SectionTitle("Masked Input")
        yield CodeHint("MaskedInput(template='9999-9999-9999-9999')")
        yield MaskedInput(template="9999-9999-9999-9999;_", id="masked-input")

        yield SectionDivider()
        yield SectionTitle("Text Area")
        yield CodeHint("TextArea(text)  — add language='python' after: pip install tree-sitter-python")
        yield TextArea(
            "# Edit this Python code\nfor i in range(10):\n    print(i)\n",
            id="code-area",
        )

        yield SectionDivider()
        yield SectionTitle("Input Validation Echo")
        yield Input(placeholder="Type something and press Enter…", id="echo-input")
        yield Static("", id="echo-output")

    @on(Input.Submitted, "#echo-input")
    def on_echo_submit(self, event: Input.Submitted) -> None:
        self.query_one("#echo-output", Static).update(
            f"[bold $success]Submitted:[/] {event.value}"
        )

    @on(Input.Changed, "#plain-input")
    def on_plain_changed(self, event: Input.Changed) -> None:
        self.query_one("#input-echo", Label).update(f"Live: {event.value!r}")


class SelectionPanel(VerticalScroll):
    """Demonstrates Select, OptionList, RadioSet, and SelectionList."""

    _FRUITS = ["Apple", "Banana", "Cherry", "Date", "Elderberry", "Fig", "Grape"]
    _LANGS = [
        ("Python", "python"),
        ("Rust", "rust"),
        ("TypeScript", "ts"),
        ("Go", "go"),
        ("Zig", "zig"),
    ]

    def compose(self) -> ComposeResult:
        yield SectionTitle("Select Dropdown")
        yield CodeHint("Select(options, prompt='...')")
        yield Select(
            [(fruit, fruit) for fruit in self._FRUITS],
            prompt="Pick a fruit",
            id="fruit-select",
        )
        yield Label("Selected: —", id="fruit-label")

        yield SectionDivider()
        yield SectionTitle("Option List")
        yield CodeHint("OptionList(*options)  — keyboard-navigable list")
        yield OptionList(
            *[Option(lang, id=key) for lang, key in self._LANGS],
            id="lang-option-list",
        )
        yield Label("Highlighted: —", id="option-label")

        yield SectionDivider()
        yield SectionTitle("Radio Set")
        yield CodeHint("RadioSet(*RadioButton('label'))")
        with RadioSet(id="theme-radio"):
            yield RadioButton("Dark", value=True)
            yield RadioButton("Light")
            yield RadioButton("High-contrast")

        yield SectionDivider()
        yield SectionTitle("Selection List  (multi-select)")
        yield CodeHint("SelectionList(*Selection('label', value, initial))")
        yield SelectionList(
            Selection("Notifications", "notif", True),
            Selection("Auto-save", "autosave", True),
            Selection("Spell-check", "spell", False),
            Selection("Telemetry", "telemetry", False),
            id="pref-list",
        )
        yield Button("Show selections", id="show-sel-btn", variant="primary")
        yield Static("", id="sel-output")

    @on(Select.Changed, "#fruit-select")
    def on_fruit(self, event: Select.Changed) -> None:
        self.query_one("#fruit-label", Label).update(f"Selected: {event.value}")

    @on(OptionList.OptionHighlighted, "#lang-option-list")
    def on_option(self, event: OptionList.OptionHighlighted) -> None:
        self.query_one("#option-label", Label).update(
            f"Highlighted: {event.option.prompt}"
        )

    @on(Button.Pressed, "#show-sel-btn")
    def on_show_sel(self) -> None:
        sel_list = self.query_one("#pref-list", SelectionList)
        selected = sel_list.selected
        self.query_one("#sel-output", Static).update(
            f"[bold]Enabled:[/] {', '.join(str(s) for s in selected) or 'none'}"
        )


class ListsPanel(VerticalScroll):
    """Demonstrates ListView and Tree."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("List View")
        yield CodeHint("ListView(*ListItem(Label('...')))")
        yield ListView(
            ListItem(Label("Home")),
            ListItem(Label("Files")),
            ListItem(Label("Search")),
            ListItem(Label("Settings")),
            ListItem(Label("Help")),
            id="nav-list",
        )
        yield Label("Clicked: —", id="list-label")

        yield SectionDivider()
        yield SectionTitle("Tree")
        yield CodeHint("Tree('root')  — expandable nodes with leaf detection")
        yield self._build_tree()

    def _build_tree(self) -> Tree:
        tree: Tree[dict] = Tree("Component Library")
        tree.root.expand()

        display = tree.root.add("Display", expand=True)
        display.add_leaf("Label")
        display.add_leaf("Static")
        display.add_leaf("Digits")
        display.add_leaf("Markdown")

        forms = tree.root.add("Forms", expand=True)
        forms.add_leaf("Button")
        forms.add_leaf("Input / TextArea")
        forms.add_leaf("Select / OptionList")
        forms.add_leaf("RadioSet / SelectionList")
        forms.add_leaf("Switch / ToggleButton")

        layout = tree.root.add("Layout")
        layout.add_leaf("Horizontal / Vertical")
        layout.add_leaf("Grid")
        layout.add_leaf("Container")
        layout.add_leaf("VerticalScroll")

        data = tree.root.add("Data")
        data.add_leaf("DataTable")
        data.add_leaf("RichLog")
        data.add_leaf("MarkdownViewer")
        data.add_leaf("DirectoryTree")

        return tree

    @on(ListView.Selected, "#nav-list")
    def on_list_selected(self, event: ListView.Selected) -> None:
        label = event.item.query_one(Label)
        self.query_one("#list-label", Label).update(f"Clicked: {label.renderable}")


class DataPanel(VerticalScroll):
    """Demonstrates DataTable and RichLog."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Data Table")
        yield CodeHint("DataTable(zebra_stripes=True, cursor_type='row')")
        yield self._build_table()

        yield SectionDivider()
        yield SectionTitle("Rich Log")
        yield CodeHint("RichLog(highlight=True, markup=True)  — live streaming log")
        yield RichLog(highlight=True, markup=True, id="rich-log", max_lines=200)
        with Horizontal(id="log-buttons"):
            yield Button("Append line", id="log-append", variant="primary")
            yield Button("Log warning", id="log-warn", variant="warning")
            yield Button("Log error", id="log-error", variant="error")
            yield Button("Clear", id="log-clear")

    def _build_table(self) -> DataTable:
        table: DataTable = DataTable(zebra_stripes=True, cursor_type="row", id="swim-table")
        return table

    def on_mount(self) -> None:
        table = self.query_one("#swim-table", DataTable)
        table.add_columns(*_SWIM_HEADERS)
        for row in _SWIM_ROWS:
            table.add_row(*row)

        log = self.query_one("#rich-log", RichLog)
        log.write("[bold $primary]RichLog initialised.[/] Click buttons to append.")

    _log_count: int = 0

    @on(Button.Pressed, "#log-append")
    def on_log_append(self) -> None:
        self._log_count += 1
        log = self.query_one("#rich-log", RichLog)
        log.write(f"[dim]{self._log_count:04d}[/]  Regular log line — {monotonic():.3f}s")

    @on(Button.Pressed, "#log-warn")
    def on_log_warn(self) -> None:
        log = self.query_one("#rich-log", RichLog)
        log.write("[bold $warning]⚠  WARNING:[/]  Something needs your attention.")

    @on(Button.Pressed, "#log-error")
    def on_log_error(self) -> None:
        log = self.query_one("#rich-log", RichLog)
        log.write("[bold $error]✗  ERROR:[/]  Something went wrong.")

    @on(Button.Pressed, "#log-clear")
    def on_log_clear(self) -> None:
        self.query_one("#rich-log", RichLog).clear()


class ProgressPanel(VerticalScroll):
    """Demonstrates ProgressBar, Switch, and ToggleButton."""

    _progress: reactive[float] = reactive(0.0)
    _running: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield SectionTitle("Progress Bar")
        yield CodeHint("ProgressBar(total=100, show_eta=True, show_percentage=True)")
        yield ProgressBar(total=100, show_eta=True, id="demo-progress")
        with Horizontal(id="progress-btns"):
            yield Button("Start", id="prog-start", variant="success")
            yield Button("Pause", id="prog-pause", variant="warning")
            yield Button("Reset", id="prog-reset", variant="error")

        yield SectionDivider()
        yield SectionTitle("Loading Indicator")
        yield CodeHint("LoadingIndicator()  — shown when waiting for async work")
        yield LoadingIndicator(id="demo-loader")
        yield Switch(value=True, id="loader-toggle")
        yield CodeHint("← Toggle to hide/show the loader")

        yield SectionDivider()
        yield SectionTitle("Switch  &  ToggleButton")
        yield CodeHint("Switch(value=True/False)  —  ToggleButton('label', value=True/False)")
        with Horizontal(id="toggle-row"):
            with Vertical(classes="toggle-col"):
                yield Label("Notifications")
                yield Switch(value=True, id="sw-notif")
            with Vertical(classes="toggle-col"):
                yield Label("Dark mode")
                yield Switch(value=False, id="sw-dark")
            with Vertical(classes="toggle-col"):
                yield Label("Auto-save")
                yield Switch(value=True, id="sw-save")

        yield SectionDivider()
        yield ToggleButton("Toggle me", id="demo-toggle")
        yield Label("Toggle value: True", id="toggle-label")

    def on_mount(self) -> None:
        self.set_interval(0.1, self._tick)

    def _tick(self) -> None:
        if self._running and self._progress < 100:
            self._progress = min(self._progress + 0.5, 100)
            self.query_one("#demo-progress", ProgressBar).advance(0.5)

    @on(Button.Pressed, "#prog-start")
    def on_start(self) -> None:
        self._running = True

    @on(Button.Pressed, "#prog-pause")
    def on_pause(self) -> None:
        self._running = False

    @on(Button.Pressed, "#prog-reset")
    def on_reset_prog(self) -> None:
        self._running = False
        self._progress = 0.0
        self.query_one("#demo-progress", ProgressBar).update(progress=0)

    @on(Switch.Changed, "#loader-toggle")
    def on_loader_toggle(self, event: Switch.Changed) -> None:
        self.query_one("#demo-loader", LoadingIndicator).display = event.value

    def on_toggle_button_changed(self, event: ToggleButton.Changed) -> None:
        if event.toggle_button.id == "demo-toggle":
            self.query_one("#toggle-label", Label).update(
                f"Toggle value: {event.toggle_button.value}"
            )


class ContentPanel(VerticalScroll):
    """Demonstrates Label variants, Collapsible, Markdown, and MarkdownViewer."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Label Variants")
        yield CodeHint("Label('text')  — styled via CSS classes or markup")
        with Horizontal(id="label-row"):
            yield Label("Default")
            yield Label("[bold]Bold[/bold]")
            yield Label("[italic]Italic[/italic]")
            yield Label("[bold $primary]Primary[/]")
            yield Label("[bold $success]Success[/]")
            yield Label("[bold $warning]Warning[/]")
            yield Label("[bold $error]Error[/]")

        yield SectionDivider()
        yield SectionTitle("Collapsible")
        yield CodeHint("Collapsible(title='...', collapsed=True/False)")
        with Collapsible(title="What is Textual?", collapsed=False):
            yield Label(
                "Textual is a Rapid Application Development framework for Python, "
                "built by Textualize. Build beautiful, interactive applications that "
                "run in the terminal — and beyond."
            )
        with Collapsible(title="Why use Textual?"):
            yield Label(
                "• Write apps in pure Python\n"
                "• CSS-like styling system\n"
                "• Rich ecosystem of widgets\n"
                "• Works in terminal, web, and desktop"
            )
        with Collapsible(title="Installation"):
            yield Static("[bold]pip install textual[/bold]", id="install-hint")

        yield SectionDivider()
        yield SectionTitle("Markdown Inline Renderer")
        yield CodeHint("Markdown(markdown_str)  — renders Markdown with Rich")
        yield Markdown(_SAMPLE_MARKDOWN, id="demo-markdown")


class TabbedPanel(VerticalScroll):
    """Demonstrates Tabs, TabbedContent, and ContentSwitcher."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Tabbed Content")
        yield CodeHint("TabbedContent(*TabPane('title', id='...'))  — lazy panel switching")
        with TabbedContent(id="demo-tabs"):
            with TabPane("Overview", id="tab-overview"):
                yield Markdown(
                    "## Overview\n\nThis tab uses `TabbedContent` with `TabPane` children.\n\n"
                    "Each pane is lazy-rendered and fully scrollable."
                )
            with TabPane("Data", id="tab-data"):
                table: DataTable = DataTable(zebra_stripes=True, id="tab-table")
                yield table
            with TabPane("Code", id="tab-code"):
                yield TextArea(
                    "# Tab 3: Code Editor\nprint('Hello from TabbedContent!')\n",
                )
            with TabPane("Log", id="tab-log"):
                yield RichLog(highlight=True, markup=True, id="tab-log-widget")

        yield SectionDivider()
        yield SectionTitle("Content Switcher (no tabs)")
        yield CodeHint("ContentSwitcher(*panels)  — programmatic switching")
        with Horizontal(id="switcher-nav"):
            yield Button("Panel A", id="sw-a", variant="primary")
            yield Button("Panel B", id="sw-b")
            yield Button("Panel C", id="sw-c")
        with ContentSwitcher(initial="panel-a", id="demo-switcher"):
            yield Static(
                "[bold $primary]Panel A[/]\n\nI am the first content panel.",
                id="panel-a",
            )
            yield Static(
                "[bold $success]Panel B[/]\n\nI am the second content panel.",
                id="panel-b",
            )
            yield Static(
                "[bold $warning]Panel C[/]\n\nI am the third content panel.",
                id="panel-c",
            )

    def on_mount(self) -> None:
        table = self.query_one("#tab-table", DataTable)
        table.add_columns(*_SWIM_HEADERS)
        for row in _SWIM_ROWS:
            table.add_row(*row)

        log = self.query_one("#tab-log-widget", RichLog)
        log.write("[bold]RichLog[/] inside TabbedContent — works seamlessly!")

    @on(Button.Pressed, "#sw-a")
    def show_a(self) -> None:
        self.query_one("#demo-switcher", ContentSwitcher).current = "panel-a"

    @on(Button.Pressed, "#sw-b")
    def show_b(self) -> None:
        self.query_one("#demo-switcher", ContentSwitcher).current = "panel-b"

    @on(Button.Pressed, "#sw-c")
    def show_c(self) -> None:
        self.query_one("#demo-switcher", ContentSwitcher).current = "panel-c"


class LayoutPanel(VerticalScroll):
    """Demonstrates Grid, Horizontal, and Vertical layout containers."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Grid Layout")
        yield CodeHint("Grid  — CSS: layout: grid; grid-size: 3; grid-gutter: 1;")
        yield Static("grid-size: 3, equal columns", id="grid-hint")
        with Grid(id="demo-grid-3"):
            for i in range(1, 10):
                yield Static(f"Cell {i}", classes="grid-cell")

        yield SectionDivider()
        yield SectionTitle("Grid — Asymmetric Columns")
        yield CodeHint("CSS: grid-columns: 1fr 2fr 1fr;")
        with Grid(id="demo-grid-asymm"):
            yield Static("1fr", classes="grid-cell accent")
            yield Static("2fr  (wider)", classes="grid-cell success")
            yield Static("1fr", classes="grid-cell accent")

        yield SectionDivider()
        yield SectionTitle("Horizontal & Vertical Containers")
        yield CodeHint("Horizontal / Vertical — flex-like stack layout")
        with Horizontal(id="hv-demo"):
            with Vertical(id="v-col-1"):
                yield Static("Col 1 — top", classes="layout-box")
                yield Static("Col 1 — bottom", classes="layout-box")
            with Vertical(id="v-col-2"):
                yield Static("Col 2 — top", classes="layout-box")
                yield Static("Col 2 — middle", classes="layout-box")
                yield Static("Col 2 — bottom", classes="layout-box")

        yield SectionDivider()
        yield SectionTitle("Placeholder")
        yield CodeHint("Placeholder(label='...', variant='text|size|...')  — for prototyping")
        with Horizontal(id="placeholder-row"):
            yield Placeholder("Header area", variant="text")
            yield Placeholder("Content area", variant="size")
            yield Placeholder("Sidebar", variant="text")


class DigitsPanel(VerticalScroll):
    """Demonstrates Digits (clock) and reactive updates."""

    _time_str: reactive[str] = reactive("00:00:00")

    def compose(self) -> ComposeResult:
        yield SectionTitle("Digits Widget  (live clock)")
        yield CodeHint("Digits(value)  — large seven-segment display; update via widget.update()")
        yield Digits("00:00:00", id="clock-digits")

        yield SectionDivider()
        yield SectionTitle("Counter  (reactive var → Digits)")
        yield CodeHint("reactive[int] + watch_* to push changes into Digits.update()")
        yield Digits("0", id="counter-digits")
        with Horizontal(id="counter-btns"):
            yield Button("−10", id="cnt-minus10", variant="error")
            yield Button("−1", id="cnt-minus", variant="error")
            yield Button("Reset", id="cnt-reset")
            yield Button("+1", id="cnt-plus", variant="success")
            yield Button("+10", id="cnt-plus10", variant="success")

    _counter: reactive[int] = reactive(0)

    def on_mount(self) -> None:
        import time as _time
        self.set_interval(1, self._tick_clock)

    def _tick_clock(self) -> None:
        import time as _time
        self.query_one("#clock-digits", Digits).update(
            _time.strftime("%H:%M:%S")
        )

    def watch__counter(self, value: int) -> None:
        self.query_one("#counter-digits", Digits).update(str(value))

    @on(Button.Pressed, "#cnt-plus")
    def _plus(self) -> None:
        self._counter += 1

    @on(Button.Pressed, "#cnt-plus10")
    def _plus10(self) -> None:
        self._counter += 10

    @on(Button.Pressed, "#cnt-minus")
    def _minus(self) -> None:
        self._counter -= 1

    @on(Button.Pressed, "#cnt-minus10")
    def _minus10(self) -> None:
        self._counter -= 10

    @on(Button.Pressed, "#cnt-reset")
    def _reset_cnt(self) -> None:
        self._counter = 0


class WorkersPanel(VerticalScroll):
    """Demonstrates @work workers — background tasks and threading."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Async Worker  (@work)")
        yield CodeHint("@work async  — runs on Textual's event loop, non-blocking UI")
        yield Button("Run async task (3s)", id="async-btn", variant="primary")
        yield ProgressBar(total=100, show_eta=False, id="async-prog")
        yield Static("Status: idle", id="async-status")

        yield SectionDivider()
        yield SectionTitle("Thread Worker  (@work(thread=True))")
        yield CodeHint("@work(thread=True)  — runs in a thread; use call_from_thread() to update UI")
        yield Button("Run thread task (2s)", id="thread-btn", variant="warning")
        yield RichLog(highlight=True, markup=True, id="thread-log", max_lines=30)

        yield SectionDivider()
        yield SectionTitle("Exclusive Worker  (@work(exclusive=True))")
        yield CodeHint("@work(exclusive=True)  — cancels previous run if triggered again")
        yield Input(placeholder="Type to trigger exclusive worker…", id="exclusive-input")
        yield Static("Result: —", id="exclusive-result")

    @on(Button.Pressed, "#async-btn")
    def on_async_btn(self) -> None:
        self._run_async_task()

    @work
    async def _run_async_task(self) -> None:
        import asyncio
        prog = self.query_one("#async-prog", ProgressBar)
        status = self.query_one("#async-status", Static)
        prog.update(progress=0)
        status.update("[bold $primary]Status:[/] running…")
        for i in range(1, 21):
            await asyncio.sleep(0.15)
            prog.advance(5)
        status.update("[bold $success]Status:[/] done ✓")

    @on(Button.Pressed, "#thread-btn")
    def on_thread_btn(self) -> None:
        self._run_thread_task()

    @work(thread=True)
    def _run_thread_task(self) -> None:
        import time as _time
        log = self.query_one("#thread-log", RichLog)
        self.call_from_thread(log.write, "[bold]Thread started[/]")
        for i in range(5):
            _time.sleep(0.4)
            self.call_from_thread(
                log.write, f"  step {i + 1}/5 — [dim]{_time.strftime('%H:%M:%S')}[/]"
            )
        self.call_from_thread(log.write, "[bold $success]Thread finished ✓[/]")

    @on(Input.Changed, "#exclusive-input")
    def on_exclusive_input(self, event: Input.Changed) -> None:
        self._exclusive_search(event.value)

    @work(exclusive=True)
    async def _exclusive_search(self, query: str) -> None:
        import asyncio
        await asyncio.sleep(0.4)  # debounce
        result = self.query_one("#exclusive-result", Static)
        result.update(
            f"Result: processed [bold]{query!r}[/bold]" if query else "Result: —"
        )


class ModalPanel(VerticalScroll):
    """Demonstrates ModalScreen and typed dismiss()."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Modal Screens")
        yield CodeHint("app.push_screen(modal, callback)  — suspends parent; returns value")

        yield Button("Open info modal", id="modal-info-btn", variant="primary")
        yield Button("Open confirm modal", id="modal-confirm-btn", variant="warning")
        yield Button("Open form modal", id="modal-form-btn", variant="success")
        yield Static("", id="modal-result")

        yield SectionDivider()
        yield SectionTitle("Notifications (app.notify)")
        yield CodeHint("app.notify(message, title='...', severity='information|warning|error')")
        with Horizontal(id="notify-btns"):
            yield Button("Info", id="notif-info", variant="primary")
            yield Button("Warning", id="notif-warn", variant="warning")
            yield Button("Error", id="notif-error", variant="error")

    @on(Button.Pressed, "#modal-info-btn")
    def open_info(self) -> None:
        self.app.push_screen(InfoModal(), self._on_modal_closed)

    @on(Button.Pressed, "#modal-confirm-btn")
    def open_confirm(self) -> None:
        self.app.push_screen(ConfirmModal(), self._on_confirm)

    @on(Button.Pressed, "#modal-form-btn")
    def open_form(self) -> None:
        self.app.push_screen(FormModal(), self._on_form_result)

    def _on_modal_closed(self, result: str | None) -> None:
        if result:
            self.query_one("#modal-result", Static).update(f"Modal said: {result!r}")

    def _on_confirm(self, confirmed: bool) -> None:
        msg = "[bold $success]Confirmed ✓[/]" if confirmed else "[bold $error]Cancelled ✗[/]"
        self.query_one("#modal-result", Static).update(msg)

    def _on_form_result(self, value: str | None) -> None:
        if value is not None:
            self.query_one("#modal-result", Static).update(f"Form returned: {value!r}")
        else:
            self.query_one("#modal-result", Static).update("Form: dismissed without value")

    @on(Button.Pressed, "#notif-info")
    def notify_info(self) -> None:
        self.app.notify("This is an informational notification.", title="Info")

    @on(Button.Pressed, "#notif-warn")
    def notify_warn(self) -> None:
        self.app.notify(
            "Something needs your attention.", title="Warning", severity="warning"
        )

    @on(Button.Pressed, "#notif-error")
    def notify_error(self) -> None:
        self.app.notify("A critical error occurred!", title="Error", severity="error")


class ThemePanel(VerticalScroll):
    """Demonstrates the design token palette and theme switching."""

    def compose(self) -> ComposeResult:
        yield SectionTitle("Design Token Palette")
        yield CodeHint("All $-variables available in TCSS — changes with app.theme")

        token_pairs = [
            ("$primary", "$primary-muted"),
            ("$secondary", "$secondary-muted"),
            ("$accent", "$accent-muted"),
            ("$success", "$success-muted"),
            ("$warning", "$warning-muted"),
            ("$error", "$error-muted"),
        ]
        for token, muted in token_pairs:
            with Horizontal(classes="token-row"):
                yield Static(token, classes=f"token-swatch swatch-{token[1:]}")
                yield Static(muted, classes=f"token-swatch swatch-{muted[1:]}")

        yield SectionDivider()
        yield SectionTitle("Surface / Panel / Background")
        with Horizontal(classes="token-row"):
            yield Static("$surface", classes="token-swatch swatch-surface")
            yield Static("$panel", classes="token-swatch swatch-panel")
            yield Static("$background", classes="token-swatch swatch-background")

        yield SectionDivider()
        yield SectionTitle("Text Tokens")
        with Horizontal(classes="token-row"):
            yield Static("[bold]$text[/]", classes="token-swatch swatch-text")
            yield Static("[dim]$text-muted[/]", classes="token-swatch swatch-text-muted")
            yield Static("[dim]$text-disabled[/]", classes="token-swatch swatch-text-disabled")

        yield SectionDivider()
        yield SectionTitle("Theme Switcher")
        yield CodeHint("app.theme = 'theme-name'  — live-swap the entire design system")
        yield OptionList(
            *[Option(name, id=name) for name in []],
            id="theme-picker",
        )

    def on_mount(self) -> None:
        picker = self.query_one("#theme-picker", OptionList)
        picker.clear_options()
        for name in self.app.available_themes:
            picker.add_option(Option(name, id=name))

    @on(OptionList.OptionSelected, "#theme-picker")
    def on_theme_selected(self, event: OptionList.OptionSelected) -> None:
        self.app.theme = str(event.option.id)


# ---------------------------------------------------------------------------
# Modal screen definitions
# ---------------------------------------------------------------------------


class InfoModal(ModalScreen[str]):
    """A simple informational modal."""

    BINDINGS = [("escape", "dismiss_modal", "Close")]

    def compose(self) -> ComposeResult:
        with Container(id="info-modal-box"):
            yield Static("[bold]Info Modal[/bold]", id="modal-title")
            yield Static(
                "This is a [bold]ModalScreen[/bold]. It overlays the current screen "
                "and can return a typed value via [bold]dismiss(value)[/bold].\n\n"
                "Press [bold]Close[/bold] or [bold]Escape[/bold] to dismiss.",
                id="modal-body",
            )
            with Horizontal(id="modal-footer"):
                yield Button("Close", id="modal-close-btn", variant="primary")

    @on(Button.Pressed, "#modal-close-btn")
    def on_close(self) -> None:
        self.dismiss("info modal closed")

    def action_dismiss_modal(self) -> None:
        self.dismiss("info modal escaped")


class ConfirmModal(ModalScreen[bool]):
    """A boolean confirm/cancel modal."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="confirm-modal-box"):
            yield Static("[bold]Confirm Action[/bold]", id="modal-title")
            yield Static(
                "Are you sure you want to proceed?\n\n"
                "This demonstrates a [bold]ModalScreen[bool][/bold] that returns "
                "[bold green]True[/bold green] or [bold red]False[/bold red].",
                id="modal-body",
            )
            with Horizontal(id="modal-footer"):
                yield Button("Cancel", id="modal-cancel-btn")
                yield Button("Confirm", id="modal-confirm-btn", variant="success")

    @on(Button.Pressed, "#modal-confirm-btn")
    def on_confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#modal-cancel-btn")
    def on_cancel_btn(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)


class FormModal(ModalScreen[str | None]):
    """A simple form modal that returns user input."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        with Container(id="form-modal-box"):
            yield Static("[bold]Form Modal[/bold]", id="modal-title")
            yield Static("Enter a value to return to the parent screen:", id="modal-body")
            yield Input(placeholder="Enter something…", id="form-modal-input")
            with Horizontal(id="modal-footer"):
                yield Button("Cancel", id="form-cancel-btn")
                yield Button("Submit", id="form-submit-btn", variant="primary")

    @on(Button.Pressed, "#form-submit-btn")
    def on_submit(self) -> None:
        value = self.query_one("#form-modal-input", Input).value
        self.dismiss(value)

    @on(Button.Pressed, "#form-cancel-btn")
    def on_cancel_btn(self) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#form-modal-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)


# ---------------------------------------------------------------------------
# Navigation sidebar
# ---------------------------------------------------------------------------

_SECTIONS = [
    ("buttons", "Buttons"),
    ("inputs", "Inputs"),
    ("selection", "Selection"),
    ("lists", "Lists & Tree"),
    ("data", "Data Display"),
    ("progress", "Progress & State"),
    ("content", "Content"),
    ("tabs", "Tabs & Switcher"),
    ("layout", "Layout"),
    ("digits", "Digits"),
    ("workers", "Workers"),
    ("modals", "Modals"),
    ("theme", "Themes"),
]


class Sidebar(Widget):
    """Left navigation sidebar — click an item to switch panels."""

    DEFAULT_CSS = """
    Sidebar {
        width: 22;
        height: 1fr;
        dock: left;
        background: $background;
        border-right: solid $panel;
        padding: 1 0;
    }
    Sidebar ListView {
        background: transparent;
        height: 1fr;
    }
    Sidebar ListItem {
        padding: 0 2;
    }
    Sidebar ListItem.--highlight {
        background: $surface;
    }
    Sidebar ListItem > Label {
        color: $text-muted;
    }
    Sidebar #sidebar-title {
        text-style: bold;
        color: $text;
        padding: 0 2;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("Component Library", id="sidebar-title")
        yield ListView(
            *[ListItem(Label(label), id=f"nav-{key}") for key, label in _SECTIONS],
            id="sidebar-list",
        )


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

_PANEL_MAP = {
    "buttons": ButtonsPanel,
    "inputs": InputsPanel,
    "selection": SelectionPanel,
    "lists": ListsPanel,
    "data": DataPanel,
    "progress": ProgressPanel,
    "content": ContentPanel,
    "tabs": TabbedPanel,
    "layout": LayoutPanel,
    "digits": DigitsPanel,
    "workers": WorkersPanel,
    "modals": ModalPanel,
    "theme": ThemePanel,
}


class ComponentLibraryApp(App):
    """Textual Component Library — interactive showcase of every widget."""

    CSS_PATH = "component_library_minimal.tcss"

    TITLE = "Component Library  —  Minimal"
    SUB_TITLE = "Monochromatic edition"

    BINDINGS = [
        Binding("ctrl+t", "toggle_theme", "Toggle theme", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("j", "next_section", "Next", show=False),
        Binding("k", "prev_section", "Prev", show=False),
    ]

    _active_key: reactive[str] = reactive("buttons")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="app-body"):
            yield Sidebar()
            with ContentSwitcher(initial="panel-buttons", id="main-switcher"):
                for key, cls in _PANEL_MAP.items():
                    instance = cls(id=f"panel-{key}")
                    yield instance
        yield Footer()

    def on_mount(self) -> None:
        self._select_section("buttons")

    def _select_section(self, key: str) -> None:
        self._active_key = key
        self.query_one("#main-switcher", ContentSwitcher).current = f"panel-{key}"
        nav_list = self.query_one("#sidebar-list", ListView)
        for item in nav_list.query(ListItem):
            item.remove_class("active")
        try:
            nav_list.query_one(f"#nav-{key}", ListItem).add_class("active")
        except Exception:
            pass

    @on(ListView.Selected, "#sidebar-list")
    def on_nav_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        if item_id.startswith("nav-"):
            self._select_section(item_id[4:])

    def action_toggle_theme(self) -> None:
        themes = list(self.available_themes.keys())
        current = themes.index(self.theme) if self.theme in themes else 0
        self.theme = themes[(current + 1) % len(themes)]
        self.notify(f"Theme: {self.theme}", title="Theme changed")

    def action_next_section(self) -> None:
        keys = [k for k, _ in _SECTIONS]
        idx = keys.index(self._active_key) if self._active_key in keys else 0
        self._select_section(keys[(idx + 1) % len(keys)])

    def action_prev_section(self) -> None:
        keys = [k for k, _ in _SECTIONS]
        idx = keys.index(self._active_key) if self._active_key in keys else 0
        self._select_section(keys[(idx - 1) % len(keys)])


if __name__ == "__main__":
    ComponentLibraryApp().run()
