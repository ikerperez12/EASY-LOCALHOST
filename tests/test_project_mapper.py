import json
import os
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from project_mapper import clear_cache, find_project_root, identify_project_from_process


class ProjectMapperTests(unittest.TestCase):
    def tearDown(self) -> None:
        clear_cache()

    def test_uses_git_origin_name_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            git_dir = os.path.join(temp_dir, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "config"), "w", encoding="utf-8") as handle:
                handle.write(
                    '[remote "origin"]\n'
                    'url = https://github.com/example/easy-localhost.git\n'
                )

            name, root = identify_project_from_process(temp_dir)
            self.assertEqual(name, "easy-localhost")
            self.assertEqual(root, temp_dir)

    def test_walks_up_to_package_json_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = os.path.join(temp_dir, "demo-app")
            nested = os.path.join(project_root, "src", "pages")
            os.makedirs(nested)
            with open(os.path.join(project_root, "package.json"), "w", encoding="utf-8") as handle:
                json.dump({"name": "demo-app"}, handle)

            resolved = find_project_root(nested)
            self.assertEqual(resolved, project_root)

    def test_prefers_cwd_over_runtime_node_modules_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = os.path.join(temp_dir, "portfolio")
            runtime_dir = os.path.join(project_root, "node_modules", "vite", "bin")
            os.makedirs(runtime_dir)
            with open(os.path.join(project_root, "package.json"), "w", encoding="utf-8") as handle:
                json.dump({"name": "portfolio-site"}, handle)

            vite_script = os.path.join(runtime_dir, "vite.js")
            with open(vite_script, "w", encoding="utf-8") as handle:
                handle.write("console.log('vite');")

            name, root = identify_project_from_process(
                project_root,
                ("node", vite_script, "--host", "127.0.0.1"),
            )
            self.assertEqual(name, "portfolio-site")
            self.assertEqual(root, project_root)

    def test_uses_command_file_project_when_cwd_is_too_general(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            general_cwd = os.path.join(temp_dir, "user-home")
            project_root = os.path.join(general_cwd, "portfolio")
            os.makedirs(project_root)
            with open(os.path.join(project_root, "package.json"), "w", encoding="utf-8") as handle:
                json.dump({"name": "portfolio-site"}, handle)

            server_file = os.path.join(project_root, "server.py")
            with open(server_file, "w", encoding="utf-8") as handle:
                handle.write("print('server')")

            name, root = identify_project_from_process(
                general_cwd,
                ("python", server_file),
            )
            self.assertEqual(name, "portfolio-site")
            self.assertEqual(root, project_root)


if __name__ == "__main__":
    unittest.main()
