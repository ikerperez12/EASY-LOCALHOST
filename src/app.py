"""
Desktop UI for Easy Localhost.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import tkinter as tk
import tkinter.font as tkfont
import time
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from actions import ActionResult, kill_process_tree, open_in_browser, open_in_folder
from controller import LocalhostController, ScanResult
from models import AppState, PortInfo, PortStatus, RefreshMode, next_refresh_mode
from presentation_state import merge_group_visibility_state, summarize_port_chips
from utils import APP_DISPLAY_NAME, APP_NAME, APP_VERSION, get_icon_path, truncate_path

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

CANVAS = "#000000"
SURFACE = "#0C0F12"
SURFACE_ELEVATED = "#13181E"
SURFACE_CARD = "#171D24"
SURFACE_ROW = "#1C232B"
SURFACE_ROW_ALT = "#181F27"
SURFACE_TINT = "#202833"
BORDER = "#2A333D"
BORDER_STRONG = "#3A4652"
TEXT = "#F3F6F8"
TEXT_SOFT = "#A6B1BC"
TEXT_MUTED = "#7D8996"
ACCENT = "#C7F36B"
ACCENT_HOVER = "#D9FF90"
ACCENT_DEEP = "#253116"
WARNING = "#D6A85F"
WARNING_DEEP = "#2C2417"
DANGER = "#D96B5F"
DANGER_DEEP = "#2C1918"
UNKNOWN = "#5D6873"
UNKNOWN_DEEP = "#161C22"

STATUS_META = {
    PortStatus.ACTIVE: ("Active", ACCENT, ACCENT_DEEP),
    PortStatus.LISTENING: ("Listening", WARNING, WARNING_DEEP),
    PortStatus.ZOMBIE: ("Stuck", DANGER, DANGER_DEEP),
    PortStatus.UNKNOWN: ("Unknown", UNKNOWN, UNKNOWN_DEEP),
}


@dataclass(slots=True)
class PortGroupData:
    """UI grouping information for a folder/project."""

    key: str
    title: str
    path: str
    ports: list[PortInfo]

    @property
    def active_count(self) -> int:
        return sum(1 for port in self.ports if port.status is PortStatus.ACTIVE)

    @property
    def port_chips(self) -> tuple[str, ...]:
        return summarize_port_chips(self.ports)


def _button_colors(variant: str) -> tuple[str, str, str, str]:
    if variant == "primary":
        return ACCENT, ACCENT_HOVER, ACCENT, CANVAS
    if variant == "accent":
        return ACCENT_DEEP, SURFACE_TINT, ACCENT, TEXT
    if variant == "secondary":
        return SURFACE_ELEVATED, SURFACE_ROW, BORDER, TEXT
    if variant == "ghost":
        return "transparent", SURFACE_TINT, BORDER_STRONG, TEXT_SOFT
    if variant == "danger":
        return "transparent", DANGER_DEEP, DANGER, DANGER
    raise ValueError(f"Unsupported button variant: {variant}")


def _bind_left_click(widgets, callback) -> None:
    for widget in widgets:
        widget.bind("<Button-1>", lambda _event, cb=callback: cb())


class EasyLocalhostApp(ctk.CTk):
    """Compact floating desktop window for localhost monitoring."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_DISPLAY_NAME} {APP_VERSION}")
        self.configure(fg_color=CANVAS)
        self.minsize(460, 520)
        self.geometry(self._default_geometry())
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_window_icon()

        self.app_state = AppState(refresh_mode=RefreshMode.AUTO, always_on_top=True)
        self.controller = LocalhostController()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self.scan_future: Future[ScanResult] | None = None
        self.pending_refresh = False
        self.refresh_job: str | None = None
        self.last_signature: tuple[tuple[str, tuple[tuple[int, int, str, int | None], ...]], ...] = ()
        self.expanded_groups: set[str] = set()
        self.known_groups: set[str] = set()
        self.group_widgets: dict[str, PortGroup] = {}
        self.empty_state_widget: ctk.CTkFrame | None = None
        self.pending_render_groups: list[PortGroupData] | None = None
        self.pending_restore_scroll: float | None = None
        self.pending_render_defer_while_scrolling = True
        self.render_job: str | None = None
        self.scroll_hold_until = 0.0

        self.brand_icon = self._load_brand_icon()
        self.port_cards_frame: ctk.CTkScrollableFrame | None = None
        self.summary_label: ctk.CTkLabel | None = None
        self.updated_label: ctk.CTkLabel | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.topmost_button: ctk.CTkButton | None = None
        self.refresh_mode_button: ctk.CTkButton | None = None
        self.expand_all_button: ctk.CTkButton | None = None
        self.collapse_all_button: ctk.CTkButton | None = None

        self._build_layout()
        self._sync_topmost_button()
        self._sync_refresh_mode_button()
        self.bind("<F5>", lambda _event: self.request_refresh(immediate=True))
        self.after(120, lambda: self.request_refresh(immediate=True))
        self.after(125, self._poll_scan_future)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(self, fg_color=CANVAS, corner_radius=0)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)

        hero = ctk.CTkFrame(
            shell,
            fg_color=SURFACE,
            corner_radius=20,
            border_width=1,
            border_color=BORDER,
        )
        hero.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        hero.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(hero, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        header.grid_columnconfigure(1, weight=1)

        if self.brand_icon is not None:
            icon_label = ctk.CTkLabel(header, text="", image=self.brand_icon)
            icon_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 10))

        meta_line = ctk.CTkFrame(header, fg_color="transparent")
        meta_line.grid(row=0, column=1, sticky="w")

        title_label = ctk.CTkLabel(
            meta_line,
            text=APP_DISPLAY_NAME,
            text_color=TEXT,
            font=("Segoe UI Semibold", 18),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="w")

        version_chip = ctk.CTkLabel(
            meta_line,
            text=f"v{APP_VERSION}",
            text_color=ACCENT,
            fg_color=ACCENT_DEEP,
            corner_radius=10,
            padx=8,
            pady=3,
            font=("Segoe UI Semibold", 9),
        )
        version_chip.grid(row=0, column=1, sticky="w", padx=(9, 0))

        subtitle = ctk.CTkLabel(
            header,
            text="Collapsed folders. Fast localhost actions.",
            text_color=TEXT_SOFT,
            font=("Segoe UI", 11),
            anchor="w",
        )
        subtitle.grid(row=1, column=1, sticky="w", pady=(2, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=(10, 0))
        for column in range(2):
            actions.grid_columnconfigure(column, weight=1)

        self.topmost_button = self._make_button(
            actions,
            text="Pinned",
            row=0,
            column=0,
            command=self.toggle_topmost,
            variant="primary",
            width=76,
            height=28,
            corner_radius=14,
        )
        self._make_button(
            actions,
            text="Reload",
            row=0,
            column=1,
            command=lambda: self.request_refresh(immediate=True),
            variant="secondary",
            width=76,
            height=28,
            corner_radius=14,
        )
        self.refresh_mode_button = self._make_button(
            actions,
            text=self.app_state.refresh_button_text,
            row=1,
            column=0,
            columnspan=2,
            command=self.cycle_refresh_mode,
            variant="accent",
            width=160,
            height=28,
            corner_radius=14,
            font_size=10,
        )

        summary = ctk.CTkFrame(
            shell,
            fg_color=SURFACE_ELEVATED,
            corner_radius=16,
            border_width=1,
            border_color=BORDER,
        )
        summary.grid(row=1, column=0, sticky="ew", padx=10)
        summary.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(
            summary,
            text="Scanning localhost ports...",
            text_color=TEXT,
            font=("Segoe UI Semibold", 12),
            padx=12,
            pady=8,
            anchor="w",
        )
        self.summary_label.grid(row=0, column=0, sticky="w")

        self.expand_all_button = self._make_button(
            summary,
            text="Expand",
            row=0,
            column=1,
            command=self.expand_all_groups,
            variant="ghost",
            width=70,
            height=24,
            corner_radius=12,
            font_size=9,
            padx=(8, 0),
            pady=(0, 0),
        )
        self.collapse_all_button = self._make_button(
            summary,
            text="Collapse",
            row=0,
            column=2,
            command=self.collapse_all_groups,
            variant="ghost",
            width=76,
            height=24,
            corner_radius=12,
            font_size=9,
            padx=(6, 0),
            pady=(0, 0),
        )

        self.updated_label = ctk.CTkLabel(
            summary,
            text="Waiting",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10),
            padx=10,
            pady=8,
            anchor="e",
        )
        self.updated_label.grid(row=0, column=3, sticky="e")

        self.port_cards_frame = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=SURFACE_TINT,
            scrollbar_button_hover_color=ACCENT,
        )
        self.port_cards_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(8, 8))
        self.port_cards_frame.grid_columnconfigure(0, weight=1)
        self._bind_scroll_activity()

        footer = ctk.CTkFrame(
            shell,
            fg_color=SURFACE,
            corner_radius=14,
            border_width=1,
            border_color=BORDER,
        )
        footer.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10),
            anchor="w",
            padx=10,
            pady=6,
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

    def _make_button(
        self,
        parent,
        text: str,
        row: int,
        column: int,
        command,
        *,
        variant: str = "secondary",
        width: int = 90,
        height: int = 36,
        corner_radius: int = 18,
        columnspan: int = 1,
        font_size: int = 11,
        padx: tuple[int, int] | int | None = None,
        pady: tuple[int, int] | int | None = None,
    ) -> ctk.CTkButton:
        fg_color, hover_color, border_color, text_color = _button_colors(variant)
        button = ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=height,
            corner_radius=corner_radius,
            fg_color=fg_color,
            hover_color=hover_color,
            border_width=1,
            border_color=border_color,
            text_color=text_color,
            font=("Segoe UI Semibold", font_size),
            command=command,
        )
        grid_padx = padx if padx is not None else (0 if column == 0 else 8, 0)
        grid_pady = pady if pady is not None else (0 if row == 0 else 8, 0)
        button.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=grid_padx,
            pady=grid_pady,
        )
        return button

    def _sync_topmost_button(self) -> None:
        if not self.topmost_button:
            return

        variant = "primary" if self.app_state.always_on_top else "secondary"
        fg_color, hover_color, border_color, text_color = _button_colors(variant)
        self.topmost_button.configure(
            text="Pinned" if self.app_state.always_on_top else "Unpinned",
            fg_color=fg_color,
            hover_color=hover_color,
            border_color=border_color,
            text_color=text_color,
        )

    def _sync_refresh_mode_button(self) -> None:
        if not self.refresh_mode_button:
            return

        variant = "primary" if self.app_state.refresh_mode is RefreshMode.AUTO else "accent"
        if self.app_state.refresh_mode is RefreshMode.MANUAL:
            variant = "secondary"

        fg_color, hover_color, border_color, text_color = _button_colors(variant)
        self.refresh_mode_button.configure(
            text=self.app_state.refresh_button_text,
            fg_color=fg_color,
            hover_color=hover_color,
            border_color=border_color,
            text_color=text_color,
        )

    def toggle_topmost(self) -> None:
        self.app_state.always_on_top = not self.app_state.always_on_top
        self.attributes("-topmost", self.app_state.always_on_top)
        self._sync_topmost_button()
        self._set_status(
            "Window pinned to top." if self.app_state.always_on_top else "Window unpinned from top."
        )

    def cycle_refresh_mode(self) -> None:
        self.app_state.refresh_mode = next_refresh_mode(self.app_state.refresh_mode)
        self._sync_refresh_mode_button()

        if self.refresh_job is not None:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

        if self.app_state.refresh_mode is RefreshMode.MANUAL:
            self._set_status("Refresh mode set to Manual. Use Reload to scan.")
            return

        self._queue_next_refresh(force=True)
        self._set_status(f"Refresh mode set to {self.app_state.refresh_status_text}.")

    def expand_all_groups(self) -> None:
        groups = self._group_ports(self.app_state.ports)
        self.expanded_groups = {group.key for group in groups}
        self._schedule_render_groups(groups, self._get_scroll_position(), defer_while_scrolling=False)
        self._set_status("All folders expanded.")

    def collapse_all_groups(self) -> None:
        self.expanded_groups.clear()
        self._schedule_render_groups(
            self._group_ports(self.app_state.ports),
            self._get_scroll_position(),
            defer_while_scrolling=False,
        )
        self._set_status("All folders collapsed.")

    def request_refresh(self, immediate: bool = False) -> None:
        if self.refresh_job is not None:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

        if self.scan_future and not self.scan_future.done():
            self.pending_refresh = True
            return

        self.app_state.is_scanning = True
        self._set_status("Scanning localhost ports...")
        self.scan_future = self.executor.submit(self.controller.refresh)

    def _poll_scan_future(self) -> None:
        if self.scan_future and self.scan_future.done():
            future = self.scan_future
            self.scan_future = None
            self.app_state.is_scanning = False

            try:
                result = future.result()
            except Exception as exc:
                logger.exception("Scan failed: %s", exc)
                self._set_status(f"Scan failed: {exc}")
                self._queue_next_refresh()
            else:
                self._apply_scan_result(result)
                self._queue_next_refresh(force=self.pending_refresh)

            self.pending_refresh = False

        self.after(120, self._poll_scan_future)

    def _queue_next_refresh(self, force: bool = False) -> None:
        if self.refresh_job is not None:
            self.after_cancel(self.refresh_job)
            self.refresh_job = None

        if force:
            self.refresh_job = self.after(250, self.request_refresh)
            return

        if self.app_state.scan_interval_ms is None:
            return

        self.refresh_job = self.after(self.app_state.scan_interval_ms, self.request_refresh)

    def _apply_scan_result(self, result: ScanResult) -> None:
        ordered_ports = sorted(result.ports, key=_port_sort_key)
        groups = self._group_ports(ordered_ports)
        self._expand_new_groups(groups)

        self.app_state.ports = ordered_ports
        self.app_state.last_scan_time = result.scanned_at
        self.app_state.total_scans += 1

        active = sum(1 for item in ordered_ports if item.status is PortStatus.ACTIVE)
        summary = (
            f"{len(groups)} folders | {len(ordered_ports)} localhost | "
            f"{active} active | {result.elapsed_ms:.0f} ms"
        )
        updated = datetime.fromtimestamp(result.scanned_at).strftime("%H:%M:%S")

        if self.summary_label:
            self.summary_label.configure(text=summary)
        if self.updated_label:
            self.updated_label.configure(text=f"Updated {updated}")

        signature = self._groups_signature(groups)
        if signature != self.last_signature:
            scroll_position = self._get_scroll_position()
            self.last_signature = signature
            self._schedule_render_groups(groups, restore_scroll=scroll_position)

        if ordered_ports:
            self._set_status(
                f"Watching {len(ordered_ports)} ports in {len(groups)} folders. "
                f"Refresh: {self.app_state.refresh_status_text}."
            )
        else:
            self._set_status(f"No localhost processes detected. Refresh: {self.app_state.refresh_status_text}.")

    def _group_ports(self, ports: list[PortInfo]) -> list[PortGroupData]:
        groups: dict[str, PortGroupData] = {}

        for port in ports:
            key_path = _group_path(port)
            group_key = key_path.casefold() if key_path else f"unresolved:{port.display_name.casefold()}"
            group_title = _group_title(port, key_path)
            group = groups.setdefault(
                group_key,
                PortGroupData(
                    key=group_key,
                    title=group_title,
                    path=key_path,
                    ports=[],
                ),
            )
            group.ports.append(port)

        for group in groups.values():
            group.ports.sort(key=_port_sort_key)

        return sorted(
            groups.values(),
            key=lambda group: (
                0 if group.active_count > 0 else 1,
                -group.active_count,
                -len(group.ports),
                group.title.casefold(),
                group.path.casefold(),
            ),
        )

    def _expand_new_groups(self, groups: list[PortGroupData]) -> None:
        self.expanded_groups, self.known_groups = merge_group_visibility_state(
            self.expanded_groups,
            self.known_groups,
            ((group.key, group.active_count) for group in groups),
        )

    def _groups_signature(
        self,
        groups: list[PortGroupData],
    ) -> tuple[tuple[str, tuple[tuple[int, int, str, int | None], ...]], ...]:
        return tuple(
            (
                group.key,
                tuple(
                    (
                        port.port,
                        port.pid,
                        port.status.value,
                        port.http_status_code,
                    )
                    for port in group.ports
                ),
            )
            for group in groups
        )

    def _render_groups(
        self,
        groups: list[PortGroupData],
        restore_scroll: float | None = None,
    ) -> None:
        if not self.port_cards_frame:
            return

        self.pending_render_groups = None
        self.pending_restore_scroll = None
        self.render_job = None

        if not groups:
            for widget in self.group_widgets.values():
                widget.destroy()
            self.group_widgets.clear()
            if self.empty_state_widget is None or not self.empty_state_widget.winfo_exists():
                self.empty_state_widget = self._build_empty_state(self.port_cards_frame)
            self.empty_state_widget.grid(row=0, column=0, sticky="ew", pady=(8, 0))
            return

        if self.empty_state_widget is not None and self.empty_state_widget.winfo_exists():
            self.empty_state_widget.grid_forget()

        current_keys = {group.key for group in groups}
        for group_key in tuple(self.group_widgets):
            if group_key not in current_keys:
                self.group_widgets.pop(group_key).destroy()

        self._render_group_batch(groups, 0, restore_scroll)

    def _render_group_batch(
        self,
        groups: list[PortGroupData],
        start_index: int,
        restore_scroll: float | None,
    ) -> None:
        self.render_job = None
        started_at = time.perf_counter()
        index = start_index

        while index < len(groups):
            self._render_single_group(groups[index], index)
            index += 1
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            if index < len(groups) and elapsed_ms >= 28:
                self.render_job = self.after(
                    1,
                    lambda next_index=index: self._render_group_batch(
                        groups,
                        next_index,
                        restore_scroll,
                    ),
                )
                return

        if restore_scroll is not None:
            self.after(16, lambda: self._restore_scroll_position(restore_scroll))
            self.after(90, lambda: self._restore_scroll_position(restore_scroll))
            self.after(350, lambda: self._restore_scroll_position(restore_scroll))
            self.after(900, lambda: self._restore_scroll_position(restore_scroll))

        if self.pending_render_groups is not None:
            self.render_job = self.after_idle(self._flush_pending_render)

    def _render_single_group(self, group: PortGroupData, row_index: int) -> None:
        if not self.port_cards_frame:
            return

        expanded = group.key in self.expanded_groups
        render_signature = _group_render_signature(group, expanded)
        group_widget = self.group_widgets.get(group.key)
        should_grid = False
        if group_widget is None or group_widget.render_signature != render_signature:
            if group_widget is not None:
                group_widget.destroy()
            group_widget = PortGroup(
                self.port_cards_frame,
                group=group,
                expanded=expanded,
                render_signature=render_signature,
                on_toggle=self._toggle_group,
                on_open=self._handle_open,
                on_copy=self._handle_copy,
                on_folder=self._handle_folder,
                on_group_folder=self._handle_group_folder,
                on_close=self._handle_close,
            )
            self.group_widgets[group.key] = group_widget
            should_grid = True

        if getattr(group_widget, "render_row_index", None) != row_index:
            should_grid = True

        if should_grid or not group_widget.winfo_ismapped():
            group_widget.grid(row=row_index, column=0, sticky="ew", pady=(0, 6))
            group_widget.render_row_index = row_index

    def _schedule_render_groups(
        self,
        groups: list[PortGroupData],
        restore_scroll: float | None = None,
        defer_while_scrolling: bool = True,
    ) -> None:
        self.pending_render_groups = groups
        if restore_scroll is not None:
            self.pending_restore_scroll = restore_scroll
        if not defer_while_scrolling:
            self.pending_render_defer_while_scrolling = False
            if self.render_job is not None:
                try:
                    self.after_cancel(self.render_job)
                except Exception as exc:
                    logger.debug("Could not cancel deferred render: %s", exc)
                self.render_job = None
        if self.render_job is None:
            self.render_job = self.after_idle(self._flush_pending_render)

    def _flush_pending_render(self) -> None:
        groups = self.pending_render_groups
        restore_scroll = self.pending_restore_scroll
        if groups is None:
            self.render_job = None
            self.pending_restore_scroll = None
            self.pending_render_defer_while_scrolling = True
            return

        if self.pending_render_defer_while_scrolling and self._is_scroll_active():
            delay_ms = max(80, int((self.scroll_hold_until - time.monotonic()) * 1000))
            self.render_job = self.after(delay_ms, self._flush_pending_render)
            return

        self.pending_render_defer_while_scrolling = True
        self._render_groups(groups, restore_scroll=restore_scroll)

    def _toggle_group(self, group_key: str) -> None:
        if group_key in self.expanded_groups:
            self.expanded_groups.remove(group_key)
        else:
            self.expanded_groups.add(group_key)
        self._schedule_render_groups(
            self._group_ports(self.app_state.ports),
            self._get_scroll_position(),
            defer_while_scrolling=False,
        )

    def _build_empty_state(self, parent: ctk.CTkScrollableFrame) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=SURFACE_CARD,
            corner_radius=30,
            border_width=1,
            border_color=BORDER_STRONG,
        )
        frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            frame,
            text="No localhost detected",
            text_color=TEXT,
            font=("Segoe UI Semibold", 19),
        )
        title.grid(row=0, column=0, pady=(24, 8), padx=20)

        detail = ctk.CTkLabel(
            frame,
            text="Launch a local dev server and it will appear here automatically.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 13),
            wraplength=360,
            justify="center",
        )
        detail.grid(row=1, column=0, pady=(0, 24), padx=20)
        return frame

    def _handle_open(self, port_info: PortInfo) -> None:
        self._show_action_result(open_in_browser(port_info.port))

    def _handle_copy(self, port_info: PortInfo) -> None:
        self.clipboard_clear()
        self.clipboard_append(port_info.url)
        self._show_action_result(ActionResult(True, f"Copied {port_info.url}"))

    def _handle_folder(self, port_info: PortInfo) -> None:
        self._show_action_result(open_in_folder(port_info.launch_path))

    def _handle_group_folder(self, group_path: str) -> None:
        self._show_action_result(open_in_folder(group_path))

    def _handle_close(self, port_info: PortInfo) -> None:
        answer = messagebox.askyesno(
            "Close localhost",
            f"Close {port_info.process_name} on :{port_info.port}?",
            parent=self,
        )
        if not answer:
            return

        result = kill_process_tree(port_info.pid)
        self._show_action_result(result)
        if result.success:
            self.request_refresh(immediate=True)

    def _show_action_result(self, result: ActionResult) -> None:
        self._set_status(result.message or ("Done" if result.success else "Action failed"))

    def _set_status(self, text: str) -> None:
        if self.status_label:
            self.status_label.configure(text=text)

    def _default_geometry(self) -> str:
        width = min(560, max(500, self.winfo_screenwidth() - 64))
        height = min(760, max(640, self.winfo_screenheight() - 64))
        margin = 18
        x = max(self.winfo_screenwidth() - width - margin, margin)
        y = margin
        return f"{width}x{height}+{x}+{y}"

    def _get_scroll_position(self) -> float:
        if not self.port_cards_frame:
            return 0.0
        try:
            return float(self.port_cards_frame._parent_canvas.yview()[0])
        except Exception:
            return 0.0

    def _restore_scroll_position(self, position: float) -> None:
        if not self.port_cards_frame:
            return
        try:
            self.port_cards_frame._parent_canvas.yview_moveto(position)
        except Exception as exc:
            logger.debug("Could not restore scroll position: %s", exc)

    def _bind_scroll_activity(self) -> None:
        if not self.port_cards_frame:
            return

        try:
            canvas = self.port_cards_frame._parent_canvas
            canvas.bind("<MouseWheel>", self._note_scroll_activity, add="+")
            canvas.bind("<ButtonPress-1>", self._note_scroll_activity, add="+")
            canvas.bind("<B1-Motion>", self._note_scroll_activity, add="+")
        except Exception as exc:
            logger.debug("Could not bind scroll activity hooks: %s", exc)

    def _note_scroll_activity(self, _event=None) -> None:
        self.scroll_hold_until = time.monotonic() + 0.45

    def _is_scroll_active(self) -> bool:
        return time.monotonic() < self.scroll_hold_until

    def _set_window_icon(self) -> None:
        try:
            self.iconbitmap(get_icon_path("ico"))
        except Exception as exc:
            logger.debug("Could not set window icon: %s", exc)

    def _load_brand_icon(self) -> ctk.CTkImage | None:
        try:
            image = Image.open(get_icon_path("png"))
            return ctk.CTkImage(light_image=image, dark_image=image, size=(30, 30))
        except Exception as exc:
            logger.debug("Could not load brand icon: %s", exc)
            return None

    def _on_close(self) -> None:
        try:
            if self.refresh_job is not None:
                self.after_cancel(self.refresh_job)
            if self.render_job is not None:
                self.after_cancel(self.render_job)
            self.executor.shutdown(wait=False, cancel_futures=True)
        finally:
            self.destroy()


