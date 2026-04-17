"""
Tests for mise.toml configuration changes introduced in this PR.

Covers:
- bootstrap task: macOS-conditional brew symlink command
- parse task: updated description with results/ path
- build task: updated description with results/ path
- full task: run array format with two commands
"""

import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
MISE_TOML = REPO_ROOT / "mise.toml"


def load_mise_config() -> dict:
    """
    Load the repository's mise.toml configuration and return it as a dictionary.

    Returns:
        dict: Parsed TOML configuration from the file pointed to by `MISE_TOML`.
    """
    with open(MISE_TOML, "rb") as f:
        return tomllib.load(f)


class TestMiseTomlParses(unittest.TestCase):
    """Sanity checks that mise.toml is valid TOML and has expected top-level keys."""

    def test_toml_is_valid(self):
        config = load_mise_config()
        self.assertIsInstance(config, dict)

    def test_tasks_section_exists(self):
        """
        Checks that the repository's mise.toml contains a top-level "tasks" section.
        """
        config = load_mise_config()
        self.assertIn("tasks", config)

    def test_tools_section_exists(self):
        config = load_mise_config()
        self.assertIn("tools", config)


class TestBootstrapTask(unittest.TestCase):
    """Tests for the bootstrap task's updated macOS-conditional run command."""

    def setUp(self):
        """
        Load the repository's mise.toml into self.config and set self.bootstrap to the 'bootstrap' task entry.

        Prepares test fixtures by parsing the top-level configuration and extracting config["tasks"]["bootstrap"] for use in tests.
        """
        self.config = load_mise_config()
        self.bootstrap = self.config["tasks"]["bootstrap"]

    def test_bootstrap_task_exists(self):
        """
        Verify the configuration contains a 'bootstrap' entry under the top-level 'tasks' section.
        
        This test fails if 'bootstrap' is not present in self.config["tasks"].
        """
        self.assertIn("bootstrap", self.config["tasks"])

    def test_bootstrap_run_is_list(self):
        self.assertIsInstance(self.bootstrap["run"], list)

    def test_bootstrap_run_has_two_commands(self):
        self.assertEqual(len(self.bootstrap["run"]), 2)

    def test_bootstrap_first_command_has_macos_ostype_guard(self):
        """The brew symlink command must be guarded by an OSTYPE darwin check."""
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("[[ $OSTYPE == 'darwin'*", first_cmd)

    def test_bootstrap_first_command_uses_conditional_and(self):
        """The macOS guard uses && so the symlink only runs on Darwin."""
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("]]", first_cmd)
        self.assertIn("&&", first_cmd)

    def test_bootstrap_first_command_contains_brew_symlink(self):
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("ln -s $(brew --prefix)/lib/*", first_cmd)

    def test_bootstrap_first_command_is_darwin_guarded(self):
        """
        Ensure the first bootstrap command is guarded to run only on macOS.

        Asserts the command references `OSTYPE`, contains `darwin`, and uses `&&` to combine the conditional with the command.
        """
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("OSTYPE", first_cmd)
        self.assertIn("darwin", first_cmd)
        self.assertIn("&&", first_cmd)

    def test_bootstrap_first_command_does_not_run_unconditionally(self):
        """Previous behaviour ran brew unconditionally; ensure that raw unconditional form is gone."""
        first_cmd = self.bootstrap["run"][0]
        # Must NOT start with bare ln -s (without a guard)
        self.assertFalse(
            first_cmd.lstrip().startswith("ln -s"),
            "brew symlink must be guarded by OS check, not run unconditionally",
        )

    def test_bootstrap_second_command_installs_requirements(self):
        second_cmd = self.bootstrap["run"][1]
        self.assertEqual(second_cmd, "uv pip install -r requirements.txt")

    def test_bootstrap_has_description(self):
        """
        Check that the `bootstrap` task contains a `description` key.

        Asserts that the parsed `bootstrap` task dictionary includes a non-missing "description" entry.
        """
        self.assertIn("description", self.bootstrap)

    # Regression: previous command was not OS-guarded; ensure OSTYPE check is present
    def test_bootstrap_ostype_check_references_darwin(self):
        """
        Asserts that the first command in the bootstrap task's `run` list references 'darwin'.
        
        Verifies the bootstrap task's initial run command includes the substring 'darwin', ensuring an OSTYPE check for macOS is present.
        """
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("darwin", first_cmd)


