"""Behavior checks for the read-only article preparation CLI.

Run with Python 3.10+. Fixtures use process TEMP or the platform temp folder.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("prepare_article.py")


class PrepareArticleTests(unittest.TestCase):
    def setUp(self):
        self.work = tempfile.TemporaryDirectory(
            prefix="x-article-parser-", dir=os.environ.get("TEMP") or None
        )
        self.addCleanup(self.work.cleanup)
        self.root = Path(self.work.name)
        self.vault = self.root / "vault"
        self.note_dir = self.vault / "notes"
        self.note_dir.mkdir(parents=True)
        self.source = self.note_dir / "教程.md"
        self.output = self.root / "prepared.json"

    def image(self, relative_path):
        target = self.vault / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # The parser validates file identity/existence, not image decoding.
        target.write_bytes(b"fixture-image-bytes\x00\x01")
        return target

    def run_cli(self, markdown, output=None):
        self.assertTrue(SCRIPT.is_file(), "Article preparation CLI is missing")
        self.source.write_bytes(markdown.encode("utf-8"))
        original = self.source.read_bytes()
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT), "--vault", str(self.vault),
                "--source", str(self.source), "--output", str(output or self.output),
            ],
            text=True, encoding="utf-8", capture_output=True, check=False,
        )
        self.assertEqual(self.source.read_bytes(), original, "Source was modified")
        return result

    def success(self, markdown):
        result = self.run_cli(markdown)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(self.output.read_text(encoding="utf-8"))

    def test_preserves_order_links_styles_and_escaped_table_pipes(self):
        image = self.image("output/图甲.png")
        markdown = (
            "---\n版本: 2\n使用依据: '[[内部依据]]'\n---\n\n# 测试 **标题**\n\n"
            "开头 **加粗**、*斜体* 和 [官网](https://example.com/a?q=1&b=2)。\n\n"
            "### 小节标题\n\n"
            "| 项目 | 说明 |\n| --- | --- |\n"
            "| A\\|B | [检查](https://example.com/check) |\n\n"
            "![[output/图甲.png|1000]]\n\n---\n\n结尾 `+86`。\n"
        )
        data = self.success(markdown)
        self.assertEqual(data["vault_path"], str(self.vault.resolve()))
        self.assertEqual(data["title"], "测试 标题")
        self.assertEqual(data["source_sha256"], hashlib.sha256(markdown.encode()).hexdigest())
        self.assertEqual([b["kind"] for b in data["blocks"]], ["text", "table", "image", "divider", "text"])
        self.assertEqual("".join(b["markdown"] for b in data["blocks"]), data["body_markdown"])
        self.assertNotIn("版本:", data["body_markdown"])
        self.assertNotIn("# 测试 **标题**", data["body_markdown"])
        first, table, picture, _, last = data["blocks"]
        self.assertIn("<strong>加粗</strong>", first["html"])
        self.assertIn("<em>斜体</em>", first["html"])
        self.assertIn('href="https://example.com/a?q=1&amp;b=2"', first["html"])
        self.assertIn("<h2>小节标题</h2>", first["html"])
        self.assertNotIn("<h3>", first["html"])
        self.assertIn("A\\|B", table["markdown"])
        self.assertIn("A|B", table["plain_text"])
        self.assertIn("项目\t说明\nA|B\t检查 (https://example.com/check)", table["plain_text"])
        self.assertIn('href="https://example.com/check"', table["html"])
        self.assertEqual((table["rows"], table["columns"], table["data_rows"]), (2, 2, 1))
        self.assertEqual(picture["path"], str(image.resolve()))
        self.assertEqual(picture["sha256"], hashlib.sha256(image.read_bytes()).hexdigest())
        self.assertIn("<code>+86</code>", last["html"])
        self.assertIn("heading_adapted", {w["code"] for w in data["warnings"]})
        self.assertNotIn("unsupported_wikilink", {w["code"] for w in data["warnings"]})

    def test_markdown_images_resolve_from_note_and_split_inline_in_order(self):
        image = self.image("notes/assets/a (1).png")
        data = self.success("# 图片测试\n\n前文 ![替代文字](<assets/a (1).png>) 后文。\n")
        self.assertEqual([b["kind"] for b in data["blocks"]], ["text", "image", "text"])
        self.assertEqual(data["blocks"][0]["plain_text"].strip(), "前文")
        self.assertEqual(data["blocks"][1]["path"], str(image.resolve()))
        self.assertEqual(data["blocks"][1]["plain_text"], "替代文字")
        self.assertEqual(data["blocks"][2]["plain_text"].strip(), "后文。")
        self.assertEqual("".join(b["markdown"] for b in data["blocks"]), data["body_markdown"])
        self.assertIn("inline_image_split", {w["code"] for w in data["warnings"]})

    def test_reference_links_and_reference_images_keep_targets(self):
        image = self.image("notes/图乙.png")
        data = self.success(
            "# 引用式语法\n\n[官网][site]\n\n![图乙][pic]\n\n结束。\n\n"
            "[site]: https://example.com/reference\n[pic]: 图乙.png\n"
        )
        self.assertIn('href="https://example.com/reference"', data["blocks"][0]["html"])
        self.assertEqual([b["path"] for b in data["blocks"] if b["kind"] == "image"], [str(image.resolve())])
        self.assertEqual("".join(b["markdown"] for b in data["blocks"]), data["body_markdown"])

    def test_image_example_in_inline_code_is_not_extracted_instead_of_real_image(self):
        self.image("notes/图.png")
        data = self.success("# 图片语法\n\n代码 `![图](图.png)` 然后实际图片 ![图](图.png) 后文。\n")
        self.assertIn("<code>![图](图.png)</code>", data["blocks"][0]["html"])
        self.assertIn("然后实际图片", data["blocks"][0]["plain_text"])
        self.assertEqual([b["kind"] for b in data["blocks"]], ["text", "image", "text"])

    def test_missing_image_stops_without_creating_output(self):
        result = self.run_cli("# 缺失图片\n\n![[output/不存在.png|1000]]\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing_image", result.stderr)
        self.assertFalse(self.output.exists())

    def test_external_images_are_not_downloaded_and_are_explicitly_flagged(self):
        data = self.success("# 外链图片\n\n![网络图](https://example.invalid/never-download.png)\n")
        picture = next(b for b in data["blocks"] if b["kind"] == "image")
        self.assertIsNone(picture["path"])
        self.assertIsNone(picture["sha256"])
        self.assertEqual(picture["url"], "https://example.invalid/never-download.png")
        self.assertIn("external_image_not_downloaded", {w["code"] for w in data["warnings"]})
        self.assertEqual(list(self.note_dir.iterdir()), [self.source])

    def test_wikilinks_remain_visible_and_warn_but_code_is_not_reinterpreted(self):
        data = self.success("# 本地链接\n\n请看 [[内部页面|说明]]，保留 `[[代码示例]]`。\n")
        self.assertIn("[[内部页面|说明]]", data["blocks"][0]["plain_text"])
        wiki_warnings = [w for w in data["warnings"] if w["code"] == "unsupported_wikilink"]
        self.assertEqual(len(wiki_warnings), 1)
        self.assertIn("内部页面", wiki_warnings[0]["message"])
        self.assertIn("<code>[[代码示例]]</code>", data["blocks"][0]["html"])

    def test_cjk_emphasis_handles_punctuation_next_to_chinese_without_touching_code_or_escapes(self):
        data = self.success(
            "# 中文强调\n\n**账号地区和电话区号分开选。**国家选。\n\n"
            "文字**“继续”**查看，*中文。*后续。\n\n**数据材料。**Excel、CSV。\n\n"
            "`**代码。**正文` 与 \\*\\*转义。\\*\\*正文。\n\n"
            "word**(latin)**next\n"
        )
        rich = data["blocks"][0]["html"]
        self.assertIn("<strong>账号地区和电话区号分开选。</strong>国家选。", rich)
        self.assertIn("文字<strong>“继续”</strong>查看", rich)
        self.assertIn("<em>中文。</em>后续", rich)
        self.assertIn("<strong>数据材料。</strong>Excel、CSV。", rich)
        self.assertIn("<code>**代码。**正文</code>", rich)
        self.assertIn("**转义。**正文", rich)
        self.assertNotIn("<strong>转义。", rich)
        self.assertIn("word**(latin)**next", rich)

    def test_obsidian_images_resolve_note_relative_and_unique_shortnames(self):
        first = self.image("notes/assets/相对图.png")
        second = self.image("shared/唯一短名.png")
        data = self.success("# 图片路径\n\n![[assets/相对图.png|800]]\n\n![[唯一短名.png]]\n")
        self.assertEqual([b["path"] for b in data["blocks"] if b["kind"] == "image"], [str(first.resolve()), str(second.resolve())])

    def test_ambiguous_obsidian_shortname_stops_instead_of_selecting_first_file(self):
        self.image("one/重名.png")
        self.image("two/重名.png")
        result = self.run_cli("# 歧义路径\n\n![[重名.png]]\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ambiguous_image", result.stderr)
        self.assertFalse(self.output.exists())

    def test_quotes_and_numbered_groups_keep_structure_while_h4_is_degraded(self):
        data = self.success("# 正文\n\n#### 提示\n\n> 第一段\n>\n> 第二段\n\n1. 第一步\n2. 第二步\n")
        rich = data["blocks"][0]["html"]
        self.assertIn("<strong>提示</strong>", rich)
        self.assertIn("<blockquote>", rich)
        self.assertIn("<ol>", rich)
        self.assertIn("<li>第一步</li>", rich)
        self.assertNotIn("<h4>", rich)

    def test_cannot_write_output_into_the_vault_or_overwrite_source(self):
        result = self.run_cli("# 不能覆盖\n\n正文\n", output=self.source)
        self.assertEqual(result.returncode, 2)
        self.assertIn("output_inside_vault", result.stderr)

    def test_local_image_outside_vault_is_not_hashed_or_uploaded(self):
        outside = self.root / "private.png"
        outside.write_bytes(b"private")
        result = self.run_cli("# 越界路径\n\n![图](../../private.png)\n")
        self.assertEqual(result.returncode, 2)
        self.assertIn("image_outside_vault", result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