def _group_render_signature(group: PortGroupData, expanded: bool) -> tuple:
    visible_ports = group.ports if expanded else group.ports[:3]
    return (
        group.key,
        expanded,
        group.title,
        group.path,
        len(group.ports),
        group.active_count,
        tuple(
            (
                port.port,
                port.pid if expanded else None,
                port.process_name if expanded else "",
                port.status.value,
                port.http_status_code if expanded else None,
                port.source_display_path if expanded else "",
            )
            for port in visible_ports
        ),
    )


class PortGroup(ctk.CTkFrame):
    """Collapsible folder/project group."""

    def __init__(
        self,
        master,
        group: PortGroupData,
        expanded: bool,
        render_signature: tuple,
        on_toggle,
        on_open,
        on_copy,
        on_folder,
        on_group_folder,
        on_close,
    ) -> None:
        border_color = ACCENT if expanded and group.active_count > 0 else BORDER_STRONG if expanded else BORDER
        super().__init__(
            master,
            fg_color=SURFACE_CARD if expanded else SURFACE_ELEVATED,
            corner_radius=18,
            border_width=1,
            border_color=border_color,
        )
        self.render_signature = render_signature
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 7))
        header.grid_columnconfigure(1, weight=1)

        toggle_pill = ctk.CTkButton(
            header,
            text="-" if expanded else "+",
            fg_color=ACCENT_DEEP if group.active_count > 0 else SURFACE_ROW,
            hover_color=SURFACE_TINT,
            corner_radius=12,
            border_width=1,
            border_color=ACCENT if expanded and group.active_count > 0 else BORDER_STRONG,
            width=26,
            height=26,
            text_color=ACCENT if group.active_count > 0 else TEXT_SOFT,
            font=("Segoe UI Semibold", 13),
            command=lambda: on_toggle(group.key),
        )
        toggle_pill.grid(row=0, column=0, sticky="w", padx=(0, 9))

        info = ctk.CTkFrame(header, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew")
        info.grid_columnconfigure(0, weight=1)

        top_line = ctk.CTkFrame(info, fg_color="transparent")
        top_line.grid(row=0, column=0, sticky="ew")
        top_line.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            top_line,
            text=group.title,
            text_color=TEXT,
            font=("Segoe UI Semibold", 14),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        stats = ctk.CTkLabel(
            top_line,
            text=f"{len(group.ports)} ports / {group.active_count} active",
            text_color=ACCENT if group.active_count > 0 else TEXT_SOFT,
            fg_color=ACCENT_DEEP if group.active_count > 0 else SURFACE_ROW,
            corner_radius=12,
            font=("Segoe UI Semibold", 9),
            padx=8,
            pady=4,
        )
        stats.grid(row=0, column=1, sticky="e", padx=(8, 0))

        detail_line = ctk.CTkFrame(info, fg_color="transparent")
        detail_line.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        detail_line.grid_columnconfigure(0, weight=1)

        path_label = ctk.CTkLabel(
            detail_line,
            text=truncate_path(group.path, 56) if group.path else "No folder resolved",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 10),
            anchor="w",
        )
        path_label.grid(row=0, column=0, sticky="w")

        chips = ctk.CTkFrame(detail_line, fg_color="transparent")
        chips.grid(row=0, column=1, sticky="e", padx=(10, 0))

        chip_widgets = []
        for index, port in enumerate(group.ports[:3]):
            chip = ctk.CTkLabel(
                chips,
                text=f":{port.port}",
                text_color=_port_chip_text(port.status),
                fg_color=_port_chip_background(port.status),
                corner_radius=9,
                font=("Consolas", 9, "bold"),
                padx=7,
                pady=3,
            )
            chip.grid(row=0, column=index, sticky="e", padx=(4 if index else 0, 0))
            chip_widgets.append(chip)

        folder_fg, folder_hover, folder_border, folder_text = _button_colors("ghost")
        folder_button = ctk.CTkButton(
            header,
            text="Folder",
            width=62,
            height=26,
            corner_radius=13,
            fg_color=folder_fg,
            hover_color=folder_hover,
            border_width=1,
            border_color=folder_border,
            text_color=folder_text,
            font=("Segoe UI Semibold", 10),
            command=lambda: on_group_folder(group.path),
            state="normal" if group.path else "disabled",
        )
        folder_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

        _bind_left_click(
            [header, info, top_line, title, stats, detail_line, path_label, chips, *chip_widgets],
            lambda: on_toggle(group.key),
        )

        self.row_render_job: str | None = None
        self.body: ctk.CTkFrame | None = None
        self.group_ports = group.ports
        self.next_port_row = 0
        self.on_open = on_open
        self.on_copy = on_copy
        self.on_folder = on_folder
        self.on_close = on_close

        if expanded:
            self.body = ctk.CTkFrame(self, fg_color="transparent")
            self.body.grid(row=1, column=0, sticky="ew", padx=7, pady=(0, 7))
            self.body.grid_columnconfigure(0, weight=1)
            self.row_render_job = self.after_idle(self._render_port_batch)

    def _render_port_batch(self) -> None:
        self.row_render_job = None
        if self.body is None or not self.body.winfo_exists():
            return

        started_at = time.perf_counter()
        while self.next_port_row < len(self.group_ports):
            row_index = self.next_port_row
            port = self.group_ports[row_index]
            card = PortCard(
                self.body,
                port_info=port,
                row_index=row_index,
                on_open=self.on_open,
                on_copy=self.on_copy,
                on_folder=self.on_folder,
                on_close=self.on_close,
            )
            card.grid(row=row_index, column=0, sticky="ew", pady=(0, 5))
            self.next_port_row += 1

            elapsed_ms = (time.perf_counter() - started_at) * 1000
            if self.next_port_row < len(self.group_ports) and elapsed_ms >= 12:
                self.row_render_job = self.after(1, self._render_port_batch)
                return

    def destroy(self) -> None:
        if self.row_render_job is not None:
            try:
                self.after_cancel(self.row_render_job)
            except Exception as exc:
                logger.debug("Could not cancel pending row render: %s", exc)
            self.row_render_job = None
        super().destroy()


