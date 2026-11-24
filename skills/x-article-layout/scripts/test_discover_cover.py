"""Read-only cover discovery behavior, including priority and ambiguity."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


SCRIPT = Path(__file__).with_name("discover_cover.py")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


class DiscoverCoverTests(unittest.TestCase):
    def setUp(self):
        temp_root = os.environ.get("TEMP") or tempfile.gettempdir()
        Path(temp_root).mkdir(parents=True, exist_ok=True)
        self.work = tempfile.TemporaryDirectory(prefix="x-cover-discovery-", dir=temp_root)
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.vault = self.root / "vault"
        self.notes = self.vault / "文章"
        self.notes.mkdir(parents=True)
        self.source = self.notes / "2026-11-24-教程.md"
        self.output = self.root / "cover.json"

    def image(self, relative):
        path = self.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PNG)
        return path

    def run_cli(self, body, metadata=None, output=None):
        self.assertTrue(SCRIPT.is_file(), "Cover discovery CLI is missing")
        text = ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" if metadata is not None else "") + body
        self.source.write_bytes(text.encode("utf-8"))
        original = self.source.read_bytes()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(self.vault), "--source", str(self.source), "--output", str(output or self.output)],
            capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(self.source.read_bytes(), original, "Source must remain unchanged")
        return result

    def discover(self, body, metadata=None):
        result = self.run_cli(body, metadata)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8"))

    def test_first_directory_or_illustration_image_is_not_assumed_to_be_a_cover(self):
        self.image("文章/附件/2026-11-24-教程/目录.png")
        data = self.discover("# 教程\n\n## 目录\n\n![[文章/附件/2026-11-24-教程/目录.png|1000]]\n")
        self.assertEqual(data["status"], "missing")
        self.assertIsNone(data["path"])

    def test_explicit_frontmatter_wins_over_section_and_named_attachment(self):
        chosen = self.image("素材/指定封面.png")
        self.image("文章/section.png")
        self.image("文章/附件/2026-11-24-教程/另一个封面.png")
        data = self.discover("# 教程\n\n## 封面\n\n![封面](section.png)\n", {"cover": "![[素材/指定封面.png|1000]]"})
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))
        self.assertEqual(data["sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual((data["width"], data["height"], data["aspect_ratio"]), (1, 1, 1.0))
        self.assertEqual(data["selection_evidence"][0]["kind"], "frontmatter")

    def test_missing_explicit_reference_does_not_fall_back_to_another_image(self):
        self.image("文章/附件/2026-11-24-教程/真实封面.png")
        data = self.discover("# 教程\n", {"封面图": "![[不存在的封面.png]]"})
        self.assertEqual(data["status"], "invalid_reference")
        self.assertIsNone(data["path"])
        self.assertIn("missing_image", data["issues"][0]["code"])

    def test_conflicting_explicit_fields_are_ambiguous_without_guessing(self):
        self.image("素材/甲.png")
        self.image("素材/乙.png")
        data = self.discover("# 教程\n", {"cover": "素材/甲.png", "封面路径": "素材/乙.png"})
        self.assertEqual(data["status"], "ambiguous")
        self.assertEqual(len(data["candidates"]), 2)

    def test_duplicate_explicit_references_to_same_file_are_not_ambiguous(self):
        chosen = self.image("素材/唯一.png")
        data = self.discover("# 教程\n", {"cover_image": "[[素材/唯一.png]]", "封面": "![[素材/唯一.png|800]]"})
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))
        self.assertEqual(len(data["selection_evidence"]), 2)

    def test_cover_heading_selects_its_image_and_not_the_first_toc_image(self):
        self.image("文章/目录.png")
        chosen = self.image("文章/assets/hero (1).png")
        data = self.discover("# 教程\n\n![目录](目录.png)\n\n## 文章封面（5:2）\n\n![](<assets/hero (1).png>)\n\n## 正文\n\n继续。\n")
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))
        self.assertEqual(data["selection_evidence"][0]["kind"], "cover_section")

    def test_explicit_cover_label_supports_non_embedded_wikilink(self):
        chosen = self.image("文章/assets/封面.png")
        data = self.discover("# 教程\n\n**封面图：** [[assets/封面.png|查看原图]]\n")
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))

    def test_multiple_images_in_cover_section_are_ambiguous(self):
        self.image("文章/a.png")
        self.image("文章/b.png")
        data = self.discover("# 教程\n\n## 封面\n\n![第一版](a.png)\n\n![第二版](b.png)\n")
        self.assertEqual(data["status"], "ambiguous")

    def test_unique_explicitly_named_article_attachment_is_found(self):
        chosen = self.image("文章/附件/2026-11-24-教程/教程_封面_第1版.png")
        self.image("文章/附件/其他文章/其他封面.png")
        data = self.discover("# 教程\n")
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))
        self.assertEqual(data["selection_evidence"][0]["kind"], "named_attachment")

    def test_body_attachment_reference_scopes_a_shortened_article_folder(self):
        self.image("文章/附件/2026-11-24-主题/操作截图.png")
        chosen = self.image("文章/附件/2026-11-24-主题/教程封面.png")
        data = self.discover("# 教程\n\n![[文章/附件/2026-11-24-主题/操作截图.png]]\n")
        self.assertEqual(data["status"], "found")
        self.assertEqual(data["path"], str(chosen.resolve()))

    def test_multiple_versioned_cover_files_are_ambiguous(self):
        self.image("文章/附件/2026-11-24-教程/封面-v1.png")
        self.image("文章/附件/2026-11-24-教程/封面-v2.png")
        data = self.discover("# 教程\n")
        self.assertEqual(data["status"], "ambiguous")

    def test_remote_reference_is_invalid_and_is_never_downloaded(self):
        data = self.discover("# 教程\n", {"cover": "![封面](https://example.invalid/cover.png)"})
        self.assertEqual(data["status"], "invalid_reference")
        self.assertIn("remote_image_not_local", {issue["code"] for issue in data["issues"]})

    def test_cover_syntax_in_code_is_not_executed_or_selected(self):
        self.image("文章/假封面.png")
        data = self.discover("# 教程\n\n```markdown\n## 封面\n![[假封面.png]]\n```\n")
        self.assertEqual(data["status"], "missing")

    def test_corrupt_explicit_image_is_invalid_reference(self):
        path = self.vault / "坏封面.png"
        path.write_bytes(b"not an image")
        data = self.discover("# 教程\n", {"封面": "坏封面.png"})
        self.assertEqual(data["status"], "invalid_reference")

    def test_png_checksum_failure_is_invalid_reference_and_not_a_cli_crash(self):
        path = self.vault / "损坏校验封面.png"
        path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42AAAAAASUVORK5CYII="))
        data = self.discover("# 教程\n", {"封面": "损坏校验封面.png"})
        self.assertEqual(data["status"], "invalid_reference")

    def test_output_cannot_overwrite_the_source_or_write_into_vault(self):
        result = self.run_cli("# 原文\n", output=self.source)
        self.assertEqual(result.returncode, 2)
        self.assertIn("output_inside_vault", result.stderr)


if __name__ == "__main__":
    unittest.main()