class TestParseTaskDescription(unittest.TestCase):
    """Tests for the parse task's updated description."""

    def setUp(self):
        """
        Prepare the test fixture by loading the repository's mise.toml and storing the `parse` task.

        Sets:
            self.config (dict): Parsed TOML configuration returned by load_mise_config().
            self.parse_task (dict): The mapping for the `tasks.parse` entry from the loaded config.
        """
        self.config = load_mise_config()
        self.parse_task = self.config["tasks"]["parse"]

    def test_parse_task_exists(self):
        self.assertIn("parse", self.config["tasks"])

    def test_parse_description_includes_results_path(self):
        """Description must reference the results/ directory, not just cv_data.json."""
        desc = self.parse_task["description"]
        self.assertIn("results/cv_data.json", desc)

    def test_parse_description_does_not_use_bare_cv_data_json(self):
        """
        Ensure the parse task description does not reference `cv_data.json` without the `results/` prefix.

        This test asserts the description does not contain the legacy marker "→ cv_data.json".
        """
        desc = self.parse_task["description"]
        # The path should include 'results/' prefix
        self.assertNotIn("→ cv_data.json", desc)

    def test_parse_description_is_non_empty_string(self):
        desc = self.parse_task["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_parse_task_run_command(self):
        self.assertEqual(self.parse_task["run"], "python main.py parse")

    def test_parse_task_depends_on_bootstrap(self):
        self.assertIn("bootstrap", self.parse_task.get("depends", []))


class TestBuildTaskDescription(unittest.TestCase):
    """Tests for the build task's updated description."""

    def setUp(self):
        """
        Load the project's mise.toml and cache the `build` task for use by tests.
        
        Assigns the parsed TOML mapping to `self.config` and `self.build_task` to `self.config["tasks"]["build"]`.
        """
        self.config = load_mise_config()
        self.build_task = self.config["tasks"]["build"]

    def test_build_task_exists(self):
        self.assertIn("build", self.config["tasks"])

    def test_build_description_mentions_results_cv_pdf(self):
        """Description must reference the default output path results/cv.pdf."""
        desc = self.build_task["description"]
        self.assertIn("results/cv.pdf", desc)

    def test_build_description_mentions_default(self):
        """Description should indicate this is the default output."""
        desc = self.build_task["description"]
        self.assertIn("default", desc)

    def test_build_description_is_non_empty_string(self):
        desc = self.build_task["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_build_task_run_command(self):
        self.assertEqual(self.build_task["run"], "python main.py build")

    # Regression: old description was "Build PDF from JSON data" with no output path
    def test_build_description_no_longer_lacks_output_path(self):
        desc = self.build_task["description"]
        # Must mention an output file path
        self.assertIn("cv.pdf", desc)


class TestFullTask(unittest.TestCase):
    """Tests for the full task (parse + build) run array."""

    def setUp(self):
        """
        Prepare the test fixture by loading the repository's mise.toml and storing its "full" task.
        
        Attributes:
            config (dict): Parsed TOML configuration.
            full_task (dict): Mapping for the `tasks["full"]` entry.
        """
        self.config = load_mise_config()
        self.full_task = self.config["tasks"]["full"]

    def test_full_task_exists(self):
        self.assertIn("full", self.config["tasks"])

    def test_full_run_is_list(self):
        self.assertIsInstance(self.full_task["run"], list)

    def test_full_run_has_two_commands(self):
        self.assertEqual(len(self.full_task["run"]), 2)

    def test_full_run_first_command_is_parse(self):
        self.assertEqual(self.full_task["run"][0], "python main.py parse")

    def test_full_run_second_command_is_build(self):
        self.assertEqual(self.full_task["run"][1], "python main.py build")

    def test_full_task_description(self):
        desc = self.full_task["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)


if __name__ == "__main__":
    unittest.main()