class PortCard(tk.Canvas):
    """Single compact row representing one localhost process.

    A canvas row replaces many nested widgets. This keeps large localhost lists
    responsive while preserving a polished visual treatment.
    """

    def __init__(
        self,
        master,
        port_info: PortInfo,
        row_index: int,
        on_open,
        on_copy,
        on_folder,
        on_close,
    ) -> None:
        status_label, status_color, status_surface = STATUS_META[port_info.status]
        row_color = SURFACE_ROW if row_index % 2 == 0 else SURFACE_ROW_ALT
        super().__init__(master, height=94, bg=SURFACE_CARD, highlightthickness=0, bd=0)
        self.configure(cursor="arrow")
        self.port_info = port_info
        self.row_color = row_color
        self.status_label = status_label
        self.status_color = status_color
        self.status_surface = status_surface
        self.on_open = on_open
        self.on_copy = on_copy
        self.on_folder = on_folder
        self.on_close = on_close
        self.hover_button: str | None = None
        self.button_regions: dict[str, tuple[int, int, int, int]] = {}

        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Motion>", self._handle_motion)
        self.bind("<Leave>", self._handle_leave)
        self.bind("<Button-1>", self._handle_click)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 420)
        height = 94
        self.button_regions.clear()

        _rounded_rect(self, 0, 0, width - 1, height - 2, 16, fill=self.row_color, outline=BORDER)
        _rounded_rect(self, 9, 10, 13, height - 12, 3, fill=self.status_color, outline=self.status_color)
        _rounded_rect(self, 22, 12, 100, 40, 12, fill=SURFACE_ELEVATED, outline=BORDER)
        self.create_text(
            61,
            26,
            text=f":{self.port_info.port}",
            fill=TEXT,
            font=("Consolas", 16, "bold"),
        )

        status_width = max(64, tkfont.Font(family="Segoe UI Semibold", size=9).measure(self.status_label) + 20)
        status_left = width - status_width - 14
        _rounded_rect(
            self,
            status_left,
            12,
            width - 14,
            36,
            12,
            fill=self.status_surface,
            outline=self.status_color,
        )
        self.create_text(
            status_left + status_width / 2,
            24,
            text=self.status_label,
            fill=self.status_color,
            font=("Segoe UI Semibold", 9),
        )

        title_font = tkfont.Font(family="Segoe UI Semibold", size=13)
        detail_font = tkfont.Font(family="Segoe UI", size=10)
        muted_font = tkfont.Font(family="Segoe UI", size=9)
        text_left = 112
        text_right = max(text_left + 80, status_left - 12)
        self.create_text(
            text_left,
            16,
            text=_ellipsize_text(self.port_info.process_name, title_font, text_right - text_left),
            fill=TEXT,
            font=title_font,
            anchor="nw",
        )
        self.create_text(
            text_left,
            38,
            text=_ellipsize_text(self._build_runtime_text(self.port_info), detail_font, width - text_left - 24),
            fill=TEXT_SOFT,
            font=detail_font,
            anchor="nw",
        )
        source_path = self.port_info.source_display_path
        source_label = "File" if self.port_info.command_file_path else "Path"
        self.create_text(
            22,
            53,
            text=_ellipsize_text(
                f"{source_label}: {source_path}" if source_path else "No source path resolved",
                muted_font,
                width - 44,
            ),
            fill=TEXT_MUTED,
            font=muted_font,
            anchor="nw",
        )

        self._draw_button("open", "Open", 22, "primary")
        self._draw_button("copy", "Copy", 92, "ghost")
        self._draw_button("source", "Source", 160, "ghost")
        self._draw_button("close", "Close", width - 78, "danger")

    def _draw_button(self, key: str, text: str, x: int, variant: str) -> None:
        width = 58 if text != "Source" else 68
        if key == "close":
            width = 56
        y1, y2 = 67, 89
        fg_color, hover_color, border_color, text_color = _button_colors(variant)
        fill = hover_color if self.hover_button == key else fg_color
        if fill == "transparent":
            fill = self.row_color
        _rounded_rect(self, x, y1, x + width, y2, 10, fill=fill, outline=border_color)
        self.create_text(
            x + width / 2,
            y1 + 12,
            text=text,
            fill=text_color,
            font=("Segoe UI Semibold", 9),
        )
        self.button_regions[key] = (x, y1, x + width, y2)

    def _button_at(self, x: int, y: int) -> str | None:
        for key, (x1, y1, x2, y2) in self.button_regions.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                return key
        return None

    def _handle_motion(self, event) -> None:
        key = self._button_at(event.x, event.y)
        if key != self.hover_button:
            self.hover_button = key
            self.configure(cursor="hand2" if key else "arrow")
            self._draw()

    def _handle_leave(self, _event) -> None:
        if self.hover_button is not None:
            self.hover_button = None
            self.configure(cursor="arrow")
            self._draw()

    def _handle_click(self, event) -> None:
        key = self._button_at(event.x, event.y)
        if key == "open":
            self.on_open(self.port_info)
        elif key == "copy":
            self.on_copy(self.port_info)
        elif key == "source":
            self.on_folder(self.port_info)
        elif key == "close":
            self.on_close(self.port_info)

    def _build_runtime_text(self, port_info: PortInfo) -> str:
        details = [f"PID {port_info.pid}", port_info.status.value]
        if port_info.http_status_code:
            details.append(f"HTTP {port_info.http_status_code}")
        return " | ".join(details)


