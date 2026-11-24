"""Behavior checks for read-only X editor snapshot verification."""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("verify_snapshot.py")


def dom(text, html=None, tag="DIV", cls="longform-unstyled", **extra):
    return {"tag": tag, "cls": cls, "text": text, "html": html or f"<div>{text}</div>", "images": [], "tables": [], "links": [], **extra}


def native_image(src):
    return dom("Provide a caption (optional)", f'<section><img src="{src}"></section>', tag="SECTION", cls="", images=[{"src": src, "width": 1200, "height": 800}])


def ordered_item(text, reset=False):
    cls = "longform-ordered-list-item public-DraftStyleDefault-orderedListItem public-DraftStyleDefault-depth0"
    if reset:
        cls += " public-DraftStyleDefault-reset"
    return dom(text, f'<li class="{cls}">{text}</li>', tag="LI", cls=cls)


class VerifySnapshotTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="x-snapshot-check-", dir=os.environ["TEMP"])
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)

    def run_check(self, blocks, observed, checkpoint=None):
        self.assertTrue(SCRIPT.is_file(), "Snapshot verification CLI is missing")
        plan = {"title": "测试标题", "source_sha256": "source-hash", "blocks": blocks}
        snapshot = {"title": "测试标题", "blocks": observed}
        paths = {}
        for name, value in (("plan", plan), ("snapshot", snapshot), ("checkpoint", checkpoint)):
            if value is not None:
                path = self.root / f"{name}.json"
                path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                paths[name] = path
        before = {name: path.read_bytes() for name, path in paths.items()}
        command = [sys.executable, str(SCRIPT), "--plan", str(paths["plan"]), "--snapshot", str(paths["snapshot"])]
        if checkpoint is not None:
            command.extend(["--checkpoint", str(paths["checkpoint"])])
        result = subprocess.run(command, text=True, encoding="utf-8", capture_output=True, check=False)
        for name, path in paths.items():
            self.assertEqual(path.read_bytes(), before[name], f"Input {name} was modified")
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_uses_expected_html_text_and_groups_multiple_dom_blocks(self):
        blocks = [{"index": 0, "kind": "text", "html": '<p>前文<a href="https://example.com">官网</a>。</p><p>后文</p>', "plain_text": "1. 前文官网 (https://example.com)。后文"}]
        observed = [dom("前文官网。", '<div>前文<a href="https://example.com">官网</a>。</div>', links=[{"text": "官网", "href": "https://example.com"}]), dom("后文")]
        code, report = self.run_check(blocks, observed)
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "passed")

    def test_missing_english_word_separator_is_a_body_difference(self):
        blocks = [{"index": 0, "kind": "text", "html": "<p><strong>重点</strong> pip install</p>"}]
        code, report = self.run_check(blocks, [dom("重点 pipinstall")])
        self.assertEqual(code, 1, report)
        self.assertIn("body_text_mismatch", {item["code"] for item in report["errors"]})

    def test_code_spaces_are_checked_verbatim_beyond_normal_word_separation(self):
        blocks = [{"index": 0, "kind": "text", "html": "<p>运行 <code>pip  install --name a b</code>。</p>"}]
        code, report = self.run_check(blocks, [dom("运行 pip install --name a b。")])
        self.assertEqual(code, 1, report)
        self.assertIn("code_text_mismatch", {item["code"] for item in report["errors"]})

    def test_matching_inline_and_quote_content_still_requires_formatting_ui_check(self):
        blocks = [{"index": 0, "kind": "text", "html": "<p><strong>重点</strong> <em>提示</em> <code>pip  install</code></p><blockquote><p>引用</p></blockquote>"}]
        code, report = self.run_check(blocks, [dom("重点 提示 pip  install"), dom("引用")])
        self.assertEqual(code, 3, report)
        self.assertEqual(report["errors"], [])
        checks = [item for item in report["ui_checks"] if item["code"] == "formatting_requires_ui"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(set(checks[0]["formats"]), {"strong", "em", "code", "blockquote"})

    def test_separate_english_paragraphs_preserve_a_word_boundary(self):
        blocks = [{"index": 0, "kind": "text", "html": "<p>First paragraph</p><p>Second paragraph</p>"}]
        code, report = self.run_check(blocks, [dom("First paragraph"), dom("Second paragraph")])
        self.assertEqual(code, 0, report)

    def test_missing_tail_reports_missing_source_indices(self):
        blocks = [{"index": 0, "kind": "text", "html": "<p>开头</p>"}, {"index": 1, "kind": "divider", "html": "<hr>"}, {"index": 2, "kind": "text", "html": "<p>结尾</p>"}]
        code, report = self.run_check(blocks, [dom("开头")])
        self.assertEqual(code, 1)
        self.assertEqual(report["missing_source_indices"], [1, 2])

    def test_same_characters_with_wrong_body_link_do_not_pass(self):
        blocks = [{"index": 0, "kind": "text", "html": '<p><a href="https://good.example">官网</a></p>'}]
        observed = [dom("官网", '<div><a href="https://wrong.example">官网</a></div>', links=[{"text": "官网", "href": "https://wrong.example"}])]
        code, report = self.run_check(blocks, observed)
        self.assertEqual(code, 1)
        self.assertIn("body_links_mismatch", {error["code"] for error in report["errors"]})

    def test_all_table_cells_and_cell_link_positions_are_compared(self):
        expected = '<table><tr><th>A</th><th>B</th></tr><tr><td>甲</td><td><a href="https://example.com">链接</a></td></tr></table>'
        actual = '<section><table><tr><th>A</th><th>B</th></tr><tr><td>错误<a href="https://example.com">链接</a></td><td>甲</td></tr></table></section>'
        blocks = [{"index": 0, "kind": "table", "html": expected, "rows": 2, "columns": 2}]
        observed = [dom("", actual, tag="SECTION", cls="", tables=[{"cells": [["A", "B"], ["错误链接", "甲"]], "links": [{"text": "链接", "href": "https://example.com"}]}])]
        code, report = self.run_check(blocks, observed)
        self.assertEqual(code, 1)
        codes = {error["code"] for error in report["errors"]}
        self.assertIn("table_cell_text_mismatch", codes)
        self.assertIn("table_cell_links_mismatch", codes)

    def test_matching_native_table_and_divider_pass(self):
        table = '<table><tr><th>A</th><th>B</th></tr><tr><td>甲</td><td>乙</td></tr></table>'
        blocks = [{"index": 0, "kind": "table", "html": table}, {"index": 1, "kind": "divider", "html": "<hr>"}]
        observed = [dom("", f"<section>{table}</section>", tag="SECTION", cls="", tables=[{"cells": [["A", "B"], ["甲", "乙"]], "links": []}]), dom("", '<section><div role="separator"></div></section>', tag="SECTION", cls="")]
        code, report = self.run_check(blocks, observed)
        self.assertEqual(code, 0, report)

    def test_image_order_uses_checkpoint_media_sources_not_compressed_hashes(self):
        blocks = [{"index": 0, "kind": "image", "path": "D:/vault/a.png", "sha256": "a"}, {"index": 1, "kind": "image", "path": "D:/vault/b.png", "sha256": "b"}]
        first = "https://pbs.twimg.com/media/first.jpg"
        second = "https://pbs.twimg.com/media/second.jpg"
        checkpoint = {"source_sha256": "source-hash", "last_verified_index": 1, "applied_blocks": deepcopy(blocks), "editor_snapshot": {"blocks": [native_image(first), native_image(second)]}}
        code, report = self.run_check(blocks, [native_image(second), native_image(first)], checkpoint)
        self.assertEqual(code, 1)
        self.assertIn("image_src_order_mismatch", {error["code"] for error in report["errors"]})
        code, report = self.run_check(blocks, [native_image(first), native_image(second)], checkpoint)
        self.assertEqual(code, 0, report)

    def test_reopened_same_image_with_new_blob_url_requires_review_instead_of_false_identity_error(self):
        block = {"index": 0, "kind": "image", "path": "D:/vault/a.png", "sha256": "original-file-hash"}
        checkpoint = {"source_sha256": "source-hash", "last_verified_index": 0, "applied_blocks": [block], "editor_snapshot": {"blocks": [native_image("blob:https://x.com/old-session")]}}
        code, report = self.run_check([block], [native_image("blob:https://x.com/reopened-session")], checkpoint)
        self.assertEqual(code, 3, report)
        self.assertEqual(report["errors"], [])
        self.assertIn("image_identity_requires_ui", {item["code"] for item in report["ui_checks"]})

    def test_rendered_content_hash_verifies_reopened_blob_image(self):
        block = {"index": 0, "kind": "image", "path": "D:/vault/a.png", "sha256": "original-file-hash"}
        old = native_image("blob:https://x.com/old-session")
        old["images"][0]["rendered_sha256"] = "c" * 64
        current = native_image("blob:https://x.com/new-session")
        current["images"][0]["rendered_sha256"] = "c" * 64
        checkpoint = {"source_sha256": "source-hash", "last_verified_index": 0, "applied_blocks": [block], "editor_snapshot": {"blocks": [old]}}
        code, report = self.run_check([block], [current], checkpoint)
        self.assertEqual(code, 0, report)
        current["images"][0]["rendered_sha256"] = "d" * 64
        code, report = self.run_check([block], [current], checkpoint)
        self.assertEqual(code, 1, report)
        self.assertIn("image_rendered_hash_mismatch", {item["code"] for item in report["errors"]})

    def test_image_without_identity_evidence_requires_ui_check(self):
        code, report = self.run_check([{"index": 0, "kind": "image", "sha256": "original-not-remote-hash"}], [native_image("https://pbs.twimg.com/compressed.jpg")])
        self.assertEqual(code, 3)
        self.assertEqual(report["status"], "needs_ui_check")
        self.assertIn("image_identity_requires_ui", {item["code"] for item in report["ui_checks"]})

    def test_missing_native_heading_is_reported_even_when_text_matches(self):
        code, report = self.run_check([{"index": 9, "kind": "text", "html": "<h1>章节标题</h1>"}], [dom("章节标题")])
        self.assertEqual(code, 1)
        self.assertIn("heading_levels_mismatch", {error["code"] for error in report["errors"]})

    def test_css_only_ordered_lists_do_not_falsely_pass_rendered_number_checks(self):
        block = {"index": 0, "kind": "text", "html": "<ol><li>甲</li><li>乙</li></ol><p>间隔</p><ol><li>丙</li></ol>"}
        code, report = self.run_check([block], [ordered_item("甲", True), ordered_item("乙"), dom("间隔"), ordered_item("丙", True)])
        self.assertEqual(code, 3, report)
        self.assertEqual(report["errors"], [])
        self.assertIn("ordered_list_numbers_require_ui", {item["code"] for item in report["ui_checks"]})

    def test_missing_ordered_list_reset_marker_is_reported(self):
        block = {"index": 0, "kind": "text", "html": "<ol><li>甲</li></ol><p>间隔</p><ol><li>乙</li></ol>"}
        code, report = self.run_check([block], [ordered_item("甲", True), dom("间隔"), ordered_item("乙")])
        self.assertEqual(code, 1)
        self.assertIn("ordered_list_reset_missing", {error["code"] for error in report["errors"]})


if __name__ == "__main__":
    unittest.main()
