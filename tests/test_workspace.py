import tempfile
import unittest
from pathlib import Path

from garmin_data import safe_error
from prepare_openclaw import sync_workspace
from prepare_railway_build import FILES


class WorkspaceTests(unittest.TestCase):
    def test_rules_update_but_preferences_and_memory_survive(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as folder:
            root = Path(folder)
            source, target = root / "templates", root / "workspace"
            source.mkdir()
            for name in ["SOUL.md", "AGENTS.md", "USER.md", "MEMORY.md", "PREFERENCES.md"]:
                (source / name).write_text("initial", encoding="utf-8")
            sync_workspace(source, target)
            for name in ["USER.md", "MEMORY.md", "PREFERENCES.md"]:
                (target / name).write_text("user settings", encoding="utf-8")
            (source / "SOUL.md").write_text("new rules", encoding="utf-8")
            sync_workspace(source, target)
            self.assertEqual((target / "SOUL.md").read_text(encoding="utf-8"), "new rules")
            for name in ["USER.md", "MEMORY.md", "PREFERENCES.md"]:
                self.assertEqual((target / name).read_text(encoding="utf-8"), "user settings")
            backups = list((target / ".template-backups").glob("SOUL-*.md"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "initial")

    def test_deployment_includes_preferences_and_all_runtime_modules(self):
        root = Path(__file__).resolve().parents[1]
        for name in ["garmin_data.py", "garmin_extended.py", "coach/PREFERENCES.md"]:
            self.assertIn(name, FILES)
        self.assertNotIn("verify_mcp.py", FILES)
        self.assertTrue(all((root / name).is_file() for name in FILES))
        self.assertFalse(any(name.startswith((".private/", "tests/")) for name in FILES))

    def test_nested_errors_do_not_leak_messages(self):
        try:
            try:
                raise PermissionError("SECRET credential URL")
            except PermissionError as cause:
                raise RuntimeError("PRIVATE RESPONSE") from cause
        except RuntimeError as exc:
            result = safe_error(exc)
        self.assertEqual(result["error_types"], ["PermissionError", "RuntimeError"])
        self.assertNotIn("SECRET", str(result))


if __name__ == "__main__":
    unittest.main()
