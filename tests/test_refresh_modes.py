import os
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import (
    AppState,
    PortInfo,
    PortStatus,
    RefreshMode,
    next_refresh_mode,
    refresh_interval_for_mode,
)
from presentation_state import merge_group_visibility_state, summarize_port_chips


class RefreshModeTests(unittest.TestCase):
    def test_cycles_in_expected_ui_order(self) -> None:
        mode = RefreshMode.AUTO
        mode = next_refresh_mode(mode)
        self.assertEqual(mode, RefreshMode.FIXED_10S)
        mode = next_refresh_mode(mode)
        self.assertEqual(mode, RefreshMode.FIXED_5S)
        mode = next_refresh_mode(mode)
        self.assertEqual(mode, RefreshMode.MANUAL)
        mode = next_refresh_mode(mode)
        self.assertEqual(mode, RefreshMode.AUTO)

    def test_returns_expected_intervals(self) -> None:
        self.assertEqual(refresh_interval_for_mode(RefreshMode.AUTO), 7000)
        self.assertEqual(refresh_interval_for_mode(RefreshMode.FIXED_10S), 10000)
        self.assertEqual(refresh_interval_for_mode(RefreshMode.FIXED_5S), 5000)
        self.assertIsNone(refresh_interval_for_mode(RefreshMode.MANUAL))

    def test_app_state_exposes_refresh_text(self) -> None:
        state = AppState(refresh_mode=RefreshMode.MANUAL)
        self.assertEqual(state.refresh_button_text, "Refresh: Manual")
        self.assertEqual(state.refresh_status_text, "Manual")
        self.assertIsNone(state.scan_interval_ms)


class PresentationStateTests(unittest.TestCase):
    def test_keeps_new_groups_collapsed_by_default(self) -> None:
        expanded, known = merge_group_visibility_state(
            expanded_groups={"existing"},
            known_groups={"existing"},
            groups=(
                ("existing", 2),
                ("active-new", 1),
                ("listening-new", 0),
            ),
        )
        self.assertEqual(expanded, {"existing"})
        self.assertEqual(known, {"existing", "active-new", "listening-new"})

    def test_summarizes_group_ports_with_three_chip_limit(self) -> None:
        ports = [
            PortInfo(3000, 1, "node.exe", "", "", "demo", PortStatus.ACTIVE),
            PortInfo(5173, 2, "node.exe", "", "", "demo", PortStatus.ACTIVE),
            PortInfo(8000, 3, "python.exe", "", "", "demo", PortStatus.LISTENING),
            PortInfo(8765, 4, "dotnet.exe", "", "", "demo", PortStatus.LISTENING),
        ]
        self.assertEqual(summarize_port_chips(ports), (":3000", ":5173", ":8000"))

    def test_source_display_prefers_exact_command_file(self) -> None:
        with self.subTest("relative command file"):
            import tempfile

            with tempfile.TemporaryDirectory() as temp_dir:
                script_path = os.path.join(temp_dir, "server.py")
                with open(script_path, "w", encoding="utf-8") as handle:
                    handle.write("print('server')")

                port = PortInfo(
                    8765,
                    10,
                    "python.exe",
                    "",
                    temp_dir,
                    "demo",
                    PortStatus.ACTIVE,
                    command_args=("python", "server.py"),
                    project_root=temp_dir,
                )
                self.assertEqual(port.command_file_path, script_path)
                self.assertEqual(port.source_display_path, script_path)


if __name__ == "__main__":
    unittest.main()
