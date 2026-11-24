# Setup and sign-in

[English](onboarding.md) | [简体中文](../zh-CN/onboarding.md)

Use this guide for a first-time user; skip installation when the environment already works. EgoLite is the browser, and `ego-browser` is its local control command. This package includes no browser installer, signed-in session, or X API credentials.

## 1. Install and connect EgoLite

Download the appropriate Windows or macOS installer from the [EgoLite website](https://lite.ego.app/). The user runs it and completes first-run onboarding. Importing data from another browser is the user's choice; do not import profiles or read passwords automatically. Check the download page for currently supported platforms and explain when no suitable build exists.

After onboarding, open a new terminal and check the command. In Windows PowerShell:

```powershell
Get-Command ego-browser
ego-browser nodejs -e "console.log('ego-browser ready')"
ego-browser skill
```

On macOS:

```bash
command -v ego-browser
ego-browser nodejs -e "console.log('ego-browser ready')"
ego-browser skill
```

If the command is unavailable, first confirm onboarding is complete and a new terminal has been opened. Do not clear cookies or reset the browser. If an older version does not recognize `skill`, follow the current official install/upgrade guidance and obtain authorization for any upgrade that is not already authorized. Read `ego-browser skill` through `[ego-browser:skill] end of guide`. If truncated, save it outside the Vault and read it in parts. Use that guide for APIs, TaskSpace lifecycle, and handoffs; do not separately install Playwright, open debugging ports, or guess APIs.

## 2. Prepare Python

Use Python 3.10 or newer, with this package's `requirements.txt` installed in a virtual environment selected by the user. Keep the environment outside the Vault, Skill directory, and public repository; follow local disk and cache rules. Check existing environments before installing anything. Use the selected interpreter's `-m pip` so dependencies do not end up in a different Python environment. Check:

```bash
python -c "import markdown_it, bs4, yaml, PIL; print('article helpers ready')"
python -X utf8 /absolute/path/x-article-layout/scripts/prepare_article.py --help
```

Replace example paths with the actual installation paths. In PowerShell, use `&` to call a quoted Python path containing spaces. Pass that interpreter's actual path as `target.pythonExecutable` for browser imports: EgoLite's Node process may not inherit environment variables just set in a terminal. No third-party Node packages are required. Browser rounds run in EgoLite's bundled Node runtime.

## 3. Let the user sign into X

Choose a TaskSpace for this goal according to the dynamic guide and open `https://x.com/`. If the user identifies an existing space, inspect that space and page rather than guessing an ID from screenshot order. Do not enumerate other browser profiles.

At a sign-in or verification page, call `task.handOff()` and stop browser actions for that round. Ask the user to sign in personally in EgoLite, switch to the intended account, handle 2FA or verification codes, and explicitly reply that they are done and you may continue. Do not request passwords, codes, cookies, or login tokens; elapsed time is not permission to resume.

After the reply, reclaim the same space and adopt or restore its tabs following the guide. Verify that the profile entry's @handle matches the user-selected account; a display name is insufficient. If no account was specified but one is clearly signed in, have the user confirm it before the first write. Never store an installer's own account as a default.

## 4. Confirm Articles access and try a small import

Open Articles from the sidebar; if needed, inspect `https://x.com/compose/articles`. Confirm you are in Articles Drafts, not ordinary Post drafts. Articles has account eligibility requirements: consult the [official X guidance](https://help.x.com/en/using-x/articles) and actual current access rather than assuming a particular plan is permanently eligible.

If the entry is absent or access is refused, first check the account and sign-in state, then explain the missing capability. Do not automatically subscribe, pay, or switch the task to an ordinary Post. Once access works, import a few opening blocks from the authorized article and verify rich text, saving, and reopening. Inspect the first table and image individually when encountered before continuing. Keep the same draft; no public test content is needed.

## PowerShell round files

Write complex browser code into a UTF-8 `.mjs` file in the private run directory outside the Vault. Use a single-line PowerShell entry:

```powershell
ego-browser nodejs -e "await import('file:///D:/x-article-runs/round-01.mjs')"
```

The path is illustrative: use the actual absolute path with forward slashes for this run. Put Chinese text and multiline code in the file, and do not pipe code through `Get-Content`. Write a complete new script for each round; run only the script written for the current turn, to avoid repeating an earlier write. JavaScript variables do not survive between rounds, while TaskSpaces and tabs do; restore them as directed by the latest guide.
