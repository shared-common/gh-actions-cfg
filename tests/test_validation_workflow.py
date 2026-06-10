import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "validate-configs.yml"


class ValidationWorkflowTests(unittest.TestCase):
    def test_workflow_validates_central_config_repo_against_shared_loader(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: validate-configs", text)
        self.assertIn('group: validate-configs-${{ github.ref }}', text)
        self.assertIn("config-contract:", text)
        self.assertIn("shared-loader:", text)
        self.assertIn(
            "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            text,
        )
        self.assertIn("repository: shared-common/glab-groups-shared", text)
        self.assertIn("ref: mcr/main", text)
        self.assertIn(
            "LC_ALL=C TZ=UTC python3 -m unittest discover -s tests -p 'test_*.py'",
            text,
        )
        self.assertIn("perl -I shared/lib -MGlabGroups=load_config_dir -", text)
        self.assertIn("find . -mindepth 1 -maxdepth 1 -type d -name 'glab-groups-*' | sort", text)


if __name__ == "__main__":
    unittest.main()