def _rounded_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int,
    **kwargs,
) -> int:
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=12, **kwargs)


def _ellipsize_text(text: str, font: tkfont.Font, max_width: int) -> str:
    if max_width <= 0 or font.measure(text) <= max_width:
        return text

    ellipsis = "..."
    if font.measure(ellipsis) > max_width:
        return ""

    low = 0
    high = len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if font.measure(text[:middle] + ellipsis) <= max_width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + ellipsis


def _port_chip_background(status: PortStatus) -> str:
    return STATUS_META[status][2]


def _port_chip_text(status: PortStatus) -> str:
    return STATUS_META[status][1]


def _group_path(port_info: PortInfo) -> str:
    path = port_info.project_root or port_info.cwd or port_info.exe_path
    if not path:
        return ""

    normalized = os.path.normpath(path)
    if os.path.isfile(normalized):
        return os.path.dirname(normalized)
    return normalized


def _group_title(port_info: PortInfo, group_path: str) -> str:
    if port_info.project_name and port_info.project_name != "Unknown":
        return port_info.project_name
    if group_path:
        return os.path.basename(group_path) or group_path
    return port_info.process_name or APP_NAME


def _port_sort_key(port_info: PortInfo) -> tuple[int, str, int]:
    order = {
        PortStatus.ACTIVE: 0,
        PortStatus.LISTENING: 1,
        PortStatus.ZOMBIE: 2,
        PortStatus.UNKNOWN: 3,
    }
    return (
        order.get(port_info.status, 99),
        port_info.process_name.lower(),
        port_info.port,
    )
