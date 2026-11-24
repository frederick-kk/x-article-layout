"""Discover an article's existing local cover without changing the article.

Priority: explicit frontmatter, clearly labelled cover section, cover-named
files in an article-specific attachment directory. A first illustration/TOC
image is never a default cover. Normal result statuses (all exit 0) are found,
missing, ambiguous, invalid_reference; CLI/input errors exit 2. No downloads,
image changes, browser operations or Vault writes occur.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

from markdown_it.rules_inline import link as markdown_link
from markdown_it.token import Token
from PIL import Image, UnidentifiedImageError
import yaml

from prepare_article import ArticleError, IMAGE_EXTENSIONS, local_image, parser as article_parser, plain_text


COVER_KEYS = {"cover", "cover_image", "封面", "封面图", "封面路径"}
ATTACHMENT_NAMES = ("附件", "assets", "attachments")


def cover_parser():
    """Use the existing Markdown parser, retaining bare image wikilinks too."""
    md = article_parser()

    def wiki_link(state, silent):
        start = state.pos
        if not state.src.startswith("[[", start):
            return False
        end = state.src.find("]]", start + 2, state.posMax)
        if end < 0 or "\n" in state.src[start:end]:
            return False
        if not silent:
            token = state.push("cover_wikilink", "", 0)
            token.content = state.src[start : end + 2]
            token.attrs = {"src": state.src[start + 2 : end].partition("|")[0].strip()}
            token.meta = {"source": token.content, "obsidian": True}
        state.pos = end + 2
        return True

    def positioned_link(state, silent):
        start, count = state.pos, len(state.tokens)
        matched = markdown_link(state, silent)
        if matched and not silent:
            for token in state.tokens[count:]:
                if token.type == "link_open":
                    token.meta["source"] = state.src[start : state.pos]
        return matched

    md.inline.ruler.before("obsidian", "cover_wikilink", wiki_link)
    md.inline.ruler.at("link", positioned_link)
    md.renderer.rules["cover_wikilink"] = lambda tokens, index, options, env: html.escape(tokens[index].content)
    return md


def image_token(reference, obsidian=True, raw=None):
    token = Token("image", "img", 0)
    token.attrs = {"src": reference}
    token.meta = {"obsidian": obsidian, "source": raw or reference}
    return token


def references(inline):
    found = []
    for child in inline.children or []:
        if child.type in {"image", "cover_wikilink"}:
            found.append(child)
        elif child.type == "link_open":
            target = child.attrGet("href") or ""
            if Path(urlsplit(target).path).suffix.lower() in IMAGE_EXTENSIONS:
                found.append(image_token(target, False, child.meta.get("source", target)))
    return found


def is_cover_label(value):
    label = re.sub(r"\s+", "", value or "").strip("：:")
    label = re.sub(r"[（(]?(?:比例)?5[:：/]2[）)]?$", "", label).strip("：:")
    return label.casefold() in {"封面", "封面图", "封面图片", "文章封面", "本文封面", "本篇封面", "x封面", "x文章封面", "cover", "coverimage"}


def read_frontmatter(text):
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return [], text
    for index in range(1, len(lines)):
        if lines[index].strip() not in {"---", "..."}:
            continue
        root = yaml.compose("".join(lines[1:index]), Loader=yaml.SafeLoader)
        if not isinstance(root, yaml.MappingNode):
            return [], text
        # Compose retains repeated cover keys instead of silently taking the last.
        values = [(key.value, value) for key, value in root.value if isinstance(key, yaml.ScalarNode) and key.value.casefold() in COVER_KEYS]
        return values, "".join(lines[index + 1 :])
    if re.search(r"(?m)^[^\s:#][^\n:]*:\s", text):
        raise ArticleError("unclosed_frontmatter: YAML metadata has no closing delimiter")
    return [], text


def scalar_references(node):
    if isinstance(node, yaml.SequenceNode):
        return [value for child in node.value for value in scalar_references(child)]
    if not isinstance(node, yaml.ScalarNode):
        raise ArticleError("invalid_cover_value: cover field must contain local image references")
    if node.tag.endswith(":null") or not node.value.strip():
        return []
    return [node.value.strip()]


def field_references(value, md):
    env = {}
    inline_tokens = md.parseInline(value, env)
    found = [reference for inline in inline_tokens for reference in references(inline)]
    return found or [image_token(value)]


def labelled_body_references(body, md):
    env = {}
    tokens = md.parse(body, env)
    found = []
    all_images = []
    cover_level = None
    pending_label = False
    heading_inline_positions = set()
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            level = int(token.tag[1])
            if cover_level is not None and level <= cover_level:
                cover_level = None
            inline = tokens[index + 1]
            heading_inline_positions.add(index + 1)
            label = plain_text(md.renderer.renderInline(inline.children or [], md.options, env))
            if is_cover_label(label):
                cover_level = level
            pending_label = False
            continue
        if token.type != "inline" or index in heading_inline_positions:
            continue
        refs = references(token)
        all_images.extend(reference for reference in refs if reference.type == "image")
        remainder = token.content
        for reference in refs:
            remainder = remainder.replace(reference.meta.get("source", ""), "")
        label = plain_text(md.renderInline(remainder, {"suppress_issues": True}))
        labelled = is_cover_label(label)
        explicit_alt = any(reference.type == "image" and is_cover_label(reference.content) for reference in refs)
        if refs and (cover_level is not None or pending_label or labelled or explicit_alt):
            for reference in refs:
                found.append((reference, {"kind": "cover_section", "line": token.map[0] + 1 if token.map else None, "reference": reference.meta.get("source", reference.attrGet("src"))}))
        if labelled and not refs:
            pending_label = True
        elif not refs:
            pending_label = False
    return found, all_images


def image_metadata(reference, vault, source, cache):
    located = local_image(reference, vault, source, cache)
    if located["path"] is None:
        raise ArticleError(f"remote_image_not_local: {located.get('url', '')}")
    try:
        with Image.open(located["path"]) as image:
            width, height = image.size
            image_format = image.format
            image.verify()
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise ArticleError(f"invalid_image: {reference.attrGet('src')}") from exc
    return {**located, "width": width, "height": height, "aspect_ratio": width / height, "image_format": image_format}


def choose(stage_refs, result, vault, source, cache):
    candidates, evidence, issues = {}, [], []
    for reference, item in stage_refs:
        evidence.append(item)
        try:
            candidate = image_metadata(reference, vault, source, cache)
            candidates[candidate["path"]] = candidate
        except ArticleError as exc:
            code, _, message = str(exc).partition(":")
            issues.append({"code": code, "message": message.strip(), "reference": item.get("reference")})
    result.update({"selection_evidence": evidence, "candidates": list(candidates.values()), "issues": issues})
    if issues:
        result["status"] = "ambiguous" if all(issue["code"] == "ambiguous_image" for issue in issues) else "invalid_reference"
    elif len(candidates) > 1:
        result["status"] = "ambiguous"
    elif candidates:
        result.update({"status": "found", **next(iter(candidates.values()))})
    return result


def attachment_candidates(source, vault, all_images, cache):
    """Search only note-named dirs, or same-date article dirs referenced by it."""
    roots = {source.parent / source.stem, source.parent / (source.stem + ".assets"), source.parent / (source.stem + "_assets")}
    containers = [source.parent / name for name in ATTACHMENT_NAMES]
    roots.update(container / source.stem for container in containers)
    date = re.match(r"\d{4}-\d{2}-\d{2}", source.stem)
    for reference in all_images:
        try:
            located = local_image(reference, vault, source, cache)
            path = Path(located["path"]) if located["path"] else None
        except ArticleError:
            continue
        if path is None:
            continue
        for container in containers:
            if not path.is_relative_to(container):
                continue
            parts = path.relative_to(container).parts
            if len(parts) > 1 and (parts[0] == source.stem or date and parts[0].startswith(date.group())):
                roots.add(container / parts[0])
    existing = sorted({root.resolve() for root in roots if root.is_dir() and root.resolve().is_relative_to(vault)})
    refs = []
    seen = set()
    for root in existing:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            if "封面" not in path.stem and not re.search(r"(?:^|[-_\s])cover(?:$|[-_\s])", path.stem, re.I):
                continue
            resolved = path.resolve()
            if resolved in seen or not resolved.is_relative_to(vault):
                continue
            seen.add(resolved)
            refs.append((image_token(str(resolved)), {"kind": "named_attachment", "directory": str(root), "reference": str(path)}))
    return refs, existing


def discover_cover(vault, source):
    if not vault.is_absolute() or not source.is_absolute():
        raise ArticleError("absolute_paths_required: --vault and --source must be absolute")
    vault, source = vault.resolve(), source.resolve()
    if not source.is_relative_to(vault):
        raise ArticleError("source_outside_vault: source must be inside --vault")
    raw = source.read_bytes()
    text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    fields, body = read_frontmatter(text)
    result = {
        "schema_version": 1, "source_path": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "status": "missing", "path": None, "sha256": None, "width": None, "height": None, "aspect_ratio": None,
        "selection_evidence": [], "candidates": [], "issues": [],
    }
    md, cache, explicit = cover_parser(), {}, []
    for key, node in fields:
        try:
            values = scalar_references(node)
        except ArticleError as exc:
            result.update({"status": "invalid_reference", "issues": [{"code": "invalid_cover_value", "message": str(exc), "field": key}]})
            return result
        for value in values:
            for reference in field_references(value, md):
                explicit.append((reference, {"kind": "frontmatter", "field": key, "reference": value}))
    if explicit:
        return choose(explicit, result, vault, source, cache)
    labelled, all_images = labelled_body_references(body, md)
    if labelled:
        return choose(labelled, result, vault, source, cache)
    named, directories = attachment_candidates(source, vault, all_images, cache)
    if named:
        return choose(named, result, vault, source, cache)
    result["selection_evidence"] = [{"kind": "searched_attachment_directory", "directory": str(path)} for path in directories]
    return result


def main(argv=None):
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
            raise ArticleError("output_inside_vault: cover discovery output must be outside the read-only Vault")
        result = discover_cover(args.vault, args.source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (ArticleError, OSError, UnicodeError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "path": result["path"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
