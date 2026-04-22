"""
Desktop UI for Easy Localhost.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import logging
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from actions import ActionResult, kill_process_tree, open_in_browser, open_in_folder
from controller import LocalhostController, ScanResult
from models import AppState, PortInfo, PortStatus
from utils import APP_NAME, APP_VERSION, get_icon_path, truncate_path

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

CANVAS = "#000000"
SURFACE = "#190019"
SURFACE_ALT = "#181A2F"
SURFACE_RAISED = "#242E49"
SURFACE_CARD = "#0A050D"
SURFACE_CARD_ALT = "#2B124C"
BORDER = "#522B5B"
BORDER_STRONG = "#6E3482"
TEXT = "#FBE4D8"
TEXT_SOFT = "#E7DBEF"
TEXT_MUTED = "#DFB6B2"
ACCENT = "#FDA481"
ACCENT_ALT = "#A56ABD"
ACCENT_DEEP = "#49225B"
DANGER = "#B4182D"
DANGER_DEEP = "#54162B"

STATUS_META = {
    PortStatus.ACTIVE: ("Active", "#8FF0B7", "#0B2A19"),
    PortStatus.LISTENING: ("Listening", ACCENT, "#3A1C1A"),
    PortStatus.ZOMBIE: ("Stuck", "#FF6B7A", DANGER_DEEP),
    PortStatus.UNKNOWN: ("Unknown", TEXT_SOFT, SURFACE_RAISED),
}


class EasyLocalhostApp(ctk.CTk):
    """Compact floating desktop window for localhost monitoring."""

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.configure(fg_color=CANVAS)
        self.minsize(430, 460)
        self.geometry(self._default_geometry())
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_window_icon()

        self.app_state = AppState(scan_interval_ms=1800, always_on_top=True)
        self.controller = LocalhostController()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")
        self.scan_future: Future[ScanResult] | None = None
        self.pending_refresh = False
        self.refresh_job: str | None = None
        self.last_signature: tuple[tuple[int, int, str, str, str, int | None], ...] = ()

        self.brand_icon = self._load_brand_icon()
        self.port_cards_frame: ctk.CTkScrollableFrame | None = None
        self.summary_label: ctk.CTkLabel | None = None
        self.updated_label: ctk.CTkLabel | None = None
        self.status_label: ctk.CTkLabel | None = None
        self.topmost_button: ctk.CTkButton | None = None
        self.empty_state: ctk.CTkFrame | None = None

        self._build_layout()
        self.bind("<F5>", lambda _event: self.request_refresh(immediate=True))
        self.after(120, lambda: self.request_refresh(immediate=True))
        self.after(125, self._poll_scan_future)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        shell = ctk.CTkFrame(
            self,
            fg_color=CANVAS,
            corner_radius=0,
        )
        shell.grid(row=0, column=0, sticky="nsew")
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(shell, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 12))
        header.grid_columnconfigure(1, weight=1)

        if self.brand_icon is not None:
            icon_label = ctk.CTkLabel(header, text="", image=self.brand_icon)
            icon_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))

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
            text="Live ports, project origin, quick actions.",
            text_color=TEXT_MUTED,
            font=("Segoe UI", 13),
            anchor="w",
        )
        subtitle.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.grid(row=0, column=2, rowspan=3, sticky="e")

        self.topmost_button = self._make_header_button(
            actions,
            "Pinned",
            0,
            self.toggle_topmost,
            active=True,
        )
        self._make_header_button(
            actions,
            "Refresh",
            1,
            lambda: self.request_refresh(immediate=True),
        )

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
            width=90,
            height=36,
            corner_radius=18,
            fg_color=ACCENT if active else SURFACE_CARD,
            hover_color="#E58C6D" if active else SURFACE_CARD_ALT,
            border_width=1,
            border_color=ACCENT if active else BORDER,
            text_color=CANVAS if active else TEXT_SOFT,
            font=("Segoe UI Semibold", 12),
            command=command,
        )
        button.grid(row=0, column=column, padx=(0 if column == 0 else 8, 0))
        return button

    def toggle_topmost(self) -> None:
        self.app_state.always_on_top = not self.app_state.always_on_top
        self.attributes("-topmost", self.app_state.always_on_top)
        if self.topmost_button:
            self.topmost_button.configure(
                text="Pinned" if self.app_state.always_on_top else "Unpinned",
                fg_color=ACCENT if self.app_state.always_on_top else SURFACE_CARD,
                hover_color="#E58C6D" if self.app_state.always_on_top else SURFACE_CARD_ALT,
                border_color=ACCENT if self.app_state.always_on_top else BORDER,
                text_color=CANVAS if self.app_state.always_on_top else TEXT_SOFT,
            )

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
        self.app_state.ports = ordered_ports
        self.app_state.last_scan_time = result.scanned_at
        self.app_state.total_scans += 1

        active = sum(1 for item in ordered_ports if item.status is PortStatus.ACTIVE)
        summary = f"{len(ordered_ports)} localhost | {active} active | {result.elapsed_ms:.0f} ms"
        updated = datetime.fromtimestamp(result.scanned_at).strftime("%H:%M:%S")

        if self.summary_label:
            self.summary_label.configure(text=summary)
        if self.updated_label:
            self.updated_label.configure(text=f"Updated {updated}")

        signature = tuple(
            (
                port.port,
                port.pid,
                port.status.value,
                port.display_name,
                port.launch_path,
                port.http_status_code,
            )
            for port in ordered_ports
        )
        if signature != self.last_signature:
            self.last_signature = signature
            self._render_ports(ordered_ports)

        if ordered_ports:
            self._set_status(f"Watching {len(ordered_ports)} localhost processes.")
        else:
            self._set_status("No localhost processes detected.")

    def _render_ports(self, ports: list[PortInfo]) -> None:
        if not self.port_cards_frame:
            return

        for child in self.port_cards_frame.winfo_children():
            child.destroy()

        if not ports:
            self.empty_state = self._build_empty_state(self.port_cards_frame)
            self.empty_state.grid(row=0, column=0, sticky="ew", pady=(8, 0))
            return

        self.empty_state = None
        for row_index, port in enumerate(ports):
            card = PortCard(
                self.port_cards_frame,
                port_info=port,
                on_open=self._handle_open,
                on_copy=self._handle_copy,
                on_folder=self._handle_folder,
                on_close=self._handle_close,
            )
            card.grid(row=row_index, column=0, sticky="ew", pady=(0, 12))

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
            wraplength=330,
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

    def _handle_close(self, port_info: PortInfo) -> None:
        answer = messagebox.askyesno(
            "Close localhost",
            f"Close {port_info.display_name} on :{port_info.port}?",
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
        width = 490
        height = 660
        margin = 26
        x = max(self.winfo_screenwidth() - width - margin, margin)
        y = margin
        return f"{width}x{height}+{x}+{y}"

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


class PortCard(ctk.CTkFrame):
    """Single compact card representing one localhost process."""

    def __init__(
        self,
        master,
        port_info: PortInfo,
        on_open,
        on_copy,
        on_folder,
        on_close,
    ) -> None:
        status_label, status_color, status_surface = STATUS_META[port_info.status]
        super().__init__(
            master,
            fg_color=SURFACE_CARD,
            corner_radius=30,
            border_width=1,
            border_color=BORDER,
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(16, 9))
        header.grid_columnconfigure(0, weight=1)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        dot = ctk.CTkLabel(
            left,
            text="●",
            text_color=status_color,
            font=("Segoe UI Symbol", 18),
        )
        dot.grid(row=0, column=0, sticky="w", padx=(0, 8))

        name = ctk.CTkLabel(
            left,
            text=port_info.display_name,
            text_color=TEXT,
            font=("Segoe UI Semibold", 16),
        )
        name.grid(row=0, column=1, sticky="w")

        port_badge = ctk.CTkLabel(
            header,
            text=f":{port_info.port}",
            text_color=TEXT,
            fg_color=SURFACE_CARD_ALT,
            corner_radius=16,
            border_width=1,
            border_color=BORDER_STRONG,
            font=("Consolas", 12),
            padx=11,
            pady=6,
        )
        port_badge.grid(row=0, column=1, sticky="e")

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16)
        meta.grid_columnconfigure(1, weight=1)

        status_badge = ctk.CTkLabel(
            meta,
            text=status_label,
            text_color=status_color,
            fg_color=status_surface,
            corner_radius=16,
            border_width=1,
            border_color=status_color,
            font=("Segoe UI Semibold", 11),
            padx=9,
            pady=5,
        )
        status_badge.grid(row=0, column=0, sticky="w")

        runtime = ctk.CTkLabel(
            meta,
            text=self._build_runtime_text(port_info),
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            anchor="w",
        )
        runtime.grid(row=0, column=1, sticky="w", padx=(11, 0))

        location = ctk.CTkLabel(
            self,
            text=truncate_path(port_info.launch_path or port_info.cwd or port_info.exe_path, 56),
            text_color=TEXT_MUTED,
            font=("Segoe UI", 12),
            anchor="w",
            justify="left",
            wraplength=420,
        )
        location.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(9, 8))

        commands = ctk.CTkFrame(self, fg_color="transparent")
        commands.grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        for index in range(4):
            commands.grid_columnconfigure(index, weight=1)

        self._make_button(commands, "Open", 0, lambda: on_open(port_info), filled=True)
        self._make_button(commands, "Copy", 1, lambda: on_copy(port_info))
        self._make_button(commands, "Source", 2, lambda: on_folder(port_info))
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
    ) -> None:
        fg_color = ACCENT if filled else SURFACE_RAISED
        hover_color = "#E58C6D" if filled else SURFACE_CARD_ALT
        border_color = ACCENT if filled else BORDER
        text_color = CANVAS if filled else TEXT_SOFT
        if danger:
            fg_color = DANGER_DEEP
            hover_color = DANGER
            border_color = DANGER
            text_color = "#FFD7D7"

        button = ctk.CTkButton(
            parent,
            text=text,
            height=34,
            corner_radius=17,
            fg_color=fg_color,
            hover_color=hover_color,
            border_width=1,
            border_color=border_color,
            text_color=text_color,
            font=("Segoe UI Semibold", 12),
            command=command,
        )
        button.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 7, 0))

    def _build_runtime_text(self, port_info: PortInfo) -> str:
        details = [port_info.process_name]
        if port_info.http_status_code:
            details.append(f"HTTP {port_info.http_status_code}")
        return " • ".join(details)


def _port_sort_key(port_info: PortInfo) -> tuple[int, str, int]:
    order = {
        PortStatus.ACTIVE: 0,
        PortStatus.LISTENING: 1,
        PortStatus.ZOMBIE: 2,
        PortStatus.UNKNOWN: 3,
    }
    return (
        order.get(port_info.status, 99),
        port_info.display_name.lower(),
        port_info.port,
    )
