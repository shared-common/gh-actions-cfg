import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIRS = sorted(path for path in REPO_ROOT.glob("glab-groups-*") if path.is_dir())
PROJECTS_ONLY_CONFIGS = {"glab-groups-projects"}
EXPECTED_DEFAULTS = {
    "glab-groups-android": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-chromium": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-debian": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-freedesktop": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-gnome": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-hashicorp": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-kali": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-kde": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-microsoft": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-nvidia": {"batch_size": 10, "max_parallel": 5},
    "glab-groups-openai": {"batch_size": 25, "max_parallel": 5},
    "glab-groups-projects": {"batch_size": 10, "max_parallel": 5},
    "glab-groups-small": {"batch_size": 10, "max_parallel": 5},
}


def load_structured(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    result = subprocess.run(
        [
            "perl",
            "-MCPAN::Meta::YAML",
            "-MJSON::PP",
            "-e",
            (
                'my $docs = CPAN::Meta::YAML->read(shift) or die "unable to read YAML\\n"; '
                '@{$docs} == 1 or die "expected exactly one YAML document\\n"; '
                'print JSON::PP->new->canonical(1)->encode($docs->[0]);'
            ),
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


class ConfigContractTests(unittest.TestCase):
    def assert_version_is_one(self, payload) -> None:
        self.assertEqual(int(payload["version"]), 1)

    def test_checked_in_default_parallelism_matches_safe_repo_map(self) -> None:
        self.assertEqual(
            {path.name for path in CONFIG_DIRS},
            set(EXPECTED_DEFAULTS),
            "update EXPECTED_DEFAULTS when adding or removing config directories",
        )
        for config_dir in CONFIG_DIRS:
            with self.subTest(config=config_dir.name):
                defaults_path = config_dir / "defaults.json"
                if not defaults_path.exists():
                    defaults_path = config_dir / "defaults.yml"
                self.assertTrue(defaults_path.exists(), "missing defaults file")

                payload = load_structured(defaults_path)
                self.assertEqual(payload["kind"], "glab-groups/defaults")
                self.assert_version_is_one(payload)
                expected = EXPECTED_DEFAULTS[config_dir.name]
                self.assertEqual(int(payload["defaults"]["batch_size"]), expected["batch_size"])
                self.assertEqual(int(payload["defaults"]["max_parallel"]), expected["max_parallel"])

    def test_config_directories_keep_expected_shape(self) -> None:
        for config_dir in CONFIG_DIRS:
            with self.subTest(config=config_dir.name):
                projects_path = config_dir / "projects.yml"
                self.assertTrue(projects_path.exists(), "missing projects.yml")
                projects_payload = load_structured(projects_path)
                self.assertEqual(projects_payload["kind"], "glab-groups/projects")
                self.assert_version_is_one(projects_payload)

                if config_dir.name in PROJECTS_ONLY_CONFIGS:
                    self.assertFalse((config_dir / "namespaces.json").exists(), "projects-only config should not define namespaces.json")
                    self.assertFalse((config_dir / "exclude.yml").exists(), "projects-only config should not define exclude.yml")
                    continue

                namespaces_path = config_dir / "namespaces.json"
                exclude_path = config_dir / "exclude.yml"
                self.assertTrue(namespaces_path.exists(), "missing namespaces.json")
                self.assertTrue(exclude_path.exists(), "missing exclude.yml")

                namespaces_payload = load_structured(namespaces_path)
                self.assertEqual(namespaces_payload["kind"], "glab-groups/namespaces")
                self.assert_version_is_one(namespaces_payload)
                self.assertTrue(namespaces_payload["namespaces"], "namespaces.json must define at least one namespace")

                exclude_payload = load_structured(exclude_path)
                self.assertEqual(exclude_payload["kind"], "glab-groups/project-exclusions")
                self.assert_version_is_one(exclude_payload)


if __name__ == "__main__":
    unittest.main()
