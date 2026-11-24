"""Prepare a read-only Obsidian article for the X Articles draft workflow.

Runtime: Python 3.10+ with the packages listed in requirements.txt.
No HTTP requests, image generation, rasterization, or Vault writes occur here.
The original table Markdown is authoritative; cells are parser-provided inline
Markdown (escaped table delimiters are already unescaped by markdown-it-py).
Rows include the header; data_rows excludes it. Source hashes cover exact bytes.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import glob
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

try:
    from bs4 import BeautifulSoup
    from markdown_it import MarkdownIt
    from markdown_it.rules_inline import image as markdown_image
    from markdown_it.rules_inline.state_inline import Delimiter
except ImportError as exc:
    raise SystemExit(
        "dependency_missing: install requirements.txt with the Python interpreter "
        "used for this run (python -m pip install -r requirements.txt)"
    ) from exc


class ArticleError(ValueError):
    pass


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".svg"}


def plain_text(rendered_html: str) -> str:
    """Produce a useful clipboard fallback, including link destinations."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    for link in soup.find_all("a", href=True):
        label = link.get_text()
        destination = link["href"]
        link.replace_with(label if label == destination else f"{label} ({destination})")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for listing in soup.find_all(["ol", "ul"]):
        start = int(listing.get("start", 1)) if listing.name == "ol" else 1
        for number, item in enumerate(listing.find_all("li", recursive=False), start):
            item.insert(0, f"{number}. " if listing.name == "ol" else "• ")
    for table in soup.find_all("table"):
        rows = [
            "\t".join(cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False))
            for row in table.find_all("tr")
        ]
        table.replace_with("\n".join(rows))
    return re.sub(r"\n{3,}", "\n\n", soup.get_text()).strip()


def parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")

    def issue(state, code, message):
        if not state.env.get("suppress_issues"):
            state.env.setdefault("issues", []).append({"code": code, "message": message})

    def obsidian(state, silent):
        start = state.pos
        embedded = state.src.startswith("![[", start)
        if not embedded and not state.src.startswith("[[", start):
            return False
        label_start = start + (3 if embedded else 2)
        end = state.src.find("]]", label_start, state.posMax)
        if end < 0 or "\n" in state.src[label_start:end]:
            return False
        raw = state.src[start : end + 2]
        target, _, size = state.src[label_start:end].partition("|")
        if not silent:
            if embedded and Path(target).suffix.lower() in IMAGE_EXTENSIONS:
                token = state.push("image", "img", 0)
                token.attrs = {"src": target.strip(), "alt": ""}
                token.content = Path(target).stem
                token.meta = {
                    "source": raw, "source_start": start, "source_end": end + 2,
                    "obsidian": True, "display_size": size,
                }
            else:
                token = state.push("text", "", 0)
                token.content = raw
                issue(
                    state, "unsupported_embed" if embedded else "unsupported_wikilink",
                    f"Preserved local Obsidian syntax as visible text: {raw}",
                )
        state.pos = end + 2
        return True

    def positioned_image(state, silent):
        start, token_count = state.pos, len(state.tokens)
        matched = markdown_image(state, silent)
        if matched and not silent:
            for token in state.tokens[token_count:]:
                if token.type == "image":
                    token.meta.update({
                        "source": state.src[start : state.pos],
                        "source_start": start, "source_end": state.pos,
                        "obsidian": False,
                    })
        return matched

    def cjk_emphasis(state, silent):
        """Keep upstream balancing; expand delimiter flanking for CJK letters.

        CommonMark treats punctuation before a closing marker plus a following
        Chinese letter as non-closing. Obsidian permits it. Code and escapes are
        consumed by earlier markdown-it rules, never by this emphasis rule.
        """
        start = state.pos
        marker = state.srcCharCode[start]
        if silent or marker not in {0x5F, 0x2A}:
            return False
        scanned = state.scanDelims(start, marker == 0x2A)
        before = state.src[start - 1] if start else " "
        after_pos = start + scanned.length
        after = state.src[after_pos] if after_pos < state.posMax else " "

        def cjk_letter(character):
            return character.isalnum() and unicodedata.east_asian_width(character) in {"W", "F"}

        def cjk_punctuation(character):
            return unicodedata.category(character).startswith("P") and unicodedata.east_asian_width(character) in {"W", "F"}

        can_open = scanned.can_open or ((cjk_letter(before) or cjk_punctuation(after)) and not after.isspace())
        can_close = scanned.can_close or ((cjk_letter(after) or cjk_punctuation(before)) and not before.isspace())
        if (can_open, can_close) != (scanned.can_open, scanned.can_close):
            if not any(item["code"] == "cjk_emphasis_adapted" for item in state.env.get("issues", [])):
                issue(state, "cjk_emphasis_adapted", "Applied Obsidian-compatible emphasis boundaries next to CJK letters; original Markdown is unchanged.")
        for index in range(scanned.length):
            token = state.push("text", "", 0)
            token.content = chr(marker)
            state.delimiters.append(Delimiter(
                marker=marker, length=scanned.length, jump=index,
                token=len(state.tokens) - 1, end=-1, open=can_open, close=can_close,
            ))
        state.pos += scanned.length
        return True

    md.inline.ruler.before("image", "obsidian", obsidian)
    md.inline.ruler.at("image", positioned_image)
    md.inline.ruler.at("emphasis", cjk_emphasis)

    # Only rendered HTML changes; the original Markdown remains untouched.
    def heading_open(tokens, index, options, env):
        level = int(tokens[index].tag[1])
        return "<p><strong>" if level >= 4 else f"<h{max(1, level - 1)}>"

    def heading_close(tokens, index, options, env):
        level = int(tokens[index].tag[1])
        return "</strong></p>\n" if level >= 4 else f"</h{max(1, level - 1)}>\n"

    def literal_html(tokens, index, options, env):
        return html.escape(tokens[index].content)

    md.renderer.rules.update({
        "heading_open": heading_open, "heading_close": heading_close,
        "html_inline": literal_html, "html_block": literal_html,
    })
    return md


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))
    return offsets


