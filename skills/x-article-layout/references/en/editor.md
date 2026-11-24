# X Articles editor operations and recovery

[English](editor.md) | [简体中文](../zh-CN/editor.md)

This describes the interface structure supported by the helpers, not a guarantee that the website will never change. Check controls against a current snapshot before acting. When they differ, inspect and adapt rather than continuing to paste at an uncertain location.

## Prepare a plan

Check `prepare_article.py --help`, then create a plan outside the Vault:

```bash
python -X utf8 /absolute/path/x-article-layout/scripts/prepare_article.py --vault /absolute/path/vault --source /absolute/path/vault/article.md --output /absolute/path/private-runs/article-plan.json
```

The plan contains the Vault path, source path and SHA, title, warnings, and ordered `text`/`table`/`image`/`divider` blocks. Local image resolution stays within the Vault. Resolve ambiguous filenames, invalid references, and external images before importing. The script reads the source without changing it; its output cannot be written into the Vault. A plan contains unpublished content and must not be uploaded as a public example.

## Title and body

- The entry is normally sidebar Articles → Drafts. A newly created draft has an actual address of `/compose/articles/edit/<article-id>`. Record the real URL rather than constructing one from an example.
- Candidate controls are `textarea[name="Article Title"]` for the title and `[contenteditable="true"][data-testid="composer"]` for the body. Check the live title limit; do not truncate the original title.
- Paste with `page.keyboard.paste({text,html})` through the native rich-text clipboard. `plain_text` includes link destinations and list markers for fallback, so it must not be compared directly with visible DOM text. The helper checks added text using HTML text; the verifier checks links and structure separately.
- Map source H2 to body `h1`, H3 to `h2`, and deeper headings to separate bold paragraphs. X may render inline code in an ordinary font. Preserve its text, spaces, and commands and inspect the actual result instead of assuming identical styling.
- Before appending, physically click the last `data-block` and press `ControlOrMeta+End`. Special blocks require an empty Body paragraph. An empty list item, quotation, or heading still has its formatting context; use keyboard or toolbar controls to return to Body. The helper checks this precondition.
- Pasting an isolated `h1`/`h2` may inherit the current paragraph type; the helper corrects it through the Heading/Subheading toolbar. When adjusting an existing block, confirm the caret actually moved there rather than assuming a text click established the correct selection.

Do not use `innerHTML`, React internal state, or fabricated save responses as substitutes for website editing. Here, `page.evaluate` reads rendered state.

## Native tables

1. In an empty body paragraph at the intended position, choose Insert (candidate `button[aria-label="Add Media"]`) → Table.
2. Insert a 1×1 placeholder (candidate `button[aria-label="Insert a 1 by 1 table"]`).
3. Open Edit block for the newly inserted table, scoped to the composer and newest block; do not edit an earlier table.
4. Fill `textarea[name="markdown-input"]` in the dialog with the plan's full `markdown`, then choose Update.
5. Wait for the final rows, columns, and cells to render. Verify text, bold styling, and links. The placeholder dimensions do not define the final size; inspect large tables for actual readability.

Pasting Markdown pipe-table syntax into ordinary body text is not a completed table import. Do not convert tables to images by default.

## Images and dividers

- Insert body images through Insert → Media. The current helper scopes uploads to the website's `[role="dialog"] input[type="file"]` and calls `setInputFiles` with the actual absolute path. Do not target the article-cover control.
- Check the file SHA against the prepared value. Wait for Uploading media to end and images to load. A blob preview alone does not prove upload or draft saving has finished.
- Use the current dialog's per-media-block limits; do not mistake a per-block limit for the article-wide limit. Keep each image in its source position and do not add captions by default.
- Tall images may appear as cropped thumbnails in the editor or Preview. Inspect top and bottom edges and the full image opened by clicking; disclose the actual display behavior on delivery. If splitting is needed, follow the user's request to agree on an approach rather than redrawing or cropping screenshots unprompted.
- Use Insert → Divider for separators; do not paste Markdown `---` as ordinary text.

## Helper interface

Import the module from an EgoLite `.mjs` round. This illustrates the interface: `page` comes from the current TaskSpace, and paths and account values come from this run's actual record.

```javascript
import {pathToFileURL} from 'node:url';
import path from 'node:path';
const {appendAndVerifySaved, readEditor} = await import(
  pathToFileURL(path.join(skillDirectory, 'scripts', 'ego-import.mjs')).href
);
const target = {
  draftUrl: run.draftUrl,
  account: run.accountWithoutAt,
  planPath: run.planPath,
  runDir: run.runDirectory,
  pythonExecutable: run.pythonExecutable,
  tempDir: run.tempDirectory
};
const receipt = await appendAndVerifySaved(page, plan.blocks[nextIndex], target);
const snapshot = await readEditor(page);
```

Explicitly assign these local variables in the current round script. This is not a complete script to replay directly. `skillDirectory` is the actual installed Skill directory and does not depend on the developer's filesystem. Use the current complete plan; do not force-replay its full prefix over manual draft edits.

`planPath` and `runDir` must be absolute. New plans include `vault_path`; legacy plans lacking it require an explicit `target.vaultPath`. `tempDir` is optional and, when provided, must be absolute and outside the Vault. Outputs, run directories, and temporary directories must not overwrite the source or plan. The helper checks these boundaries and dependencies before changing the page.

Interpreter precedence is `target.pythonExecutable` → `X_ARTICLE_PYTHON` in the EgoLite process → platform default (`python` on Windows, `python3` elsewhere). Prefer an absolute executable path: terminal environment changes may not reach the EgoLite process. Repair missing interpreters or dependencies before importing; do not bypass verification.

`appendAndVerifySaved` checks account, draft, and source fingerprints, observes save/upload requests triggered by website actions, waits for a draft save after the upload finishes, then reopens and compares the saved article with the source-plan prefix. It does not directly invoke X private endpoints. Save observation currently depends on page request signatures; if an X change prevents observation, the helper stops rather than claiming success. Do not dump full network events, headers, or response bodies into logs.

The lower-level `appendBlock` returns a page-application receipt with `saved:false`. Only the upper-level helper returns `saved:true` and `source_verified:true` after verification; items in `ui_checks` still require UI inspection. Persist every successful receipt rather than keeping it only in a process variable.

## Save verification and recovery

After saving, reopen the same URL. The composer may initially be an empty placeholder, so wait for the title, text, tables, and every image to be complete with `naturalWidth>0`. Compare each block against the plan. Use `verify_snapshot.py --help` for the final verification arguments: exit code 0 means passed, 1 differences, 2 invalid input, and 3 actual UI checks remain.

Read body-media identities using `readEditorWithMediaFingerprints`. Blob URLs change across reopening; compare content fingerprints when available rather than treating URL changes as changed images. Also inspect position and rendering for ordinary HTTPS images.

Before each recovery, read the run record and the same draft. Compare the source version, last verified snapshot, and current page. A changed source, different account, or manual edits requires reassessment. Preserve user text instead of overwriting with an older plan. After a timeout, inspect what was actually inserted; make only bounded retries supported by evidence. If uncertain, stop at the same draft and explain rather than duplicating drafts or retrying indefinitely.
