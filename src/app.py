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
from models import AppState, PortInfo, PortStatus
from utils import APP_NAME, APP_VERSION, get_icon_path, truncate_path

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

CANVAS = "#000000"
SURFACE = "#291C0E"
SURFACE_ALT = "#122324"
SURFACE_RAISED = "#2F3A32"
SURFACE_CARD = "#3E2411"
SURFACE_CARD_ALT = "#545748"
ROW_A = "#122324"
ROW_B = "#2F3A32"
BORDER = "#A78D78"
BORDER_STRONG = "#DB9F75"
TEXT = "#FDE8D3"
TEXT_SOFT = "#DAEBE3"
TEXT_MUTED = "#CFD6C4"
ACCENT = "#DB9F75"
ACCENT_AQUA = "#99CDD8"
ACCENT_MAUVE = "#BEB5A9"
ACCENT_DEEP = "#6E473B"
ACCENT_SAGE = "#657166"
HOVER_WARM = "#F3C3B2"
DANGER = "#804012"
DANGER_DEEP = "#3E2411"

REFRESH_PRESETS_MS = (5000, 10000)

STATUS_META = {
    PortStatus.ACTIVE: ("Active", "#99CDD8", "#122324"),
    PortStatus.LISTENING: ("Listening", "#DB9F75", "#291C0E"),
    PortStatus.ZOMBIE: ("Stuck", "#F3C3B2", "#804012"),
    PortStatus.UNKNOWN: ("Unknown", "#E1D4C2", "#545748"),
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


class EasyLocalhostApp(ctk.CTk):
    """Compact floating desktop window for localhost monitoring."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.configure(fg_color=CANVAS)
        self.minsize(460, 500)
        self.geometry(self._default_geometry())
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_window_icon()

        self.app_state = AppState(scan_interval_ms=7000, always_on_top=True)
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
        self.interval_buttons: dict[int, ctk.CTkButton] = {}

        self._build_layout()
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

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header.grid_columnconfigure(1, weight=1)

        if self.brand_icon is not None:
            icon_label = ctk.CTkLabel(header, text="", image=self.brand_icon)
            icon_label.grid(row=0, column=0, rowspan=3, sticky="w", padx=(0, 12))

        eyebrow = ctk.CTkLabel(
            header,
            text="LOCALHOST CONTROL",
            text_color=ACCENT,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        )
        eyebrow.grid(row=0, column=1, sticky="w")

        title_label = ctk.CTkLabel(
            header,
            text=APP_NAME,
            text_color=TEXT,
            font=("Segoe UI Semibold", 29),
            anchor="w",
        )
        title_label.grid(row=1, column=1, sticky="w", pady=(0, 1))

        subtitle = ctk.CTkLabel(
            header,
            text="Grouped folders, stable scroll, manual control.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 13),
            anchor="w",
        )
        subtitle.grid(row=2, column=1, sticky="w", pady=(8, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=3, sticky="e")
        for column in range(2):
            actions.grid_columnconfigure(column, weight=1)

        self.topmost_button = self._make_header_button(
            actions,
            "Pinned",
            0,
            self.toggle_topmost,
            active=True,
        )
        self._make_header_button(
            actions,
            "Reload",
            1,
            lambda: self.request_refresh(immediate=True),
        )

        for index, interval_ms in enumerate(REFRESH_PRESETS_MS):
            button = self._make_interval_button(actions, interval_ms, index)
            self.interval_buttons[interval_ms] = button
        self._sync_interval_buttons()

        self._make_compact_button(actions, "Expand all", 0, self.expand_all_groups)
        self._make_compact_button(actions, "Collapse all", 1, self.collapse_all_groups)

        summary = ctk.CTkFrame(
            shell,
            fg_color=SURFACE,
            corner_radius=28,
            border_width=1,
            border_color=BORDER_STRONG,
        )
        summary.grid(row=1, column=0, sticky="ew", padx=20)
        summary.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(
            summary,
            text="Scanning localhost ports...",
            text_color=TEXT,
            font=("Segoe UI Semibold", 14),
            padx=17,
            pady=14,
            anchor="w",
        )
        self.summary_label.grid(row=0, column=0, sticky="w")

        self.updated_label = ctk.CTkLabel(
            summary,
            text="Waiting",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            padx=17,
            pady=14,
            anchor="e",
        )
        self.updated_label.grid(row=0, column=1, sticky="e")

        self.port_cards_frame = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color=ACCENT_DEEP,
            scrollbar_button_hover_color=BORDER_STRONG,
        )
        self.port_cards_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(14, 14))
        self.port_cards_frame.grid_columnconfigure(0, weight=1)

        footer = ctk.CTkFrame(
            shell,
            fg_color=SURFACE_CARD,
            corner_radius=22,
            border_width=1,
            border_color=BORDER,
        )
        footer.grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            footer,
            text="Ready",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            padx=14,
            pady=11,
        )
        self.status_label.grid(row=0, column=0, sticky="ew")

    def _make_header_button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        column: int,
        command,
        *,
        active: bool = False,
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            width=86,
            height=35,
            corner_radius=18,
            fg_color=ACCENT if active else SURFACE_CARD,
            hover_color=HOVER_WARM if active else SURFACE_CARD_ALT,
            border_width=1,
            border_color=ACCENT if active else BORDER,
            text_color=CANVAS if active else TEXT_SOFT,
            font=("Segoe UI Semibold", 12),
            command=command,
        )
        button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0))
        return button

    def _make_interval_button(
        self,
        parent: ctk.CTkFrame,
        interval_ms: int,
        column: int,
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=f"{interval_ms // 1000}s",
            width=86,
            height=30,
            corner_radius=15,
            fg_color=SURFACE_CARD,
            hover_color=SURFACE_CARD_ALT,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SOFT,
            font=("Segoe UI Semibold", 11),
            command=lambda: self.set_refresh_interval(interval_ms),
        )
        button.grid(row=1, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=(8, 0))
        return button

    def _make_compact_button(
        self,
        parent: ctk.CTkFrame,
        text: str,
        column: int,
        command,
    ) -> ctk.CTkButton:
        button = ctk.CTkButton(
            parent,
            text=text,
            width=86,
            height=29,
            corner_radius=15,
            fg_color=ACCENT_DEEP,
            hover_color=ACCENT_MAUVE,
            border_width=1,
            border_color=ACCENT_AQUA,
            text_color=TEXT_SOFT,
            font=("Segoe UI Semibold", 10),
            command=command,
        )
        button.grid(row=2, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=(8, 0))
        return button

    def toggle_topmost(self) -> None:
        self.app_state.always_on_top = not self.app_state.always_on_top
        self.attributes("-topmost", self.app_state.always_on_top)
        if self.topmost_button:
            self.topmost_button.configure(
                text="Pinned" if self.app_state.always_on_top else "Unpinned",
                fg_color=ACCENT if self.app_state.always_on_top else SURFACE_CARD,
                hover_color=HOVER_WARM if self.app_state.always_on_top else SURFACE_CARD_ALT,
                border_color=ACCENT if self.app_state.always_on_top else BORDER,
                text_color=CANVAS if self.app_state.always_on_top else TEXT_SOFT,
            )

    def set_refresh_interval(self, interval_ms: int) -> None:
        self.app_state.scan_interval_ms = interval_ms
        self._sync_interval_buttons()
        self._queue_next_refresh(force=True)
        self._set_status(f"Auto refresh set to {interval_ms // 1000}s.")

    def _sync_interval_buttons(self) -> None:
        for interval_ms, button in self.interval_buttons.items():
            active = interval_ms == self.app_state.scan_interval_ms
            button.configure(
                fg_color=ACCENT if active else SURFACE_CARD,
                hover_color=HOVER_WARM if active else SURFACE_CARD_ALT,
                border_color=ACCENT if active else BORDER,
                text_color=CANVAS if active else TEXT_SOFT,
            )

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
        delay = 250 if force else self.app_state.scan_interval_ms
        if self.refresh_job is not None:
            self.after_cancel(self.refresh_job)
        self.refresh_job = self.after(delay, self.request_refresh)

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
                f"Auto refresh: {self.app_state.scan_interval_ms // 1000}s."
            )
        else:
            self._set_status("No localhost processes detected.")

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
        for group in groups:
            if group.key not in self.known_groups:
                if group.active_count > 0:
                    self.expanded_groups.add(group.key)
                self.known_groups.add(group.key)

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
            group_widget.grid(row=row_index, column=0, sticky="ew", pady=(0, 12))

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
        title.grid(row=0, column=0, pady=(28, 8), padx=20)

        detail = ctk.CTkLabel(
            frame,
            text="Launch a local dev server and it will appear here automatically.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 13),
            wraplength=340,
            justify="center",
        )
        detail.grid(row=1, column=0, pady=(0, 28), padx=20)
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
        width = 520
        height = 720
        margin = 26
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
            return ctk.CTkImage(light_image=image, dark_image=image, size=(46, 46))
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
        super().__init__(
            master,
            fg_color=SURFACE_CARD,
            corner_radius=30,
            border_width=1,
            border_color=BORDER_STRONG if expanded else BORDER,
        )
        self.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 12))
        header.grid_columnconfigure(1, weight=1)

        toggle = ctk.CTkButton(
            header,
            text="-" if expanded else "+",
            width=34,
            height=34,
            corner_radius=17,
            fg_color=ACCENT if expanded else SURFACE_RAISED,
            hover_color=HOVER_WARM,
            text_color=CANVAS if expanded else TEXT_SOFT,
            command=lambda: on_toggle(group.key),
        )
        toggle.grid(row=0, column=0, sticky="w", padx=(0, 10))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.grid(row=0, column=1, sticky="ew")
        title_block.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            title_block,
            text=group.title,
            text_color=TEXT,
            font=("Segoe UI Semibold", 16),
            anchor="w",
        )
        title.grid(row=0, column=0, sticky="ew")

        path_label = ctk.CTkLabel(
            title_block,
            text=truncate_path(group.path, 58) if group.path else "No folder resolved",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            anchor="w",
        )
        path_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))

        stats = ctk.CTkLabel(
            header,
            text=f"{len(group.ports)} ports / {group.active_count} active",
            text_color=ACCENT,
            fg_color=ACCENT_DEEP,
            corner_radius=15,
            font=("Segoe UI Semibold", 11),
            padx=10,
            pady=6,
        )
        stats.grid(row=0, column=2, sticky="e", padx=(10, 8))

        folder_button = ctk.CTkButton(
            header,
            text="Folder",
            width=70,
            height=32,
            corner_radius=16,
            fg_color=SURFACE_RAISED,
            hover_color=SURFACE_CARD_ALT,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT_SOFT,
            font=("Segoe UI Semibold", 11),
            command=lambda: on_group_folder(group.path),
            state="normal" if group.path else "disabled",
        )
        folder_button.grid(row=0, column=3, sticky="e")

        if expanded:
            body = ctk.CTkFrame(self, fg_color="transparent")
            body.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
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
    """Single compact card representing one localhost process."""

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
        row_color = ROW_A if row_index % 2 == 0 else ROW_B
        super().__init__(
            master,
            fg_color=row_color,
            corner_radius=18,
            border_width=1,
            border_color=status_color,
        )

        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        status_bar = ctk.CTkFrame(
            self,
            width=7,
            corner_radius=7,
            fg_color=status_color,
        )
        status_bar.grid(row=0, column=0, rowspan=5, sticky="nsw", padx=(9, 0), pady=9)
        status_bar.grid_propagate(False)

        port_badge = ctk.CTkLabel(
            self,
            text=f":{port_info.port}",
            text_color=CANVAS,
            fg_color=ACCENT,
            corner_radius=18,
            font=("Consolas", 18, "bold"),
            padx=12,
            pady=8,
        )
        port_badge.grid(row=0, column=1, sticky="w", padx=(18, 10), pady=(11, 4))

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
        process_line.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(18, 12))

        details = self._build_runtime_text(port_info)
        detail_line = ctk.CTkLabel(
            self,
            text=details,
            text_color=TEXT_SOFT,
            font=("Segoe UI", 12),
            anchor="w",
        )
        detail_line.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(18, 12), pady=(1, 5))

        path_line = ctk.CTkLabel(
            self,
            text=truncate_path(port_info.launch_path or port_info.cwd or port_info.exe_path, 64)
            or "No source path resolved",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 11),
            anchor="w",
            justify="left",
            wraplength=430,
        )
        path_line.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(18, 12), pady=(0, 9))

        commands = ctk.CTkFrame(self, fg_color="transparent")
        commands.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(18, 12), pady=(0, 11))
        for index in range(4):
            commands.grid_columnconfigure(index, weight=1)

        self._make_button(commands, "Open", 0, lambda: on_open(port_info), filled=True)
        self._make_button(commands, "Copy", 1, lambda: on_copy(port_info), color="aqua")
        self._make_button(commands, "Source", 2, lambda: on_folder(port_info), color="sage")
        self._make_button(commands, "Close", 3, lambda: on_close(port_info), danger=True)

    def _make_button(
        self,
        parent,
        text: str,
        column: int,
        command,
        *,
        filled: bool = False,
        danger: bool = False,
        color: str = "default",
    ) -> None:
        fg_color = SURFACE_CARD_ALT
        hover_color = ACCENT_MAUVE
        border_color = ACCENT_AQUA
        text_color = TEXT_SOFT
        if filled:
            fg_color = ACCENT
            hover_color = HOVER_WARM
            border_color = ACCENT
            text_color = CANVAS
        elif color == "aqua":
            fg_color = ACCENT_SAGE
            hover_color = ACCENT_AQUA
            border_color = ACCENT_AQUA
            text_color = TEXT_SOFT
        elif color == "sage":
            fg_color = SURFACE_RAISED
            hover_color = ACCENT_SAGE
            border_color = ACCENT_SAGE
            text_color = TEXT_SOFT
        if danger:
            fg_color = DANGER_DEEP
            hover_color = DANGER
            border_color = DANGER
            text_color = "#FDE8D3"

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
        return " / ".join(details)

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
    return port_info.process_name or "Unknown"


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
