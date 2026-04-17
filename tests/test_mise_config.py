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
    Load and parse the repository's mise.toml configuration from the configured MISE_TOML path.

    Returns:
        dict: Parsed TOML configuration mapping.
    """
    with open(MISE_TOML, "rb") as f:
        return tomllib.load(f)


class MiseTestBase(unittest.TestCase):
    """Base class for mise.toml tests with shared helper methods."""

    def assert_darwin_guarded(self, cmd):
        """
        Assert that a command is guarded to run only on macOS.

        Checks that the command references `OSTYPE`, contains `darwin`, and includes the `if [[`/`then`/`fi` conditional markers.
        """
        self.assertIn("OSTYPE", cmd)
        self.assertIn("darwin", cmd)
        self.assertIn("if [[", cmd)
        self.assertIn("then", cmd)
        self.assertIn("fi", cmd)


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


class TestBootstrapTask(MiseTestBase):
    """Tests for the bootstrap task's updated macOS-conditional run command."""

    def setUp(self):
        """
        Prepare test fixtures by loading the repository's mise.toml and extracting the 'bootstrap' task.

        Sets self.config to the parsed TOML mapping and self.bootstrap to config["tasks"]["bootstrap"] for use by test methods.
        """
        self.config = load_mise_config()
        self.bootstrap = self.config["tasks"]["bootstrap"]

    def test_bootstrap_task_exists(self):
        """
        Check that the top-level `tasks` section includes a `bootstrap` entry.
        """
        self.assertIn("bootstrap", self.config["tasks"])

    def test_bootstrap_run_is_list(self):
        """
        Assert that the bootstrap task's `run` field is a list.

        This test checks that `self.bootstrap["run"]` is an instance of `list`.
        """
        self.assertIsInstance(self.bootstrap["run"], list)

    def test_bootstrap_run_has_two_commands(self):
        self.assertEqual(len(self.bootstrap["run"]), 2)

    def test_bootstrap_first_command_is_darwin_guarded(self):
        """
        Verify the first bootstrap run command is guarded to execute only on macOS.

        Asserts the command references `OSTYPE`, contains `darwin`, and includes the `if [[`, `then`, and `fi` conditional markers.
        """
        first_cmd = self.bootstrap["run"][0]
        self.assert_darwin_guarded(first_cmd)

    def test_bootstrap_first_command_contains_brew_symlink(self):
        """
        Assert that the first command in the bootstrap task's `run` list creates a Homebrew symlink and references the Python sysconfig path.

        The test checks that the command string contains:
        - the symlink invocation `"ln -s"`,
        - the Homebrew library prefix `"$(brew --prefix)/lib/*"`,
        - and a reference to `sysconfig.get_path`.
        """
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("ln -s", first_cmd)
        self.assertIn("$(brew --prefix)/lib/*", first_cmd)
        self.assertIn("sysconfig.get_path", first_cmd)

    def test_bootstrap_first_command_does_not_run_unconditionally(self):
        """
        Ensure the first bootstrap command does not run an unguarded 'ln -s' symlink.

        Asserts that, after stripping leading whitespace, the first command in the bootstrap task does not start with "ln -s", guaranteeing the brew symlink is protected by an OS-type guard.
        """
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
        Ensure the `bootstrap` task defines a non-missing `description` key.
        """
        self.assertIn("description", self.bootstrap)

    # Regression: previous command was not OS-guarded; ensure OSTYPE check is present
    def test_bootstrap_ostype_check_references_darwin(self):
        """
        Verify the bootstrap task's first run command references 'darwin'.

        Asserts that the first command contains the substring 'darwin', indicating an OSTYPE check for macOS.
        """
        first_cmd = self.bootstrap["run"][0]
        self.assertIn("darwin", first_cmd)


class TestParseTaskDescription(unittest.TestCase):
    """Tests for the parse task's updated description."""

    def setUp(self):
        """
        Load the repository's mise.toml and store the `parse` task for use by tests.

        Sets:
            self.config: Parsed TOML configuration loaded from the repository root.
            self.parse_task: The mapping for the `tasks.parse` entry from the loaded config.
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
        """
        Verify that the `parse` task has a `description` that is a non-empty string.

        Asserts the `description` field on the `parse` task is an instance of `str` and its length is greater than zero.
        """
        desc = self.parse_task["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_parse_task_run_command(self):
        self.assertEqual(self.parse_task["run"], "python main.py parse")

    def test_parse_task_depends_on_bootstrap(self):
        """
        Asserts that the `parse` task declares `bootstrap` as a dependency.

        Checks the `depends` entry of the `parse` task (treating it as an empty list if missing) and fails if `"bootstrap"` is not present.
        """
        self.assertIn("bootstrap", self.parse_task.get("depends", []))


class TestBuildTaskDescription(unittest.TestCase):
    """Tests for the build task's updated description."""

    def setUp(self):
        """
        Prepare the test case by loading the repository's mise.toml and caching the `build` task.

        Sets:
            self.config: Parsed TOML mapping from the repository's mise.toml.
            self.build_task: Mapping for the `build` task (equivalent to self.config["tasks"]["build"]).
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
        """
        Verify the build task's description mentions the output file path "cv.pdf".

        Asserts that the `description` field of the `build` task contains the substring "cv.pdf".
        """
        desc = self.build_task["description"]
        # Must mention an output file path
        self.assertIn("cv.pdf", desc)


class TestFullTask(unittest.TestCase):
    """Tests for the full task (parse + build) run array."""

    def setUp(self):
        """
        Prepare the test fixture by loading the repository's mise.toml and storing the `full` task.

        Loads the parsed TOML into self.config and stores the mapping for tasks["full"] in self.full_task for use by test methods.
        """
        self.config = load_mise_config()
        self.full_task = self.config["tasks"]["full"]

    def test_full_task_exists(self):
        """
        Asserts that the parsed mise.toml defines a top-level "full" task under the `tasks` section.
        """
        self.assertIn("full", self.config["tasks"])

    def test_full_run_is_list(self):
        """
        Verify the `run` field of the `full` task is a list.

        This test ensures the `tasks.full` entry defines its commands as a sequence (list) rather than a single string or other type.
        """
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


class TestBootstrapGuardCompleteness(MiseTestBase):
    """
    Regression tests that verify the consolidated darwin-guard test covers
    all required conditional markers as a single atomic assertion group.
    """

    def setUp(self):
        """
        Prepare test fixture by loading the repository's mise.toml configuration and storing the first command from the bootstrap task.

        The parsed TOML mapping is stored on `self.config`. The first bootstrap task command (the first element of `config["tasks"]["bootstrap"]["run"]`) is stored on `self.first_cmd`.
        """
        self.config = load_mise_config()
        self.first_cmd = self.config["tasks"]["bootstrap"]["run"][0]

    def test_darwin_guard_has_opening_bracket_syntax(self):
        """The conditional must use bash double-bracket [[ syntax."""
        self.assertIn("[[", self.first_cmd)

    def test_darwin_guard_closing_fi_keyword(self):
        """The conditional block must be properly closed with 'fi'."""
        self.assertIn("fi", self.first_cmd)

    def test_darwin_guard_then_keyword(self):
        """The conditional block must contain a 'then' clause."""
        self.assertIn("then", self.first_cmd)

    def test_darwin_guard_all_markers_present_together(self):
        """All six guard markers must be present in the same command string."""
        self.assert_darwin_guarded(self.first_cmd)

    def test_darwin_guard_if_precedes_fi(self):
        """'if [[' must appear before 'fi' in the command string."""
        if_pos = self.first_cmd.find("if [[")
        fi_pos = self.first_cmd.rfind("fi")
        self.assertLess(if_pos, fi_pos, "'if [[' must appear before 'fi'")

    def test_bootstrap_first_command_is_multiline_or_compound(self):
        """
        The macOS guard command should span multiple logical parts
        (at minimum more than one shell keyword), confirming it is not trivial.
        """
        keywords_found = sum(1 for kw in ["if", "then", "fi"] if kw in self.first_cmd)
        self.assertGreaterEqual(keywords_found, 3)


class TestBootstrapGuardOrdering(unittest.TestCase):
    """
    Structural ordering tests for the bootstrap darwin guard command.
    Verifies that shell keywords appear in the correct sequence.
    """

    def setUp(self):
        self.config = load_mise_config()
        self.first_cmd = self.config["tasks"]["bootstrap"]["run"][0]

    def test_then_appears_between_if_and_fi(self):
        """'then' must appear after 'if [[' and before 'fi'."""
        if_pos = self.first_cmd.find("if [[")
        then_pos = self.first_cmd.find("then")
        fi_pos = self.first_cmd.rfind("fi")
        self.assertNotEqual(if_pos, -1, "'if [[' must exist in command")
        self.assertNotEqual(then_pos, -1, "'then' must exist in command")
        self.assertNotEqual(fi_pos, -1, "'fi' must exist in command")
        self.assertLess(if_pos, then_pos, "'if [[' must precede 'then'")
        self.assertLess(then_pos, fi_pos, "'then' must precede 'fi'")

    def test_ln_s_appears_after_then(self):
        """The 'ln -s' command must appear after the 'then' keyword."""
        then_pos = self.first_cmd.find("then")
        ln_pos = self.first_cmd.find("ln -s")
        self.assertNotEqual(then_pos, -1, "'then' must exist in command")
        self.assertNotEqual(ln_pos, -1, "'ln -s' must exist in command")
        self.assertLess(then_pos, ln_pos, "'then' must appear before 'ln -s'")

    def test_ln_s_appears_before_fi(self):
        """The 'ln -s' command must appear before the closing 'fi'."""
        ln_pos = self.first_cmd.find("ln -s")
        fi_pos = self.first_cmd.rfind("fi")
        self.assertNotEqual(ln_pos, -1, "'ln -s' must exist in command")
        self.assertNotEqual(fi_pos, -1, "'fi' must exist in command")
        self.assertLess(ln_pos, fi_pos, "'ln -s' must appear before 'fi'")

    def test_ostype_check_appears_before_ln_s(self):
        """The OSTYPE variable reference must precede the 'ln -s' command."""
        ostype_pos = self.first_cmd.find("OSTYPE")
        ln_pos = self.first_cmd.find("ln -s")
        self.assertNotEqual(ostype_pos, -1, "'OSTYPE' must exist in command")
        self.assertNotEqual(ln_pos, -1, "'ln -s' must exist in command")
        self.assertLess(ostype_pos, ln_pos, "OSTYPE check must appear before 'ln -s'")

    def test_second_command_uses_uv(self):
        """The second bootstrap run command must invoke uv."""
        second_cmd = self.config["tasks"]["bootstrap"]["run"][1]
        self.assertIn("uv", second_cmd)

    def test_bootstrap_description_is_non_empty_string(self):
        """The bootstrap task must have a non-empty string description."""
        desc = self.config["tasks"]["bootstrap"]["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)


class TestAdditionalTasks(unittest.TestCase):
    """
    Tests for task entries that exist in mise.toml but are not covered by
    the existing test classes.
    """

    def setUp(self):
        self.config = load_mise_config()
        self.tasks = self.config["tasks"]

    def test_info_task_exists(self):
        """The 'info' task must be defined in mise.toml."""
        self.assertIn("info", self.tasks)

    def test_info_task_has_description(self):
        """The 'info' task must have a non-empty description."""
        desc = self.tasks["info"]["description"]
        self.assertIsInstance(desc, str)
        self.assertGreater(len(desc), 0)

    def test_lint_task_exists(self):
        """The 'lint' task must be defined in mise.toml."""
        self.assertIn("lint", self.tasks)

    def test_lint_task_depends_on_bootstrap(self):
        """The 'lint' task must declare 'bootstrap' as a dependency."""
        self.assertIn("bootstrap", self.tasks["lint"].get("depends", []))

    def test_format_task_exists(self):
        """The 'format' task must be defined in mise.toml."""
        self.assertIn("format", self.tasks)

    def test_test_task_exists(self):
        """The 'test' task must be defined in mise.toml."""
        self.assertIn("test", self.tasks)

    def test_test_task_run_invokes_pytest(self):
        """The 'test' task run command must invoke pytest."""
        self.assertIn("pytest", self.tasks["test"]["run"])

    def test_coverage_task_exists(self):
        """The 'coverage' task must be defined in mise.toml."""
        self.assertIn("coverage", self.tasks)

    def test_coverage_task_includes_cov_flag(self):
        """The 'coverage' task run command must include a --cov flag."""
        self.assertIn("--cov", self.tasks["coverage"]["run"])

    def test_full_task_run_is_not_empty(self):
        """The 'full' task run list must not be empty."""
        run = self.tasks["full"]["run"]
        self.assertGreater(len(run), 0)

    def test_all_expected_tasks_are_present(self):
        """All nine canonical tasks must exist in the tasks section."""
        expected = {
            "bootstrap",
            "info",
            "parse",
            "build",
            "full",
            "lint",
            "format",
            "test",
            "coverage",
        }
        for task_name in expected:
            self.assertIn(
                task_name, self.tasks, f"Task '{task_name}' missing from mise.toml"
            )


if __name__ == "__main__":
    unittest.main()
