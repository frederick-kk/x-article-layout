"""Validate distributable paths and scan text without printing matched data.

This scans the working tree, not Git history or provider-side account settings.
All runtime records, generated images and credentials belong outside this tree.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT_FILES = {
    ".gitignore", ".gitattributes", "LICENSE", "VERSION", "README.md",
    "README.zh-CN.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
    ".github/workflows/ci.yml", ".github/pull_request_template.md",
    "tools/check_release.py", "tools/build_release.py", "tools/test_release_tools.py",
}
SKILL = "skills/x-article-layout/"
SKILL_FILES = {"SKILL.md", "SKILL.zh-CN.md", "requirements.txt",
               "agents/openai.yaml", "agents/openai.zh-CN.yaml"}
SCRIPT_FILES = {
    "cover-ui.mjs", "discover_cover.py", "ego-import.mjs", "import-runtime.mjs",
    "prepare_article.py", "verify_snapshot.py", "test_cover_ui.mjs",
    "test_discover_cover.py", "test_import_runtime.mjs", "test_prepare_article.py",
    "test_verify_snapshot.py",
}
REFERENCE_NAMES = {"onboarding.md", "editor.md", "cover.md", "privacy.md"}
REQUIRED = (ROOT_FILES - {".github/pull_request_template.md"}) | {
    SKILL + name for name in SKILL_FILES
} | {SKILL + "scripts/" + name for name in SCRIPT_FILES} | {
    SKILL + "references/" + locale + "/" + name
    for locale in ("en", "zh-CN") for name in REFERENCE_NAMES
}
PATTERNS = {
    "provider_token": re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    "bearer_value": re.compile(r"\bBearer\s+[A-Za-z0-9_.-]{24,}", re.I),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "jwt_value": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "credential_assignment": re.compile(r"\b(?:api[_-]?key|auth_token|ct0|loginToken|sessionid|password)\b[\"']?\s*[:=]\s*[\"'][A-Za-z0-9._%+/-]{16,}[\"']", re.I),
    "personal_windows_home": re.compile(r"\b[A-Za-z]:[/\\]+Users[/\\]+(?!<)[A-Za-z0-9_.-]+[/\\]", re.I),
    "personal_unix_home": re.compile(r"/(?:home|Users)/(?!<)[A-Za-z0-9_.-]+/"),
    "real_draft_url": re.compile(r"https://(?:www\.)?x\.com/compose/articles/edit/\d{12,}", re.I),
    "email_address": re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "mobile_number": re.compile(r"(?<![A-Za-z0-9])1[3-9]\d{9}(?![A-Za-z0-9])"),
}


def allowed(relative):
    value = str(relative).replace("\\", "/")
    if value in ROOT_FILES:
        return True
    if not value.startswith(SKILL):
        return False
    tail = value[len(SKILL):]
    if tail in SKILL_FILES:
        return True
    parts = PurePosixPath(tail).parts
    if len(parts) == 2 and parts[0] == "scripts":
        return parts[1] in SCRIPT_FILES
    return len(parts) == 3 and parts[0] == "references" and parts[1] in {"en", "zh-CN"} and parts[2] in REFERENCE_NAMES


def scan_text(content, relative):
    findings = []
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(content):
            findings.append({"category": category, "file": str(relative),
                             "line": content.count("\n", 0, match.start()) + 1})
    return findings


def inspect(root):
    root = Path(root).resolve()
    files, findings = [], []
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        # CI checks out Git metadata; it must never enter a release archive.
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if item.is_symlink():
            findings.append({"category": "symlink_not_distributable", "file": relative})
            continue
        if not item.is_file():
            continue
        if not allowed(relative):
            findings.append({"category": "unapproved_path", "file": relative})
            continue
        try:
            content = item.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append({"category": "unreadable_or_non_utf8", "file": relative})
            continue
        files.append(relative)
        findings.extend(scan_text(content, relative))
    for name in sorted(REQUIRED - set(files)):
        findings.append({"category": "missing_required_file", "file": name})
    return files, findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    files, findings = inspect(args.root)
    print(json.dumps({"passed": not findings, "files_checked": len(files), "findings": findings}, ensure_ascii=True))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
