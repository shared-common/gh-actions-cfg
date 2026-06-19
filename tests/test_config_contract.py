import json
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIRS = sorted(path for path in REPO_ROOT.glob("glab-groups-*") if path.is_dir())
PROJECTS_ONLY_CONFIGS = {"glab-groups-projects"}
GROUP_FILTER_CONFIGS = {
    "glab-groups-debian",
    "glab-groups-freedesktop",
    "glab-groups-gnome",
    "glab-groups-kde",
}
EXPECTED_GROUP_FILTER_COUNTS = {
    "glab-groups-debian": 103,
    "glab-groups-freedesktop": 60,
    "glab-groups-gnome": 7,
    "glab-groups-kde": 33,
}
EXPECTED_DEFAULTS = {
    "glab-groups-android": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-chromium": {"batch_size": 50, "max_parallel": 5},
    "glab-groups-debian": {"batch_size": 50, "max_parallel": 1},
    "glab-groups-freedesktop": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-gnome": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-hashicorp": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-kali": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-kde": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-microsoft": {"batch_size": 50, "max_parallel": 2},
    "glab-groups-nvidia": {"batch_size": 10, "max_parallel": 2},
    "glab-groups-openai": {"batch_size": 25, "max_parallel": 2},
    "glab-groups-projects": {"batch_size": 10, "max_parallel": 2},
    "glab-groups-small": {"batch_size": 10, "max_parallel": 2},
}
EXPECTED_NAMESPACE_DISCOVERY_SHARDS = {
    "glab-groups-microsoft": 10,
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
                self.assertNotIn(
                    "target_branches_protect",
                    payload["defaults"],
                    "default configs must not enforce target branch protection by default",
                )
                self.assertNotIn(
                    "mirror_pristine_tar",
                    payload["defaults"],
                    "default configs must not opt projects into pristine-tar mirroring",
                )
                expected = EXPECTED_DEFAULTS[config_dir.name]
                self.assertEqual(int(payload["defaults"]["batch_size"]), expected["batch_size"])
                self.assertEqual(int(payload["defaults"]["max_parallel"]), expected["max_parallel"])

    def test_config_directories_keep_expected_shape(self) -> None:
        for config_dir in CONFIG_DIRS:
            with self.subTest(config=config_dir.name):
                projects_path = config_dir / "projects.yml"
                groups_path = config_dir / "groups.jsonl"
                self.assertTrue(projects_path.exists(), "missing projects.yml")
                projects_payload = load_structured(projects_path)
                self.assertEqual(projects_payload["kind"], "glab-groups/projects")
                self.assert_version_is_one(projects_payload)

                if config_dir.name in PROJECTS_ONLY_CONFIGS:
                    self.assertFalse((config_dir / "namespaces.json").exists(), "projects-only config should not define namespaces.json")
                    self.assertFalse((config_dir / "exclude.yml").exists(), "projects-only config should not define exclude.yml")
                    self.assertFalse(groups_path.exists(), "projects-only config should not define groups.jsonl")
                    continue

                namespaces_path = config_dir / "namespaces.json"
                exclude_path = config_dir / "exclude.yml"
                self.assertTrue(namespaces_path.exists(), "missing namespaces.json")
                self.assertTrue(exclude_path.exists(), "missing exclude.yml")

                namespaces_payload = load_structured(namespaces_path)
                self.assertEqual(namespaces_payload["kind"], "glab-groups/namespaces")
                self.assert_version_is_one(namespaces_payload)
                self.assertTrue(namespaces_payload["namespaces"], "namespaces.json must define at least one namespace")
                for namespace in namespaces_payload["namespaces"]:
                    self.assertNotIn(
                        "target_branches_protect",
                        namespace,
                        "namespace configs must not enforce target branch protection by default",
                    )
                    self.assertNotIn(
                        "mirror_pristine_tar",
                        namespace,
                        "namespace configs must not opt projects into pristine-tar mirroring",
                    )
                expected_discovery_shards = EXPECTED_NAMESPACE_DISCOVERY_SHARDS.get(config_dir.name)
                if expected_discovery_shards is not None:
                    self.assertEqual(
                        int(namespaces_payload["namespaces"][0]["discovery_shards"]),
                        expected_discovery_shards,
                        "namespace discovery shard count must match the checked-in parallel discovery contract",
                    )

                exclude_payload = load_structured(exclude_path)
                self.assertEqual(exclude_payload["kind"], "glab-groups/project-exclusions")
                self.assert_version_is_one(exclude_payload)
                self.assertIsInstance(exclude_payload.get("projects"), list, "exclude.yml projects must be a list")
                for item in exclude_payload.get("source_groups", []):
                    self.assertIsInstance(item, dict, "exclude.yml source_groups entries must be objects")
                    self.assertIsInstance(item.get("source_group_path"), str, "exclude.yml source_groups entries must define source_group_path")
                    self.assertTrue(item["source_group_path"].strip(), "exclude.yml source_group_path must not be blank")
                    if "reason" in item:
                        self.assertIsInstance(item["reason"], str, "exclude.yml source_groups reason must be a string")
                        self.assertTrue(item["reason"].strip(), "exclude.yml source_groups reason must not be blank")

                if config_dir.name in GROUP_FILTER_CONFIGS:
                    self.assertTrue(groups_path.exists(), "missing groups.jsonl for explicit top-level GitLab group allowlists")
                    entries = [
                        json.loads(line)
                        for line in groups_path.read_text(encoding="utf-8").splitlines()
                        if line.strip()
                    ]
                    self.assertTrue(entries, "groups.jsonl must not be empty")
                    self.assertEqual(
                        len(entries),
                        EXPECTED_GROUP_FILTER_COUNTS[config_dir.name],
                        "groups.jsonl entry count must match the checked-in top-level group allowlist",
                    )
                    source_group_paths = []
                    for entry in entries:
                        self.assertTrue(
                            isinstance(entry, str)
                            or (isinstance(entry, dict) and isinstance(entry.get("source_group_path"), str)),
                            "groups.jsonl entries must be JSON strings or objects with source_group_path",
                        )
                        source_group_path = entry if isinstance(entry, str) else entry["source_group_path"]
                        self.assertTrue(source_group_path.strip(), "groups.jsonl source group path must not be blank")
                        self.assertNotIn("/", source_group_path, "groups.jsonl entries must stay top-level source groups")
                        source_group_paths.append(source_group_path)
                    self.assertEqual(
                        len(source_group_paths),
                        len(set(source_group_paths)),
                        "groups.jsonl entries must not contain duplicate source groups",
                    )
                else:
                    self.assertFalse(groups_path.exists(), "unexpected groups.jsonl outside the dedicated instance-root wrappers")


if __name__ == "__main__":
    unittest.main()
