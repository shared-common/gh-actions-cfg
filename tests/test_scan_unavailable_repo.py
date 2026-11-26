import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scan-unavailable-repo.py"
SPEC = importlib.util.spec_from_file_location("scan_unavailable_repo", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ScanUnavailableRepoTests(unittest.TestCase):
    def test_parse_project_entries_ignores_commented_examples_and_nested_ref_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projects.yml"
            path.write_text(
                """kind: glab-groups/projects
version: 1
projects:
  # - name: disabled
  - name: live
    source_project_url: https://github.com/example/live
    target_group_path: glab-forks/example
    additional_branches:
      - name: release
  - name: second
    source_project_url: 'https://gitlab.com/example/second'
    target_group_path: glab-forks/example
""",
                encoding="utf-8",
            )

            entries = MODULE.parse_project_entries(path, "glab-groups-projects")

            self.assertEqual([entry.name for entry in entries], ["live", "second"])
            self.assertEqual(entries[1].source_project_url, "https://gitlab.com/example/second")

    def test_scan_project_tries_git_suffix_before_marking_repository_unavailable(self) -> None:
        calls = []

        def runner(url, timeout):
            calls.append(url)
            if url.endswith(".git"):
                return 0, "refs/heads/main\n"
            return 128, "fatal: repository not found"

        project = MODULE.ProjectEntry(
            "glab-groups-projects",
            Path("projects.yml"),
            "demo",
            "https://github.com/example/demo",
            "glab-forks/example",
            0,
            4,
        )
        result = MODULE.scan_project(project, runner=runner, sleeper=lambda _: None)

        self.assertEqual(result.status, "available")
        self.assertEqual(calls, ["https://github.com/example/demo", "https://github.com/example/demo.git"])

    def test_remove_project_entries_preserves_other_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projects.yml"
            path.write_text(
                """kind: glab-groups/projects
version: 1
projects:
  - name: keep
    source_project_url: https://github.com/example/keep
    target_group_path: glab-forks/example
  - name: remove
    source_project_url: https://github.com/example/remove
    target_group_path: glab-forks/example
""",
                encoding="utf-8",
            )
            entries = MODULE.parse_project_entries(path)

            removed = MODULE.remove_project_entries(path, [entries[1]])

            self.assertEqual(removed, 1)
            text = path.read_text(encoding="utf-8")
            self.assertIn("name: keep", text)
            self.assertNotIn("name: remove", text)

    def test_selection_accepts_multiple_indexes_and_ranges(self) -> None:
        names = ["glab-groups-a", "glab-groups-b", "glab-groups-c", "glab-groups-d"]
        self.assertEqual(MODULE.parse_selection("1,3-4", names), [0, 2, 3])
        self.assertEqual(MODULE.parse_selection("glab-groups-b", names), [1])
        self.assertEqual(MODULE.parse_selection("all", names), [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main()
