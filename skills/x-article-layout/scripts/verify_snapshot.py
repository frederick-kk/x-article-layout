"""Read-only verification of a prepared article against readEditor JSON.

Run with Python 3.10+. Exit codes: 0 passed, 1 differences found,
2 invalid input, 3 content matched but explicit UI checks remain. Output is JSON
on stdout; inputs are never changed and this script does not access a browser.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import re
import sys
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Comment, NavigableString


def compact(value) -> str:
    """Normalize layout whitespace without merging ASCII words/numbers."""
    text = str(value or "").replace("\u200b", "")

    def ascii_word(character):
        return character.isascii() and (character.isalnum() or character == "_")

    def whitespace(match):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        return " " if ascii_word(before) and ascii_word(after) else ""

    return re.sub(r"\s+", whitespace, text)


def soup(fragment):
    return BeautifulSoup(fragment or "", "html.parser")


def html_text(element):
    """Extract content with boundaries between block elements, never URLs."""
    if isinstance(element, Comment):
        return ""
    if isinstance(element, NavigableString):
        return str(element)
    if element.name == "br":
        return "\n"
    content = "".join(html_text(child) for child in element.children)
    if element.name in {"p", "div", "blockquote", "pre", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ol", "ul", "table", "tr", "td", "th"}:
        return "\n" + content + "\n"
    return content


def links_in(element):
    return [{"text": compact(anchor.get_text()), "href": anchor.get("href", "")} for anchor in element.find_all("a", href=True)]


def observed_links(blocks):
    result = []
    for block in blocks:
        if "links" in block:
            result.extend({"text": compact(link.get("text")), "href": link.get("href", "")} for link in block["links"])
        else:
            result.extend(links_in(soup(block.get("html"))))
    return result


def expected_segments(blocks):
    segments = []
    for ordinal, block in enumerate(blocks):
        source_index = block.get("index", ordinal)
        if block["kind"] == "text":
            if not compact(soup(block.get("html")).get_text()):
                continue
            if segments and segments[-1]["kind"] == "text":
                segments[-1]["source_indices"].append(source_index)
                segments[-1]["html"] += block.get("html", "")
            else:
                segments.append({"kind": "text", "source_indices": [source_index], "html": block.get("html", "")})
        else:
            segments.append({"kind": block["kind"], "source_indices": [source_index], "block": block})
    return segments


def actual_segments(blocks):
    segments = []
    for ordinal, block in enumerate(blocks):
        tree = soup(block.get("html"))
        if block.get("tables"):
            kind = "table"
        elif block.get("images"):
            kind = "image"
        elif tree.find(attrs={"role": "separator"}) or tree.find("hr"):
            kind = "divider"
        elif block.get("tag", "").upper() == "SECTION":
            kind = "unknown_native_block"
        else:
            kind = "text"
        if kind == "text" and not compact(block.get("text")):
            continue  # The editor appends an empty paragraph after native blocks.
        if kind == "text" and segments and segments[-1]["kind"] == "text":
            segments[-1]["blocks"].append(block)
            segments[-1]["dom_indices"].append(ordinal)
        else:
            segments.append({"kind": kind, "blocks": [block], "dom_indices": [ordinal]})
    return segments


def table_details(html):
    table = soup(html).find("table")
    if table is None:
        return None
    rows = [row.find_all(["th", "td"], recursive=False) for row in table.find_all("tr")]
    return {
        "cells": [[compact(html_text(cell)) for cell in row] for row in rows],
        "cell_links": [[links_in(cell) for cell in row] for row in rows],
        "cell_codes": [[[code.get_text() for code in cell.find_all("code")] for cell in row] for row in rows],
        "links": links_in(table),
    }


def expected_lists(tree):
    groups = []
    for listing in tree.find_all(["ol", "ul"]):
        items = []
        for item in listing.find_all("li", recursive=False):
            own = soup(str(item))
            for nested in own.find_all(["ol", "ul"]):
                nested.decompose()
            items.append(compact(own.get_text()))
        groups.append({
            "kind": listing.name, "depth": len(listing.find_parents(["ol", "ul"])),
            "start": int(listing.get("start", 1)), "items": items,
        })
    return groups


def actual_lists(blocks):
    groups = []
    active = None
    unknown = []
    for ordinal, block in enumerate(blocks):
        if block.get("tag", "").upper() != "LI":
            active = None
            continue
        classes = block.get("cls", "")
        if "unordered" in classes.lower():
            kind = "ul"
        elif "ordered" in classes.lower():
            kind = "ol"
        else:
            kind = "unknown"
            unknown.append(ordinal)
        match = re.search(r"public-DraftStyleDefault-depth(\d+)", classes)
        depth = int(match.group(1)) if match else 0
        reset = "public-DraftStyleDefault-reset" in classes
        li = soup(block.get("html")).find("li")
        explicit_number = int(li["value"]) if li is not None and li.get("value", "").lstrip("-").isdigit() else None
        if active is None or (active["kind"], active["depth"]) != (kind, depth) or reset:
            active = {"kind": kind, "depth": depth, "reset": reset, "items": [], "numbers": [], "classes": classes}
            groups.append(active)
        active["items"].append(compact(block.get("text")))
        active["numbers"].append(explicit_number)
    return groups, unknown


def checkpoint_images(plan, checkpoint, errors):
    """Associate a checkpoint's media src order with its applied source blocks."""
    if checkpoint is None:
        return {}
    if checkpoint.get("source_sha256") and checkpoint["source_sha256"] != plan.get("source_sha256"):
        errors.append({"code": "checkpoint_source_mismatch", "message": "Checkpoint belongs to a different source version."})
        return {}
    if "editor_snapshot" in checkpoint:
        applied = [block for block in checkpoint.get("applied_blocks", []) if block.get("kind") == "image"]
        rendered = [image for block in checkpoint["editor_snapshot"].get("blocks", []) for image in block.get("images", [])]
        if len(applied) != len(rendered):
            errors.append({"code": "checkpoint_image_evidence_count_mismatch", "applied_images": len(applied), "snapshot_images": len(rendered)})
            return {}
        last = checkpoint.get("last_verified_index", float("inf"))
        return {
            block["index"]: {**block, "src": image.get("src", ""), "rendered_sha256": image.get("rendered_sha256")}
            for block, image in zip(applied, rendered) if block["index"] <= last
        }
    if "image_srcs" in checkpoint:
        images = [block for block in plan["blocks"] if block["kind"] == "image"]
        return {block["index"]: {"src": src} for block, src in zip(images, checkpoint["image_srcs"])}
    return {image["index"]: image for image in checkpoint.get("images", []) if "index" in image and "src" in image}


