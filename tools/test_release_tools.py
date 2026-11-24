"""Synthetic checks for privacy diagnostics, archive paths and localization."""
import io
import unittest
import zipfile

from check_release import allowed, scan_text
from build_release import make_archive, skill_entries, SKILL


class ReleaseTests(unittest.TestCase):
    def test_runtime_data_and_unknown_files_are_excluded(self):
        self.assertTrue(allowed(SKILL + "scripts/prepare_article.py"))
        for value in ("output/cover.png", ".env", SKILL + "scripts/__pycache__/x.pyc", ".git/config", "notes/article.md"):
            self.assertFalse(allowed(value))

    def test_secret_findings_never_echo_the_match(self):
        token = "ghp_" + "a" * 36
        result = scan_text("one\n" + token, "example.txt")
        self.assertEqual(result, [{"category": "provider_token", "file": "example.txt", "line": 2}])
        self.assertNotIn(token, str(result))

    def test_personal_home_is_detected_while_generic_paths_are_allowed(self):
        private_path = "C:" + "/" + "Users" + "/" + "SyntheticPerson" + "/" + "notes"
        self.assertEqual(scan_text(private_path, "example.txt")[0]["category"], "personal_windows_home")
        self.assertEqual(scan_text("/absolute/path/vault D:/x-article-runs/round.mjs", "example.txt"), [])

    def test_archives_are_reproducible_and_do_not_store_machine_metadata(self):
        entries = {"skill/SKILL.md": b"example"}
        first = make_archive(entries)
        self.assertEqual(first, make_archive(entries))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertEqual(archive.namelist(), ["skill/SKILL.md"])
            info = archive.infolist()[0]
            self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(info.comment, b"")
            self.assertEqual(info.extra, b"")

    def test_archive_rejects_traversal(self):
        for name in ("../outside.txt", "/absolute.txt", "C:/drive.txt", "folder\\outside.txt"):
            with self.assertRaises(ValueError):
                make_archive({name: b"example"})

    def test_chinese_archive_uses_shared_code_with_a_localized_entry(self):
        source = {"LICENSE": b"MIT", "README.md": b"[skill](skills/x-article-layout/SKILL.md)", "README.zh-CN.md": b"Chinese README [English](README.md)"}
        source.update({name: b"example" for name in ("CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md", "VERSION")})
        source.update({SKILL + "SKILL.md": b"[English](SKILL.md) [Chinese](SKILL.zh-CN.md)",
                       SKILL + "SKILL.zh-CN.md": b"Chinese [English](SKILL.md)",
                       SKILL + "agents/openai.yaml": b"English UI", SKILL + "agents/openai.zh-CN.yaml": b"Chinese UI",
                       SKILL + "scripts/example.py": b"shared code"})
        entries = skill_entries(source, "zh-CN")
        self.assertEqual(entries["x-article-layout/SKILL.md"], b"Chinese [English](SKILL.en.md)")
        self.assertEqual(entries["x-article-layout/SKILL.zh-CN.md"], entries["x-article-layout/SKILL.md"])
        self.assertEqual(entries["x-article-layout/SKILL.en.md"], source[SKILL + "SKILL.md"].replace(b"](SKILL.md)", b"](SKILL.en.md)"))
        self.assertEqual(entries["x-article-layout/agents/openai.yaml"], b"Chinese UI")
        self.assertEqual(entries["x-article-layout/scripts/example.py"], b"shared code")
        self.assertIn(b"](./SKILL.en.md)", entries["x-article-layout/README.en.md"])
        self.assertIn(b"](README.en.md)", entries["x-article-layout/README.md"])


if __name__ == "__main__":
    unittest.main()
