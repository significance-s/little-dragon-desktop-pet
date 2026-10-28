from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch


APP_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_DIR))

import bootstrap  # noqa: E402
import launch  # noqa: E402


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = APP_DIR / "tests" / "runtime_data" / "bootstrap"
        self.fixture.mkdir(parents=True, exist_ok=True)
        self.stamp = self.fixture / "setup-stamp"
        self.cfg = self.fixture / "pyvenv.cfg"

    def tearDown(self) -> None:
        self.stamp.unlink(missing_ok=True)
        self.cfg.unlink(missing_ok=True)

    def test_global_interpreter_is_never_considered_ready(self) -> None:
        with patch("bootstrap.subprocess.run") as probe:
            self.assertFalse(bootstrap.interpreter_ready(Path("global/python.exe")))
        probe.assert_not_called()

    def test_system_site_packages_are_rejected(self) -> None:
        with patch("bootstrap.VENV_DIR", self.fixture):
            self.cfg.write_text("include-system-site-packages = true\n", encoding="utf-8")
            self.assertFalse(bootstrap.venv_config_is_isolated())
            self.cfg.write_text("include-system-site-packages = false\n", encoding="utf-8")
            self.assertTrue(bootstrap.venv_config_is_isolated())

    def test_probe_timeout_is_not_ready(self) -> None:
        with patch.object(Path, "is_file", return_value=True), \
                patch("bootstrap.venv_config_is_isolated", return_value=True), \
                patch("bootstrap.subprocess.run", side_effect=subprocess.TimeoutExpired("python", 20)):
            self.assertFalse(bootstrap.interpreter_ready(bootstrap.VENV_PYTHON))

    def test_inherited_python_package_paths_are_removed(self) -> None:
        with patch.dict("os.environ", {"PYTHONHOME": "global", "PYTHONPATH": "global-packages"}):
            env = bootstrap.runtime_environment()
        self.assertNotIn("PYTHONHOME", env)
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")

    def test_check_mode_never_installs_or_launches_a_pet(self) -> None:
        with patch("bootstrap.project_ready", return_value=True), \
                patch("bootstrap.prepare_venv") as install, \
                patch("bootstrap.start_background") as start, \
                patch("bootstrap.subprocess.run", return_value=Mock(returncode=0)) as check:
            self.assertEqual(bootstrap.main(["--check"]), 0)
        install.assert_not_called()
        start.assert_not_called()
        self.assertEqual(Path(check.call_args.args[0][0]), bootstrap.VENV_PYTHON)
        self.assertIn("--check", check.call_args.args[0])

    def test_check_mode_fails_without_using_global_packages(self) -> None:
        with patch("bootstrap.project_ready", return_value=False), \
                patch("bootstrap.prepare_venv") as install, \
                patch("bootstrap.start_background") as start:
            self.assertEqual(bootstrap.main(["--check"]), 1)
        install.assert_not_called()
        start.assert_not_called()

    def test_setup_mode_prepares_missing_project_environment(self) -> None:
        with patch("bootstrap.project_ready", return_value=False), \
                patch("bootstrap.prepare_venv", return_value=bootstrap.VENV_PYTHON) as install, \
                patch("bootstrap.start_background") as start:
            self.assertEqual(bootstrap.main(["--setup"]), 0)
        install.assert_called_once_with(Path(sys.executable))
        start.assert_not_called()

    def test_normal_start_only_uses_project_python(self) -> None:
        with patch("bootstrap.project_ready", return_value=True), \
                patch("bootstrap.prepare_venv") as install, \
                patch("bootstrap.start_background") as start:
            self.assertEqual(bootstrap.main([]), 0)
        install.assert_not_called()
        start.assert_called_once_with(bootstrap.VENV_PYTHON)

    def test_global_background_launch_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            bootstrap.start_background(Path("global/python.exe"))

    def test_background_uses_matching_project_pythonw(self) -> None:
        with patch.object(Path, "is_file", return_value=True), \
                patch("bootstrap.subprocess.Popen") as start:
            bootstrap.start_background(bootstrap.VENV_PYTHON)
        command = start.call_args.args[0]
        self.assertEqual(Path(command[0]), bootstrap.VENV_PYTHON.with_name("pythonw.exe"))
        self.assertEqual(Path(command[1]), APP_DIR / "launch.py")
        self.assertEqual(start.call_args.kwargs["cwd"], APP_DIR)
        self.assertEqual(start.call_args.kwargs["env"]["PYTHONNOUSERSITE"], "1")

    def test_successful_setup_installs_only_in_venv_then_writes_stamp(self) -> None:
        with patch.object(Path, "is_file", return_value=True), \
                patch("bootstrap.venv_config_is_isolated", return_value=True), \
                patch("bootstrap.interpreter_ready", return_value=True), \
                patch("bootstrap.requirements_digest", return_value="new"), \
                patch("bootstrap.SETUP_STAMP", self.stamp), \
                patch("bootstrap.subprocess.run") as run:
            self.assertEqual(bootstrap.prepare_venv(Path(sys.executable)), bootstrap.VENV_PYTHON)
        self.assertEqual(self.stamp.read_text(encoding="ascii").strip(), "new")
        commands = [call.args[0] for call in run.call_args_list]
        self.assertTrue(all(Path(command[0]) == bootstrap.VENV_PYTHON for command in commands))
        self.assertIn("--no-user", commands[1])
        self.assertIn("--isolated", commands[1])

    def test_failed_install_does_not_mark_setup_as_complete(self) -> None:
        self.stamp.write_text("old", encoding="ascii")
        with patch.object(Path, "is_file", return_value=True), \
                patch("bootstrap.venv_config_is_isolated", return_value=True), \
                patch("bootstrap.SETUP_STAMP", self.stamp), \
                patch("bootstrap.subprocess.run", side_effect=[
                    Mock(returncode=0), subprocess.CalledProcessError(1, "pip"),
                ]):
            with self.assertRaises(subprocess.CalledProcessError):
                bootstrap.prepare_venv(Path(sys.executable))
        self.assertEqual(self.stamp.read_text(encoding="ascii"), "old")

    def test_setup_refuses_nonisolated_existing_venv(self) -> None:
        with patch.object(Path, "is_file", return_value=True), \
                patch("bootstrap.venv_config_is_isolated", return_value=False), \
                patch("bootstrap.subprocess.run") as run:
            with self.assertRaises(RuntimeError):
                bootstrap.prepare_venv(Path(sys.executable))
        run.assert_not_called()

    def test_changed_requirements_invalidate_ready_stamp(self) -> None:
        self.stamp.write_text("old", encoding="ascii")
        with patch("bootstrap.SETUP_STAMP", self.stamp), \
                patch("bootstrap.requirements_digest", return_value="new"), \
                patch("bootstrap.interpreter_ready") as ready:
            self.assertFalse(bootstrap.project_ready())
        ready.assert_not_called()

    def test_matching_stamp_and_isolated_dependencies_are_ready(self) -> None:
        self.stamp.write_text("same", encoding="ascii")
        with patch("bootstrap.SETUP_STAMP", self.stamp), \
                patch("bootstrap.requirements_digest", return_value="same"), \
                patch("bootstrap.interpreter_ready", return_value=True):
            self.assertTrue(bootstrap.project_ready())

    def test_unsupported_base_python_is_rejected(self) -> None:
        with patch("bootstrap.sys.version_info", (3, 14)), self.assertRaises(RuntimeError):
            bootstrap.main(["--setup"])


class LaunchTests(unittest.TestCase):
    def test_check_failure_reports_error_and_returns_failure(self) -> None:
        with patch("sys.argv", ["launch.py", "--check"]), \
                patch("launch.check_startup", side_effect=RuntimeError("test failure")), \
                patch("launch.report_error") as report:
            self.assertEqual(launch.main(), 1)
        self.assertIn("test failure", report.call_args.args[0])

    def test_error_log_and_popup(self) -> None:
        path = APP_DIR / "tests" / "runtime_data" / "launch" / "startup.log"
        try:
            with patch("launch.ERROR_LOG", path), patch("tkinter._default_root", None), \
                    patch("tkinter.Tk"), patch("tkinter.messagebox.showerror") as popup, \
                    patch("sys.stderr", None):
                launch.report_error("test diagnostic only")
            self.assertIn("test diagnostic only", path.read_text(encoding="utf-8"))
            self.assertIn(str(path), popup.call_args.args[1])
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
