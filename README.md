# X Article Layout Assistant

[简体中文](README.zh-CN.md) · English

A Codex Skill that lays out an existing Obsidian Markdown article in **X Articles drafts**. It preserves the source wording, links and image order, inserts native tables, and prepares a matching cover when one is missing. It stops at the draft stage.

## What it does

- Guides first-time users through EgoLite installation, personal login, account verification and checking access to Articles.
- Reads the specified note without changing it; resolves local images within the selected Vault.
- Pastes rich text and inserts tables, body images and dividers through the editor's own controls.
- Keeps an existing X cover, reuses an explicitly marked local cover, or generates a relevant 5:2 cover using an available image tool.
- Reopens the same draft to check saved content and resumes from verified progress while preserving manual edits.

This is an independent project. EgoLite, Obsidian, X and Python dependencies are not included in the distribution.

## Requirements

| Component | Purpose |
| --- | --- |
| Codex with local Skills support | Runs the agent instructions and local helpers |
| [EgoLite](https://lite.ego.app/) with `ego-browser` available | Operates the signed-in browser through a TaskSpace |
| Python 3.10+ and the supplied requirements | Parses Markdown, discovers covers and checks snapshots |
| An X account with current Articles access | Stores the article draft; verify eligibility in the actual UI and [X documentation](https://help.x.com/en/using-x/articles) |
| An authorized image-generation tool, if needed | Generates a missing cover; no service key or credit is supplied |

Browser scripts run in `ego-browser nodejs`. A separate Node.js 22 runtime is needed only to run the offline Node tests. No third-party npm packages are required.

## Install

1. Download or copy this repository. The installable Skill is the entire [`skills/x-article-layout`](skills/x-article-layout/SKILL.md) folder. In a standalone language package, it is the top-level `x-article-layout` folder instead.
2. Copy that folder into `$CODEX_HOME/skills/`, or `~/.codex/skills/` when `CODEX_HOME` is unset. Keep the folder name `x-article-layout`. Do not overwrite an existing installation without checking it.
3. Use the Skill in your next Codex turn. Choose **one** standalone language package; both use the same internal Skill name and scripts. The repository version includes both English and Chinese instructions.

Start with:

> Use $x-article-layout. Help me set up EgoLite, sign into my X account and verify Articles access, then lay out my specified Obsidian note in a draft. Preserve the original text and do not publish.

The [onboarding guide](skills/x-article-layout/references/en/onboarding.md) covers installation and login. Enter your password, verification code and 2FA in the browser yourself; never send them to the assistant.

Before installing Python dependencies, let the assistant check your existing environment. Install missing dependencies into a suitable environment outside your Vault and this repository, using that environment's Python:

```sh
python -m pip install -r skills/x-article-layout/requirements.txt
```

Run this from the repository root. If needed, pass the chosen interpreter's absolute path through `target.pythonExecutable`; `X_ARTICLE_PYTHON` is an alternative when the EgoLite process inherits it.

Provide the note path, Vault root and target `@handle`. Start with a few opening blocks in the same draft, verify save and reopen, and check the first table and image as they are encountered before continuing.

## Workflow and limits

The main [Skill](skills/x-article-layout/SKILL.md) routes to [editor operations](skills/x-article-layout/references/en/editor.md), [covers](skills/x-article-layout/references/en/cover.md), and [privacy](skills/x-article-layout/references/en/privacy.md). [中文 Skill](skills/x-article-layout/SKILL.zh-CN.md) contains the equivalent Chinese workflow.

Source headings and rich formatting are adapted to X's current editor. Native tables are inserted separately rather than left as Markdown pipes. Some styles, code fonts and long-image thumbnails may differ; the assistant must check the rendered result and explain any adaptation. Remote images are not downloaded automatically.

When no image-generation tool is available, the assistant reports the cover as pending and keeps the saved draft. It does not buy subscriptions or credits. Changes to X's controls or save behavior require inspection before further writes. It never clicks **Publish**.

Offline helpers have been tested on Windows with Python 3.10.9 and 3.13.5, and Node.js 22.21: 45 Python tests and 17 Node tests. The supplied CI targets Windows and Ubuntu; it has not yet run in a published GitHub repository. Browser compatibility and each new user's account permissions still require a first live trial. macOS has onboarding instructions but has not been runtime-tested here.

## Privacy and sharing

Keep source notes, account configuration, draft links, generated covers, screenshots, browser data, run records and local provider configuration **outside the Skill and repository**. Run records can contain the complete unpublished article. Cover generation sends the necessary prompt or reference material to the image provider selected by the user.

The release checker and packaging allowlist help prevent accidental inclusion; they cannot prove that arbitrary future files are anonymous. Before sharing logs or filing an issue, use a synthetic reproduction and remove personal content, handles, IDs, paths, media URLs and credentials. See [SECURITY.md](SECURITY.md) and the [privacy guide](skills/x-article-layout/references/en/privacy.md).

## Development checks

From the repository root, after installing the Skill requirements:

```sh
python tools/check_release.py
python -B -m unittest discover -s tools -p "test_*.py"
```

Then, from `skills/x-article-layout`:

```sh
python -B -X utf8 -m unittest discover -s scripts -p "test_*.py"
node --test scripts/test_cover_ui.mjs scripts/test_import_runtime.mjs
```

Set `X_ARTICLE_TEST_PYTHON` to the same environment's Python executable if the default `python` on Windows or `python3` elsewhere points to another environment. Tests use synthetic inputs and do not connect to X or an image service.

Build release archives into an absolute directory outside the repository:

```sh
python tools/build_release.py --output /absolute/path/to/release-output
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a change and [CHANGELOG.md](CHANGELOG.md) for version notes.

## License

[MIT](LICENSE). Third-party browsers, platforms and runtime dependencies retain their own licenses and terms.
