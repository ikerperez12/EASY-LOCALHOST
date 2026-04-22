import os
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scanner import _infer_working_directory


class ScannerHeuristicsTests(unittest.TestCase):
    def test_uses_first_existing_directory_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            inferred = _infer_working_directory(("python", temp_dir), "")
            self.assertEqual(inferred, temp_dir)

    def test_uses_parent_directory_for_existing_file_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = os.path.join(temp_dir, "server.py")
            with open(script_path, "w", encoding="utf-8") as handle:
                handle.write("print('hello')")

            inferred = _infer_working_directory(("python", script_path), "")
            self.assertEqual(inferred, temp_dir)


if __name__ == "__main__":
    unittest.main()
