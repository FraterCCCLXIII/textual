from __future__ import annotations

from textual import events
from textual.widgets import Static


class PaneSplitter(Static):
    """A minimal draggable divider for resizing adjacent panes."""

    def __init__(
        self,
        *,
        target_pane_id: str,
        min_width: int = 24,
        max_width: int = 80,
        **kwargs,
    ) -> None:
        super().__init__(" ", **kwargs)
        self.target_pane_id = target_pane_id
        self.min_width = min_width
        self.max_width = max_width
        self._dragging = False
        self._start_x = 0
        self._start_width = 0

    def render(self) -> str:
        height = max(self.size.height, 1)
        middle = height // 2
        lines = ["│"] * height
        lines[middle] = "⋮"
        return "\n".join(lines)

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self._start_x = event.screen_x
        pane = self.screen.query_one(f"#{self.target_pane_id}")
        self._start_width = pane.size.width or self.min_width
        self.capture_mouse()
        self.add_class("-dragging")
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if not self._dragging:
            return
        self._dragging = False
        self.capture_mouse(False)
        self.remove_class("-dragging")
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        pane = self.screen.query_one(f"#{self.target_pane_id}")
        delta = event.screen_x - self._start_x
        desired = self._start_width + delta
        desired = max(self.min_width, min(self.max_width, desired))
        pane.styles.width = desired
        pane.refresh(layout=True)
        event.stop()
