"""Build reproducible source and language-specific Skill ZIPs outside the repo."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import zipfile
import sys

sys.dont_write_bytecode = True
from check_release import inspect, SKILL


def make_archive(entries):
    # Validate before ZipInfo can normalize separators on Windows.
    for name in entries:
        if name.startswith("/") or ".." in name.split("/") or "\\" in name or ":" in name.split("/")[0]:
            raise ValueError("Unsafe archive path")
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    value = result.getvalue()
    with zipfile.ZipFile(io.BytesIO(value)) as archive:
        if archive.testzip() is not None:
            raise ValueError("Archive integrity check failed")
        if any(name.startswith("/") or ".." in Path(name).parts or "\\" in name or ":" in name.split("/")[0] for name in archive.namelist()):
            raise ValueError("Unsafe archive path")
        for name, data in entries.items():
            if archive.read(name) != data:
                raise ValueError("Archive content changed")
    return value


def skill_entries(source, locale):
    entries = {"x-article-layout/" + name[len(SKILL):]: data
               for name, data in source.items() if name.startswith(SKILL)}
    entries["x-article-layout/LICENSE"] = source["LICENSE"]
    for name in ("SECURITY.md", "CHANGELOG.md", "VERSION"):
        entries["x-article-layout/" + name] = source[name]
    for name in ("README.md", "README.zh-CN.md"):
        content = source[name].decode("utf-8").replace("skills/x-article-layout/", "./")
        # Source-repository tools/CI are intentionally absent from install ZIPs.
        if name == "README.md":
            start, end = "## Development checks", "## License"
            note = "For development tools and CI, use the source archive.\n\n"
        else:
            start, end = "## 开发检查", "## 许可证"
            note = "开发工具与 CI 配置请使用源码包。\n\n"
        if start in content and end in content:
            content = content[:content.index(start)] + note + content[content.index(end):]
        entries["x-article-layout/" + name] = content.encode("utf-8")
    if locale == "zh-CN":
        entries["x-article-layout/SKILL.en.md"] = entries["x-article-layout/SKILL.md"].decode("utf-8").replace("](SKILL.md)", "](SKILL.en.md)").encode("utf-8")
        chinese = entries["x-article-layout/SKILL.zh-CN.md"].decode("utf-8")
        entries["x-article-layout/SKILL.md"] = chinese.replace("](SKILL.md)", "](SKILL.en.md)").encode("utf-8")
        entries["x-article-layout/SKILL.zh-CN.md"] = entries["x-article-layout/SKILL.md"]
        entries["x-article-layout/agents/openai.en.yaml"] = entries["x-article-layout/agents/openai.yaml"]
        entries["x-article-layout/agents/openai.yaml"] = entries["x-article-layout/agents/openai.zh-CN.yaml"]
        english_readme = entries["x-article-layout/README.md"].decode("utf-8").replace("](./SKILL.md)", "](./SKILL.en.md)")
        chinese_readme = entries["x-article-layout/README.zh-CN.md"].decode("utf-8").replace("](README.md)", "](README.en.md)").replace("](./SKILL.md)", "](./SKILL.en.md)")
        entries["x-article-layout/README.en.md"] = english_readme.encode("utf-8")
        entries["x-article-layout/README.md"] = chinese_readme.encode("utf-8")
        entries["x-article-layout/README.zh-CN.md"] = chinese_readme.encode("utf-8")
    return entries


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError("Release output must be outside the repository")
    files, findings = inspect(root)
    if findings:
        raise ValueError("Release check failed; run check_release.py for redacted findings")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("VERSION must be major.minor.patch")
    # All approved inputs are UTF-8 text; canonical LF also stabilizes archives
    # built from Windows checkouts and avoids embedding local filesystem data.
    source = {name: (root / name).read_text(encoding="utf-8").encode("utf-8") for name in files}
    prefix = "x-article-layout-v" + version
    payloads = {
        prefix + "-source.zip": make_archive({prefix + "/" + name: data for name, data in source.items()}),
        prefix + "-en.zip": make_archive(skill_entries(source, "en")),
        prefix + "-zh-CN.zip": make_archive(skill_entries(source, "zh-CN")),
    }
    output.mkdir(parents=True, exist_ok=True)
    sums = []
    for name, data in payloads.items():
        (output / name).write_bytes(data)
        sums.append(hashlib.sha256(data).hexdigest() + "  " + name)
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return list(payloads)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        names = build(args.root, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + "\n")
    print("Built: " + ", ".join(names) + "; SHA256SUMS.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
