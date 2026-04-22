"""
Desktop UI for Easy Localhost.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import logging
import os
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from actions import ActionResult, kill_process_tree, open_in_browser, open_in_folder
from controller import LocalhostController, ScanResult
from models import AppState, PortInfo, PortStatus, RefreshMode, next_refresh_mode
from presentation_state import merge_new_group_expansion, summarize_port_chips
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
        self.title(f"{APP_DISPLAY_NAME} - {APP_VERSION}")
        self.configure(fg_color=CANVAS)
        self.minsize(500, 560)
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

        self.brand_icon = self._load_brand_icon()
        self.port_cards_frame: ctk.CTkScrollableFrame | None = None
        self.summary_label: ctk.CTkLabel | None = None
        self.updated_label: ctk.CTkLabel | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.topmost_button: ctk.CTkButton | None = None
        self.refresh_mode_button: ctk.CTkButton | None = None

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
            corner_radius=32,
            border_width=1,
            border_color=BORDER_STRONG,
        )
        hero.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 12))
        hero.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(hero, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=18, pady=18)
        header.grid_columnconfigure(1, weight=1)

        if self.brand_icon is not None:
            icon_label = ctk.CTkLabel(header, text="", image=self.brand_icon)
            icon_label.grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 14))

        meta_line = ctk.CTkFrame(header, fg_color="transparent")
        meta_line.grid(row=0, column=1, sticky="w")

        eyebrow = ctk.CTkLabel(
            meta_line,
            text="LOCALHOST CONTROL",
            text_color=ACCENT,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        )
        eyebrow.grid(row=0, column=0, sticky="w")

        version_chip = ctk.CTkLabel(
            meta_line,
            text=f"v{APP_VERSION}",
            text_color=ACCENT,
            fg_color=ACCENT_DEEP,
            corner_radius=12,
            padx=10,
            pady=4,
            font=("Segoe UI Semibold", 10),
        )
        version_chip.grid(row=0, column=1, sticky="w", padx=(8, 0))

        title_label = ctk.CTkLabel(
            header,
            text=APP_DISPLAY_NAME,
            text_color=TEXT,
            font=("Segoe UI Semibold", 28),
            anchor="w",
        )
        title_label.grid(row=1, column=1, sticky="w", pady=(2, 0))

        subtitle = ctk.CTkLabel(
            header,
            text="Compact control for localhost sessions.",
            text_color=TEXT_SOFT,
            font=("Segoe UI", 13),
            anchor="w",
        )
        subtitle.grid(row=2, column=1, sticky="w", pady=(8, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=3, sticky="e")
        for column in range(2):
            actions.grid_columnconfigure(column, weight=1)

        self.topmost_button = self._make_button(
            actions,
            text="Pinned",
            row=0,
            column=0,
            command=self.toggle_topmost,
            variant="primary",
        )
        self._make_button(
            actions,
            text="Reload",
            row=0,
            column=1,
            command=lambda: self.request_refresh(immediate=True),
            variant="secondary",
        )
        self.refresh_mode_button = self._make_button(
            actions,
            text=self.app_state.refresh_button_text,
            row=1,
            column=0,
            columnspan=2,
            command=self.cycle_refresh_mode,
            variant="accent",
            height=34,
        )
        self._make_button(
            actions,
            text="Expand all",
            row=2,
            column=0,
            command=self.expand_all_groups,
            variant="ghost",
            height=30,
            font_size=10,
        )
        self._make_button(
            actions,
            text="Collapse all",
            row=2,
            column=1,
            command=self.collapse_all_groups,
            variant="ghost",
            height=30,
            font_size=10,
        )

        summary = ctk.CTkFrame(
            shell,
            fg_color=SURFACE_ELEVATED,
            corner_radius=24,
            border_width=1,
            border_color=BORDER,
        )
        summary.grid(row=1, column=0, sticky="ew", padx=18)
        summary.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(
            summary,
            text="Scanning localhost ports...",
            text_color=TEXT,
            font=("Segoe UI Semibold", 14),
            padx=16,
            pady=14,
            anchor="w",
        )
        self.summary_label.grid(row=0, column=0, sticky="w")

        self.updated_label = ctk.CTkLabel(
            summary,
            text="Waiting",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            padx=16,
            pady=14,
            anchor="e",
        )
        self.updated_label.grid(row=0, column=1, sticky="e")

        self.port_cards_frame = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=SURFACE_TINT,
            scrollbar_button_hover_color=ACCENT,
        )
        self.port_cards_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(14, 14))
        self.port_cards_frame.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(
            shell,
            fg_color=SURFACE,
            corner_radius=22,
            border_width=1,
            border_color=BORDER,
        )
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            padx=14,
            pady=10,
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
        button.grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=(0 if column == 0 else 8, 0),
            pady=(0 if row == 0 else 8, 0),
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
        self._render_groups(groups, self._get_scroll_position())
        self._set_status("All folders expanded.")

    def collapse_all_groups(self) -> None:
        self.expanded_groups.clear()
        self._render_groups(self._group_ports(self.app_state.ports), self._get_scroll_position())
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
            self._render_groups(groups, restore_scroll=scroll_position)

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
        self.expanded_groups, self.known_groups = merge_new_group_expansion(
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

        for child in self.port_cards_frame.winfo_children():
            child.destroy()

        if not groups:
            empty_state = self._build_empty_state(self.port_cards_frame)
            empty_state.grid(row=0, column=0, sticky="ew", pady=(8, 0))
            return

        for row_index, group in enumerate(groups):
            group_widget = PortGroup(
                self.port_cards_frame,
                group=group,
                expanded=group.key in self.expanded_groups,
                on_toggle=self._toggle_group,
                on_open=self._handle_open,
                on_copy=self._handle_copy,
                on_folder=self._handle_folder,
                on_group_folder=self._handle_group_folder,
                on_close=self._handle_close,
            )
            group_widget.grid(row=row_index, column=0, sticky="ew", pady=(0, 10))

        if restore_scroll is not None:
            self.after(40, lambda: self._restore_scroll_position(restore_scroll))

    def _toggle_group(self, group_key: str) -> None:
        if group_key in self.expanded_groups:
            self.expanded_groups.remove(group_key)
        else:
            self.expanded_groups.add(group_key)
        self._render_groups(self._group_ports(self.app_state.ports), self._get_scroll_position())

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
        width = 580
        height = 760
        margin = 24
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

    def _set_window_icon(self) -> None:
        try:
            self.iconbitmap(get_icon_path("ico"))
        except Exception as exc:
            logger.debug("Could not set window icon: %s", exc)

    def _load_brand_icon(self) -> ctk.CTkImage | None:
        try:
            image = Image.open(get_icon_path("png"))
            return ctk.CTkImage(light_image=image, dark_image=image, size=(42, 42))
        except Exception as exc:
            logger.debug("Could not load brand icon: %s", exc)
            return None

    def _on_close(self) -> None:
        try:
            if self.refresh_job is not None:
                self.after_cancel(self.refresh_job)
            self.executor.shutdown(wait=False, cancel_futures=True)
        finally:
            self.destroy()


class PortGroup(ctk.CTkFrame):
    """Collapsible folder/project group."""

    def __init__(
        self,
        master,
        group: PortGroupData,
        expanded: bool,
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
            corner_radius=28,
            border_width=1,
            border_color=border_color,
        )
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 12))
        header.grid_columnconfigure(1, weight=1)

        toggle_pill = ctk.CTkFrame(
            header,
            fg_color=ACCENT_DEEP if group.active_count > 0 else SURFACE_ROW,
            corner_radius=15,
            border_width=1,
            border_color=ACCENT if expanded and group.active_count > 0 else BORDER_STRONG,
            width=34,
            height=34,
        )
        toggle_pill.grid(row=0, column=0, sticky="w", padx=(0, 10))
        toggle_pill.grid_propagate(False)

        toggle_icon = ctk.CTkLabel(
            toggle_pill,
            text="▾" if expanded else "▸",
            text_color=ACCENT if group.active_count > 0 else TEXT_SOFT,
            font=("Segoe UI Semibold", 15),
        )
        toggle_icon.place(relx=0.5, rely=0.5, anchor="center")

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
            font=("Segoe UI Semibold", 16),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="w")

        stats = ctk.CTkLabel(
            top_line,
            text=f"{len(group.ports)} localhost | {group.active_count} active",
            text_color=ACCENT if group.active_count > 0 else TEXT_SOFT,
            fg_color=ACCENT_DEEP if group.active_count > 0 else SURFACE_ROW,
            corner_radius=14,
            font=("Segoe UI Semibold", 10),
            padx=10,
            pady=5,
        )
        stats.grid(row=0, column=1, sticky="e", padx=(10, 0))

        detail_line = ctk.CTkFrame(info, fg_color="transparent")
        detail_line.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        detail_line.grid_columnconfigure(0, weight=1)

        path_label = ctk.CTkLabel(
            detail_line,
            text=truncate_path(group.path, 56) if group.path else "No folder resolved",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
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
                corner_radius=11,
                font=("Consolas", 10, "bold"),
                padx=8,
                pady=4,
            )
            chip.grid(row=0, column=index, sticky="e", padx=(6 if index else 0, 0))
            chip_widgets.append(chip)

        folder_fg, folder_hover, folder_border, folder_text = _button_colors("ghost")
        folder_button = ctk.CTkButton(
            header,
            text="Folder",
            width=74,
            height=32,
            corner_radius=16,
            fg_color=folder_fg,
            hover_color=folder_hover,
            border_width=1,
            border_color=folder_border,
            text_color=folder_text,
            font=("Segoe UI Semibold", 11),
            command=lambda: on_group_folder(group.path),
            state="normal" if group.path else "disabled",
        )
        folder_button.grid(row=0, column=2, sticky="e", padx=(12, 0))

        _bind_left_click(
            [header, toggle_pill, toggle_icon, info, top_line, title, stats, detail_line, path_label, chips, *chip_widgets],
            lambda: on_toggle(group.key),
        )

        if expanded:
            body = ctk.CTkFrame(self, fg_color="transparent")
            body.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
            body.grid_columnconfigure(0, weight=1)

            for row_index, port in enumerate(group.ports):
                card = PortCard(
                    body,
                    port_info=port,
                    row_index=row_index,
                    on_open=on_open,
                    on_copy=on_copy,
                    on_folder=on_folder,
                    on_close=on_close,
                )
                card.grid(row=row_index, column=0, sticky="ew", pady=(0, 8))


class PortCard(ctk.CTkFrame):
    """Single compact row representing one localhost process."""

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
        super().__init__(
            master,
            fg_color=row_color,
            corner_radius=20,
            border_width=1,
            border_color=BORDER,
        )

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        status_bar = ctk.CTkFrame(
            self,
            width=5,
            corner_radius=4,
            fg_color=status_color,
        )
        status_bar.grid(row=0, column=0, rowspan=5, sticky="nsw", padx=(9, 0), pady=10)
        status_bar.grid_propagate(False)

        port_badge = ctk.CTkFrame(
            self,
            fg_color=SURFACE_ELEVATED,
            corner_radius=17,
            border_width=1,
            border_color=status_color,
        )
        port_badge.grid(row=0, column=1, sticky="w", padx=(16, 10), pady=(11, 4))

        port_badge_label = ctk.CTkLabel(
            port_badge,
            text=f":{port_info.port}",
            text_color=TEXT,
            fg_color="transparent",
            font=("Consolas", 18, "bold"),
            padx=12,
            pady=7,
        )
        port_badge_label.grid(row=0, column=0)

        status_badge = ctk.CTkFrame(
            self,
            fg_color=status_surface,
            corner_radius=14,
            border_width=1,
            border_color=status_color,
        )
        status_badge.grid(row=0, column=2, sticky="e", padx=(0, 12), pady=(11, 4))

        status_badge_label = ctk.CTkLabel(
            status_badge,
            text=status_label,
            text_color=status_color,
            fg_color="transparent",
            font=("Segoe UI Semibold", 11),
            padx=9,
            pady=5,
        )
        status_badge_label.grid(row=0, column=0)

        process_line = ctk.CTkLabel(
            self,
            text=port_info.process_name,
            text_color=TEXT,
            font=("Segoe UI Semibold", 15),
            anchor="w",
        )
        process_line.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(16, 12))

        details = self._build_runtime_text(port_info)
        detail_line = ctk.CTkLabel(
            self,
            text=details,
            text_color=TEXT_SOFT,
            font=("Segoe UI", 12),
            anchor="w",
        )
        detail_line.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(16, 12), pady=(2, 5))

        path_line = ctk.CTkLabel(
            self,
            text=truncate_path(port_info.launch_path or port_info.cwd or port_info.exe_path, 68)
            or "No source path resolved",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
            wraplength=440,
        )
        path_line.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(16, 12), pady=(0, 9))

        commands = ctk.CTkFrame(self, fg_color="transparent")
        commands.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(16, 12), pady=(0, 11))
        for index in range(4):
            commands.grid_columnconfigure(index, weight=1)

        self._make_button(commands, "Open", 0, lambda: on_open(port_info), "primary")
        self._make_button(commands, "Copy", 1, lambda: on_copy(port_info), "ghost")
        self._make_button(commands, "Source", 2, lambda: on_folder(port_info), "ghost")
        self._make_button(commands, "Close", 3, lambda: on_close(port_info), "danger")

    def _make_button(self, parent, text: str, column: int, command, variant: str) -> None:
        fg_color, hover_color, border_color, text_color = _button_colors(variant)
        button = ctk.CTkButton(
            parent,
            text=text,
            height=31,
            corner_radius=15,
            fg_color=fg_color,
            hover_color=hover_color,
            border_width=1,
            border_color=border_color,
            text_color=text_color,
            font=("Segoe UI Semibold", 11),
            command=command,
        )
        button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 7, 0))

    def _build_runtime_text(self, port_info: PortInfo) -> str:
        details = [f"PID {port_info.pid}", port_info.status.value]
        if port_info.http_status_code:
            details.append(f"HTTP {port_info.http_status_code}")
        return " | ".join(details)


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
