# Cover discovery, generation, and upload

[English](cover.md) | [简体中文](../zh-CN/cover.md)

A cover is an article-level image, handled separately from body images. Preserve an existing draft cover by default, including one the user added manually in X.

## Choose an image for this article

Read the current draft using `readCover(page)` from `cover-ui.mjs`. `present` only means an image is currently displayed. When `crop_dialog_open` is true, it may still be an unsaved preview. Use the run record to inspect any unfinished upload rather than overwriting it again.

When the draft has no cover, check `discover_cover.py --help`, then run:

```bash
python -X utf8 /absolute/path/x-article-layout/scripts/discover_cover.py --vault /absolute/path/vault --source /absolute/path/vault/article.md --output /absolute/path/private-runs/cover-discovery.json
```

The finder prioritizes explicit frontmatter (`cover`, `cover_image`, `封面`, `封面图`, `封面路径`), explicitly labeled cover sections, and images clearly named `cover`/`封面` in article-specific attachment directories. Being the first image, a table-of-contents graphic, or a landscape image is insufficient evidence that it is the cover. Handle statuses as follows:

- `found`: inspect the selection evidence, file SHA, and actual image, then reuse it.
- `missing`: generate from the source. If this run already has a generated image matching the source/style, verify its SHA and reuse it.
- `ambiguous`: resolve the specific candidate ambiguity rather than choosing arbitrarily.
- `invalid_reference`: preserve the original reference and explain the failed item; do not silently ignore an explicit cover setting.

Do not edit the source merely to make cover discovery succeed. If the user explicitly supplies a separate cover file, follow that instruction and retain its provenance.

## Generate a missing cover

Read the user's current style request or explicitly selected style file. Otherwise use a simple editorial cover: a clear subject, a short title, whitespace, and sufficient contrast. Derive its title, topic, and benefit from the article. Do not invent claims such as "guaranteed success" or "free forever." Changing the title on a table-of-contents graphic does not turn it into a suitable cover.

Default to a 5:2 request for X. Choose an available, authorized image tool in the current host and follow applicable image rules and local-configuration priorities. Do not assume every installer has access to a particular paid service. Read API keys only from user-local configuration or a secure environment; never display them, log them, or package them with the Skill. An external generation service receives prompts/reference materials, so send only the necessary topic, summary, and cover text where possible. Do not include unrelated private drafts or credentials in prompts.

If no generation tool is available, report "body saved; cover pending" and continue when the user supplies an image or configures a tool. Do not pass a placeholder off as a completed cover, silently buy credits, or switch to a paid service. Report sanitized errors on generation failure. Use an alternative tool only when existing authorization covers it, and accurately record the tool actually used.

Inspect pixel dimensions, aspect ratio, Chinese text when present, factual accuracy, and thumbnail readability. Small pixel-rounding errors can be handled in X's native 5:2 crop; leave safe margins around text and the subject. Save the image in the user's private run-asset directory, without writing it back to the Vault by default.

After successful generation, record `generated` with source/style fingerprints, absolute file path, SHA, dimensions, and generation method. Then record `uploading` and `saved_verified` as those stages are reached. Reuse the same file after upload failures to avoid repeated charges. Reassess an older cover when the source or style changes.

## Upload into the same draft

1. Verify the account and actual draft URL. Save the current body baseline with `readEditorWithMediaFingerprints`; do not replace manual X edits with an older source version.
2. Check `readCover` again to ensure no saved cover is present. A candidate control is `input[type="file"][accept="image/jpeg,image/png,image/webp"]` before the title, outside the composer and any dialog. If the match is not unique, inspect the page rather than choosing the first input on it.
3. `page.setInputFiles` normally opens an Edit media crop dialog. The background preview is not proof of saving. Inspect a real screenshot to ensure the title and subject fit completely within the fixed 5:2 frame, then choose Apply.
4. Wait for the website's own media upload and article save to complete. Reopen the same draft and confirm the cover persists; inspect its actual crop and sharpness. X may re-encode images, so do not require the local original's byte SHA to equal the compressed image's SHA.
5. Read the body again and call `assertBodyUnchanged(before,after)`, checking text, tables, links, and body-image identities and order. Preserve and inspect any differences; do not rewrite the body merely to make verification pass.

Helpers in `scripts/cover-ui.mjs` are `readCover(page)`, `bodyCanonical(state)`, and `assertBodyUnchanged(before,after)`. Body snapshots come from `scripts/ego-import.mjs`. Count cover and body images separately. Insert → Media or `appendBlock(image)` cannot substitute for a cover upload. Never click Publish.
