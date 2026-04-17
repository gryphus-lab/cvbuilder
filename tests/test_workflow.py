"""
Tests for .github/workflows/python-app.yml introduced in this PR.

Uses only stdlib (pathlib, re, unittest) plus PyYAML when available,
falling back to raw-text assertions so the suite never requires an
extra install just to run.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raw_text() -> str:
    """
    Read and return the repository workflow file contents.

    Returns:
        str: The contents of the workflow file.
    """
    return WORKFLOW_FILE.read_text(encoding="utf-8")


def _load_yaml() -> dict:
    """
    Load and parse the repository workflow YAML into a Python dictionary.

    Returns:
        dict: Parsed YAML content from the workflow file.

    Raises:
        ImportError: If the `yaml` module is not installed.
    """
    import yaml  # type: ignore

    with open(WORKFLOW_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# File-existence & raw-text tests (no extra deps required)
# ---------------------------------------------------------------------------


class TestWorkflowFileExists(unittest.TestCase):
    def test_workflow_file_exists(self):
        self.assertTrue(
            WORKFLOW_FILE.exists(), f"Workflow file not found: {WORKFLOW_FILE}"
        )

    def test_workflow_file_is_non_empty(self):
        self.assertGreater(WORKFLOW_FILE.stat().st_size, 0)


class TestWorkflowRawContent(unittest.TestCase):
    """Structural checks using raw text – no YAML parser dependency."""

    def setUp(self):
        """
        Load the workflow file's raw UTF-8 contents into self.text for use by the test methods.
        """
        self.text = _raw_text()

    # ----- Trigger configuration -----

    def test_triggers_on_push_to_main(self):
        self.assertRegex(self.text, r'branches:\s*\[\s*"main"\s*\]')

    def test_triggers_on_pull_request(self):
        self.assertIn("pull_request:", self.text)

    # ----- Top-level permissions -----

    def test_top_level_permissions_contents_read(self):
        self.assertIn("contents: read", self.text)

    # ----- Runner -----

    def test_runs_on_ubuntu_latest(self):
        self.assertIn("ubuntu-latest", self.text)

    # ----- Checkout action -----

    def test_checkout_action_version(self):
        self.assertIn("actions/checkout@v6", self.text)

    def test_checkout_fetch_depth_zero(self):
        self.assertIn("fetch-depth: 0", self.text)

    # ----- Mise setup -----

    def test_mise_action_version(self):
        self.assertIn("jdx/mise-action@v4", self.text)

    def test_mise_action_install_true(self):
        self.assertIn("install: true", self.text)

    def test_mise_action_cache_true(self):
        self.assertIn("cache: true", self.text)

    # ----- Step run commands -----

    def test_step_runs_mise_bootstrap(self):
        self.assertIn("mise run bootstrap", self.text)

    def test_step_runs_mise_info(self):
        """
        Assert the workflow file contains the "mise run info" command.

        Fails the test if the substring "mise run info" is not present in the workflow's raw text.
        """
        self.assertIn("mise run info", self.text)

    def test_step_checks_mise_version(self):
        """
        Verify the raw workflow text includes a step that runs "mise --version".
        """
        self.assertIn("mise --version", self.text)

    def test_step_runs_mise_doctor(self):
        self.assertIn("mise doctor", self.text)

    # ----- Step names present -----

    def test_step_name_install_dependencies(self):
        self.assertIn("Install dependencies", self.text)

    def test_step_name_show_project_info(self):
        self.assertIn("Show project info", self.text)

    def test_step_name_check_setup(self):
        self.assertIn("Check setup", self.text)

    def test_step_name_setup_mise(self):
        self.assertIn("Setup mise", self.text)

    # ----- Regression: test step must exist -----

    def test_no_pytest_step(self):
        """Workflow must execute tests."""
        self.assertIn("pytest", self.text)


# ---------------------------------------------------------------------------
# YAML-parsed tests (skipped gracefully if PyYAML is not installed)
# ---------------------------------------------------------------------------

_YAML_AVAILABLE = True
try:
    import yaml as _yaml  # type: ignore  # noqa: F401
except ImportError:
    _YAML_AVAILABLE = False


@unittest.skipUnless(
    _YAML_AVAILABLE, "PyYAML not installed – skipping structured tests"
)
class TestWorkflowYAMLStructure(unittest.TestCase):
    """Deep structural assertions using a parsed YAML document."""

    def setUp(self):
        """
        Parse the repository workflow YAML and assign the resulting mapping to `self.cfg` for use by the test methods.
        """
        self.cfg = _load_yaml()

    def test_workflow_name(self):
        self.assertEqual(
            self.cfg["name"], "CI Workflow for cvbuilder with mise and SonarQube"
        )

    def test_on_push_branches(self):
        """
        Assert that the workflow's `on.push.branches` configuration includes "main".
        """
        self.assertIn("main", self.cfg["on"]["push"]["branches"])

    def test_on_pull_request_branches(self):
        """
        Ensure the workflow's `pull_request` trigger includes the `main` branch.

        Asserts that `"main"` appears in the parsed YAML at `on.pull_request.branches`.
        """
        self.assertIn("main", self.cfg["on"]["pull_request"]["branches"])

    def test_top_level_permissions_contents_read(self):
        """
        Assert that the workflow's top-level `permissions.contents` is set to "read".

        Raises an assertion failure if `self.cfg["permissions"]["contents"]` is not equal to `"read"`.
        """
        self.assertEqual(self.cfg["permissions"]["contents"], "read")

    def test_jobs_build_exists(self):
        self.assertIn("build", self.cfg["jobs"])

    def test_job_build_permissions_contents_write(self):
        """
        Asserts that the workflow's `build` job grants write access to repository contents.

        Verifies that `self.cfg["jobs"]["build"]["permissions"]["contents"]` is equal to `"write"`.
        """
        build_perms = self.cfg["jobs"]["build"]["permissions"]
        self.assertEqual(build_perms["contents"], "write")

    def test_job_runs_on_ubuntu_latest(self):
        self.assertEqual(self.cfg["jobs"]["build"]["runs-on"], "ubuntu-latest")

    def test_steps_is_list(self):
        """
        Asserts that the `build` job's `steps` entry in the parsed workflow YAML is a list.
        """
        steps = self.cfg["jobs"]["build"]["steps"]
        self.assertIsInstance(steps, list)

    def test_steps_count(self):
        """Workflow contains all required steps."""
        steps = self.cfg["jobs"]["build"]["steps"]

        # Check that required steps are present
        required_steps = [
            ("Checkout", lambda s: "actions/checkout" in s.get("uses", "")),
            (
                "Setup mise",
                lambda s: s.get("name") == "Setup mise"
                or "jdx/mise-action" in s.get("uses", ""),
            ),
            ("Check setup", lambda s: s.get("name") == "Check setup"),
            ("Install dependencies", lambda s: s.get("name") == "Install dependencies"),
            ("Show project info", lambda s: s.get("name") == "Show project info"),
            (
                "Run tests",
                lambda s: "pytest" in s.get("name", "").lower()
                or "test" in s.get("name", "").lower(),
            ),
        ]

        for step_desc, matcher in required_steps:
            self.assertTrue(
                any(matcher(s) for s in steps), f"Required step not found: {step_desc}"
            )

    def test_checkout_step_is_first(self):
        """
        Check that the first step of the `build` job uses the checkout action.

        Verifies that the `uses` value of the first entry in `self.cfg["jobs"]["build"]["steps"]` contains the substring "actions/checkout".
        """
        first = self.cfg["jobs"]["build"]["steps"][0]
        self.assertIn("actions/checkout", first.get("uses", ""))

    def test_checkout_fetch_depth(self):
        """
        Assert that the first step (actions/checkout) in the parsed workflow has its `with.fetch-depth` set to 0.
        """
        first = self.cfg["jobs"]["build"]["steps"][0]
        self.assertEqual(first["with"]["fetch-depth"], 0)

    def test_mise_action_step(self):
        step = self.cfg["jobs"]["build"]["steps"][1]
        self.assertIn("jdx/mise-action", step.get("uses", ""))

    def test_mise_action_with_install(self):
        step = self.cfg["jobs"]["build"]["steps"][1]
        self.assertTrue(step["with"]["install"])

    def test_mise_action_with_cache(self):
        step = self.cfg["jobs"]["build"]["steps"][1]
        self.assertTrue(step["with"]["cache"])

    def _get_step_by_name(self, name: str) -> dict:
        """
        Retrieve a job step by its displayed name from the parsed workflow configuration.

        Parameters:
            name (str): The `name` value of the step to locate within `self.cfg["jobs"]["build"]["steps"]`.

        Returns:
            step (dict): The mapping representing the first step whose `"name"` equals `name`.

        Raises:
            KeyError: If no step with the given `name` is present.
        """
        steps = self.cfg["jobs"]["build"]["steps"]
        for step in steps:
            if step.get("name") == name:
                return step
        raise KeyError(f"Step '{name}' not found")

    def test_install_dependencies_step_command(self):
        step = self._get_step_by_name("Install dependencies")
        self.assertIn("mise run bootstrap", step["run"])

    def test_show_project_info_step_command(self):
        step = self._get_step_by_name("Show project info")
        self.assertIn("mise run info", step["run"])

    def test_lint_step_command(self):
        step = self._get_step_by_name("Lint with black")
        self.assertIn("mise run lint", step["run"])

    def test_check_setup_step_commands(self):
        step = self._get_step_by_name("Check setup")
        self.assertIn("mise --version", step["run"])
        self.assertIn("mise doctor", step["run"])

    # Boundary / negative cases

    def test_no_env_at_job_level(self):
        """Job does not set extra environment variables."""
        job = self.cfg["jobs"]["build"]
        self.assertNotIn("env", job)

    def test_workflow_has_no_matrix_strategy(self):
        """Single-version workflow – no matrix defined."""
        job = self.cfg["jobs"]["build"]
        self.assertNotIn("strategy", job)


if __name__ == "__main__":
    unittest.main()