def verify_snapshot(plan, snapshot, checkpoint=None):
    errors, ui_checks, checked = [], [], []

    def error(code, source_indices=None, **detail):
        item = {"code": code, **detail}
        if source_indices is not None:
            item["source_indices"] = source_indices
        errors.append(item)

    def review(code, source_indices, **detail):
        ui_checks.append({"code": code, "source_indices": source_indices, **detail})

    def check_code_texts(code_texts, actual_verbatim, source_indices, **context):
        cursor = 0
        actual_verbatim = actual_verbatim.replace("\r\n", "\n").replace("\r", "\n")
        for ordinal, code_text in enumerate(code_texts):
            expected_code = code_text.replace("\r\n", "\n").replace("\r", "\n")
            position = actual_verbatim.find(expected_code, cursor)
            if position < 0:
                error("code_text_mismatch", source_indices, code_ordinal=ordinal, expected_verbatim=expected_code, **context)
            else:
                cursor = position + len(expected_code)

    if compact(plan.get("title")) != compact(snapshot.get("title")):
        error("title_mismatch", expected=plan.get("title"), actual=snapshot.get("title"))
    expected = expected_segments(plan["blocks"])
    actual = actual_segments(snapshot["blocks"])
    evidence = checkpoint_images(plan, checkpoint, errors)
    expected_counts = Counter(block["kind"] for block in plan["blocks"])
    observed_counts = {
        "image": sum(len(block.get("images", [])) for block in snapshot["blocks"]),
        "table": sum(len(block.get("tables", [])) for block in snapshot["blocks"]),
        "divider": sum(segment["kind"] == "divider" for segment in actual),
    }
    for kind, count in observed_counts.items():
        if expected_counts[kind] != count:
            error(f"{kind}_count_mismatch", expected=expected_counts[kind], actual=count)

    missing = []
    image_unverified = []
    table_cells_checked = 0
    for ordinal, wanted in enumerate(expected):
        indices = wanted["source_indices"]
        if ordinal >= len(actual):
            missing.extend(indices)
            continue
        found = actual[ordinal]
        if wanted["kind"] != found["kind"]:
            error("block_kind_mismatch", indices, expected=wanted["kind"], actual=found["kind"], dom_indices=found["dom_indices"])
            continue
        kind = wanted["kind"]
        expected_tree = soup(wanted["html"] if kind == "text" else wanted["block"].get("html", ""))
        formats = Counter(element.name for element in expected_tree.find_all(["strong", "b", "em", "i", "blockquote", "code", "pre", "del", "s", "u", "mark"]))
        if formats:
            review("formatting_requires_ui", indices, formats=dict(formats), message="Text/structure checks do not prove the visible bold, italic, quote, or code styling; inspect these formats in the editor.")
        if kind == "text":
            expected_text = compact(html_text(expected_tree))
            actual_verbatim = "\n".join(block.get("text", "") for block in found["blocks"])
            actual_text = compact(actual_verbatim)
            if expected_text != actual_text:
                position = next((index for index, pair in enumerate(zip(expected_text, actual_text)) if pair[0] != pair[1]), min(len(expected_text), len(actual_text)))
                error("body_text_mismatch", indices, first_difference=position, expected_excerpt=expected_text[max(0, position - 20) : position + 60], actual_excerpt=actual_text[max(0, position - 20) : position + 60])
            check_code_texts([element.get_text() for element in expected_tree.find_all("code")], actual_verbatim, indices)
            expected_links = links_in(expected_tree)
            actual_links = observed_links(found["blocks"])
            if expected_links != actual_links:
                error("body_links_mismatch", indices, expected=expected_links, actual=actual_links)
            wanted_headings = [(element.name.upper(), compact(element.get_text())) for element in expected_tree.find_all(re.compile(r"^h[1-6]$"))]
            found_headings = [(block["tag"].upper(), compact(block.get("text"))) for block in found["blocks"] if re.fullmatch(r"H[1-6]", block.get("tag", "").upper())]
            if wanted_headings != found_headings:
                error("heading_levels_mismatch", indices, expected=wanted_headings, actual=found_headings)
            wanted_lists = expected_lists(expected_tree)
            found_lists, unknown_lists = actual_lists(found["blocks"])
            if unknown_lists:
                review("list_type_requires_ui", indices, local_dom_indices=unknown_lists)
            if any(group["depth"] for group in wanted_lists + found_lists):
                review("nested_list_groups_require_ui", indices, message="Single-block outerHTML does not prove nested list grouping.")
            else:
                signature = lambda groups: [(group["kind"], group["depth"], group["items"]) for group in groups]
                if signature(wanted_lists) != signature(found_lists):
                    error("list_groups_mismatch", indices, expected=signature(wanted_lists), actual=signature(found_lists))
                else:
                    unproven = []
                    for group_index, (left, right) in enumerate(zip(wanted_lists, found_lists)):
                        if left["kind"] != "ol":
                            continue
                        expected_numbers = list(range(left["start"], left["start"] + len(left["items"])))
                        if all(number is not None for number in right["numbers"]):
                            if right["numbers"] != expected_numbers:
                                error("ordered_list_numbers_mismatch", indices, group=group_index, expected=expected_numbers, actual=right["numbers"])
                        else:
                            unproven.append({"group": group_index, "expected_numbers": expected_numbers, "reset_marker_observed": right["reset"]})
                            if left["start"] == 1 and not right["reset"] and "ordered-list-item" in right["classes"]:
                                error("ordered_list_reset_missing", indices, group=group_index)
                    if unproven:
                        review("ordered_list_numbers_require_ui", indices, groups=unproven, message="CSS reset classes prove grouping markers, not the actual rendered numerals. Check the visible numbering and restarts in the UI.")
        elif kind == "table":
            source_table = table_details(wanted["block"].get("html"))
            actual_block = found["blocks"][0]
            if source_table is None or len(actual_block.get("tables", [])) != 1:
                error("table_structure_unavailable", indices)
                continue
            actual_table = actual_block["tables"][0]
            actual_cells = [[compact(value) for value in row] for row in actual_table.get("cells", [])]
            if source_table["cells"] != actual_cells:
                error("table_cell_text_mismatch", indices, expected=source_table["cells"], actual=actual_cells)
            for row_index, row in enumerate(source_table["cell_codes"]):
                for column_index, code_texts in enumerate(row):
                    raw_cells = actual_table.get("cells", [])
                    actual_cell = str(raw_cells[row_index][column_index]) if row_index < len(raw_cells) and column_index < len(raw_cells[row_index]) else ""
                    check_code_texts(code_texts, actual_cell, indices, row=row_index, column=column_index)
            table_cells_checked += sum(len(row) for row in source_table["cells"])
            html_table = table_details(actual_block.get("html"))
            aggregate_links = [{"text": compact(link.get("text")), "href": link.get("href", "")} for link in actual_table.get("links", [])]
            if source_table["links"] != aggregate_links:
                error("table_links_mismatch", indices, expected=source_table["links"], actual=aggregate_links)
            if html_table is None:
                review("table_cell_links_require_ui", indices, message="Snapshot has no table HTML; link-to-cell positions are unproven.")
            elif source_table["cell_links"] != html_table["cell_links"]:
                error("table_cell_links_mismatch", indices, expected=source_table["cell_links"], actual=html_table["cell_links"])
        elif kind == "image":
            images = found["blocks"][0].get("images", [])
            if len(images) != 1:
                error("image_native_block_count_mismatch", indices, actual=len(images))
                continue
            image = images[0]
            if not image.get("src") or image.get("width", 0) <= 0 or image.get("height", 0) <= 0:
                error("image_not_loaded", indices)
            recorded = evidence.get(indices[0])
            if recorded is None:
                image_unverified.extend(indices)
            else:
                for key in ("path", "sha256"):
                    if key in recorded and recorded[key] != wanted["block"].get(key):
                        error("checkpoint_image_source_mismatch", indices, field=key)
                old_digest = recorded.get("rendered_sha256")
                current_digest = image.get("rendered_sha256")
                if old_digest and current_digest:
                    if old_digest.lower() != current_digest.lower():
                        error("image_rendered_hash_mismatch", indices, expected=old_digest, actual=current_digest)
                elif urlsplit(recorded.get("src", "")).scheme == "https" and urlsplit(image.get("src", "")).scheme == "https":
                    if recorded["src"] != image.get("src"):
                        error("image_src_order_mismatch", indices, expected=recorded["src"], actual=image.get("src"))
                else:
                    # X can recreate blob URLs when the same draft is reopened.
                    # Equality/difference of a session URL proves no persistent
                    # image identity; compare displayed content hashes instead.
                    image_unverified.extend(indices)
        checked.extend(indices)

    if missing:
        error("missing_source_blocks", missing)
    if len(actual) > len(expected):
        error("unexpected_editor_segments", actual_segments=len(actual), expected_segments=len(expected), dom_indices=[index for segment in actual[len(expected) :] for index in segment["dom_indices"]])
    if image_unverified:
        review("image_identity_requires_ui", image_unverified, message="Counts and native positions were checked, but both sides need rendered_sha256 or stable HTTPS media URLs to prove image identity. Blob URLs are session identifiers and may change when reopening a draft; original file hashes are not compared with X-compressed images.")
    return {
        "status": "failed" if errors else "needs_ui_check" if ui_checks else "passed",
        "errors": errors, "ui_checks": ui_checks,
        "missing_source_indices": missing, "checked_source_indices": checked,
        "counts": {"expected": dict(expected_counts), "observed": observed_counts, "expected_segments": len(expected), "observed_segments": len(actual), "table_cells_checked": table_cells_checked},
        "text_comparison": "HTML content with block boundaries; ASCII word/number separators preserved, other layout whitespace normalized; code text checked verbatim and links compared separately.",
    }


def main(argv=None):
    # Keep machine-readable output UTF-8 under Windows' legacy GBK locale,
    # including when a caller launches sys.executable without -X utf8.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--checkpoint", type=Path, help="Optional importer state.json containing applied_blocks and editor_snapshot.")
    args = parser.parse_args(argv)
    try:
        read = lambda path: json.loads(path.read_text(encoding="utf-8-sig"))
        report = verify_snapshot(read(args.plan), read(args.snapshot), read(args.checkpoint) if args.checkpoint else None)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {"passed": 0, "failed": 1, "needs_ui_check": 3}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