def remove_frontmatter(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return text
    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            # A leading thematic break is not automatically YAML metadata.
            candidate = "".join(lines[1:index])
            if re.search(r"(?m)^[^#\s][^\n:]*:\s", candidate):
                return "".join(lines[index + 1 :])
            return text
    if re.search(r"(?m)^[^#\s][^\n:]*:\s", "".join(lines[1:])):
        raise ArticleError("unclosed_frontmatter: YAML metadata has no closing delimiter")
    return text


def image_source_position(body: str, offsets: list[int], inline, position: int) -> int:
    """Map the parser's inline offset back to raw Markdown, including prefixes.

    Exact offsets distinguish actual images from identical syntax inside code.
    Unmappable container/tab transformations stop rather than guessing.
    """
    prefix = inline.content[:position]
    relative_line = prefix.count("\n")
    column = len(prefix.rsplit("\n", 1)[-1])
    content_lines = inline.content.split("\n")
    line_number = inline.map[0] + relative_line
    raw_line = body[offsets[line_number] : offsets[line_number + 1]].rstrip("\n")
    line_start = raw_line.find(content_lines[relative_line])
    if line_start < 0:
        raise ArticleError("image_source_unmapped: image source uses an unsupported container/tab transformation")
    return offsets[line_number] + line_start + column


def local_image(token, vault: Path, source: Path, shortname_cache: dict) -> dict:
    reference = token.attrGet("src") or ""
    parsed = urlsplit(reference)
    if parsed.scheme and not re.match(r"^[A-Za-z]:[/\\]", reference) or reference.startswith("//"):
        return {"path": None, "sha256": None, "url": reference}
    file_reference = unquote(parsed.path).replace("\\", "/")
    candidate = Path(file_reference)
    if candidate.is_absolute():
        candidates = [candidate.resolve()]
    else:
        bases = [vault, source.parent] if token.meta.get("obsidian") else [source.parent, vault]
        candidates = [(base / candidate).resolve() for base in bases]
    allowed = list(dict.fromkeys(path for path in candidates if path.is_relative_to(vault)))
    if not allowed:
        raise ArticleError(f"image_outside_vault: {reference}")
    found = [path for path in allowed if path.is_file()]
    if token.meta.get("obsidian") and len(found) > 1:
        raise ArticleError(f"ambiguous_image: {reference} matches more than one exact Vault/note-relative file")
    if not found and token.meta.get("obsidian"):
        key = candidate.name.casefold()
        if key not in shortname_cache:
            shortname_cache[key] = [
                path.resolve() for path in vault.rglob(glob.escape(candidate.name))
                if path.is_file() and path.resolve().is_relative_to(vault)
            ]
        found = shortname_cache[key]
        if len(candidate.parts) > 1:
            suffix = "/" + candidate.as_posix().casefold().lstrip("./")
            found = [path for path in found if path.as_posix().casefold().endswith(suffix)]
        if len(found) > 1:
            raise ArticleError(f"ambiguous_image: {reference} matches {len(found)} files inside the Vault")
    if found:
        path = found[0]
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    raise ArticleError(f"missing_image: {reference}")


def prepare_article(vault: Path, source: Path) -> dict:
    if not vault.is_absolute() or not source.is_absolute():
        raise ArticleError("absolute_paths_required: --vault and --source must be absolute")
    vault, source = vault.resolve(), source.resolve()
    if not source.is_relative_to(vault):
        raise ArticleError("source_outside_vault: source must be inside --vault")
    if not source.is_file():
        raise ArticleError("source_missing: source Markdown file does not exist")
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    body = remove_frontmatter(text)
    md = parser()
    first_env = {}
    initial = md.parse(body, first_env)
    offsets = line_offsets(body)
    title = source.stem
    warnings = []
    for index, token in enumerate(initial):
        if token.type == "heading_open" and token.tag == "h1":
            title = plain_text(md.renderer.renderInline(initial[index + 1].children or [], md.options, first_env))
            start, end = (offsets[line] for line in token.map)
            body = body[:start] + body[end:]
            break
    else:
        warnings.append({"code": "missing_h1", "message": "No H1 found; using source filename as title."})

    env = {}
    tokens = md.parse(body, env)
    warnings.extend(env.get("issues", []))
    offsets = line_offsets(body)
    events = []
    table_ranges = []
    shortname_cache = {}

    for index, token in enumerate(tokens):
        line = token.map[0] + 1 if token.map else None
        if token.type == "heading_open" and int(token.tag[1]) >= 2:
            level = int(token.tag[1])
            warnings.append({
                "code": "heading_degraded" if level >= 4 else "heading_adapted", "line": line,
                "message": f"Rendered H{level} as " + ("a standalone bold paragraph." if level >= 4 else f"H{level - 1} for the X editor."),
            })
        if token.type in {"fence", "code_block", "html_block"}:
            warnings.append({"code": "code_or_html_requires_review", "line": line, "message": f"Preserved {token.type}; review editor compatibility."})
        if token.type == "inline" and any(child.type == "html_inline" for child in token.children or []):
            warnings.append({"code": "raw_html_preserved_as_text", "line": line, "message": "Inline HTML is escaped and kept visible rather than executed."})
        if token.type not in {"table_open", "hr"}:
            continue
        start, end = (offsets[value] for value in token.map)
        event = {"start": start, "end": end, "kind": "table" if token.type == "table_open" else "divider"}
        if token.type == "table_open":
            closing = next(position for position in range(index + 1, len(tokens)) if tokens[position].type == "table_close")
            rows = []
            current = None
            for member in tokens[index : closing + 1]:
                if member.type == "tr_open":
                    current = []
                    rows.append(current)
                elif member.type == "inline" and current is not None:
                    current.append(member.content)
            event.update({"cells": rows, "rows": len(rows), "columns": len(rows[0]), "data_rows": max(0, len(rows) - 1)})
            table_ranges.append((start, end))
        if token.level:
            warnings.append({"code": "nested_block_split", "line": line, "message": "Splitting a table/divider inside a container can change surrounding layout; review it."})
        events.append(event)

    for token in tokens:
        if token.type != "inline" or not token.map:
            continue
        start, end = (offsets[value] for value in token.map)
        if any(left <= start < right for left, right in table_ranges):
            if any(child.type == "image" for child in token.children or []):
                warnings.append({"code": "image_in_table_requires_review", "line": token.map[0] + 1, "message": "Image syntax remains inside original table Markdown; it is not uploaded separately."})
            continue
        images = [child for child in token.children or [] if child.type == "image"]
        for image in images:
            literal = image.meta.get("source", "")
            position = image_source_position(body, offsets, token, image.meta["source_start"])
            image_end = image_source_position(body, offsets, token, image.meta["source_end"])
            if not literal or body[position:image_end] != literal:
                raise ArticleError("image_source_unmapped: image spans an unsupported multiline/container structure")
            location = local_image(image, vault, source, shortname_cache)
            event = {"start": position, "end": image_end, "kind": "image", "plain_text": image.content, **location}
            if image.meta.get("display_size"):
                event["display_size"] = image.meta["display_size"]
            events.append(event)
            if location["path"] is None:
                warnings.append({"code": "external_image_not_downloaded", "line": token.map[0] + 1, "message": f"External image requires a separately supplied local file: {location['url']}"})
            if body[start:position].strip() or body[image_end:end].strip():
                warnings.append({"code": "inline_image_split", "line": token.map[0] + 1, "message": "Inline image was split from surrounding text; review paragraph flow."})

    # Source maps delimit only the special blocks. Everything between them is
    # rendered together by markdown-it, preserving normal lists/quotes/styles.
    events.sort(key=lambda event: (event["start"], event["end"]))
    blocks = []
    pending_prefix = ""

    def render(fragment):
        return md.render(fragment, {**deepcopy(env), "suppress_issues": True})

    def add_text(fragment):
        nonlocal pending_prefix
        if not fragment:
            return
        if not fragment.strip():
            if blocks:
                blocks[-1]["markdown"] += fragment
            else:
                pending_prefix += fragment
            return
        fragment = pending_prefix + fragment
        pending_prefix = ""
        rich = render(fragment)
        blocks.append({"kind": "text", "markdown": fragment, "html": rich, "plain_text": plain_text(rich)})

    cursor = 0
    for event in events:
        start, end = event.pop("start"), event.pop("end")
        if start < cursor:
            raise ArticleError("overlapping_blocks: nested special blocks cannot be safely separated")
        add_text(body[cursor:start])
        fragment = pending_prefix + body[start:end]
        pending_prefix = ""
        if event["kind"] == "image":
            event.update({"markdown": fragment})
        else:
            rich = render(fragment)
            event.update({"markdown": fragment, "html": rich, "plain_text": plain_text(rich)})
        blocks.append(event)
        cursor = end
    add_text(body[cursor:])
    if pending_prefix:
        blocks.append({"kind": "text", "markdown": pending_prefix, "html": "", "plain_text": ""})
    for index, block in enumerate(blocks):
        block["index"] = index
    if "".join(block["markdown"] for block in blocks) != body:
        raise ArticleError("content_integrity_error: block Markdown does not reconstruct the body")
    return {
        "schema_version": 1, "vault_path": str(vault), "source_path": str(source),
        "source_sha256": hashlib.sha256(raw).hexdigest(), "title": title,
        "body_markdown": body, "blocks": blocks, "warnings": warnings,
    }


def main(argv=None):
    # Bare child Python processes do not inherit their parent's -X utf8 flag.
    # JSON summaries and diagnostics are a UTF-8 CLI contract on Windows too.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    args_parser = argparse.ArgumentParser(description=__doc__)
    args_parser.add_argument("--vault", required=True, type=Path)
    args_parser.add_argument("--source", required=True, type=Path)
    args_parser.add_argument("--output", required=True, type=Path)
    args = args_parser.parse_args(argv)
    try:
        if not args.output.is_absolute():
            raise ArticleError("absolute_paths_required: --output must be absolute")
        if args.output.resolve().is_relative_to(args.vault.resolve()):
            raise ArticleError("output_inside_vault: preparation output must be outside the read-only Vault")
        data = prepare_article(args.vault, args.source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ArticleError, OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    counts = {kind: sum(block["kind"] == kind for block in data["blocks"]) for kind in ("text", "table", "image", "divider")}
    print(json.dumps({"output": str(args.output), "blocks": counts, "warnings": len(data["warnings"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
