# Runtime data and privacy

[English](privacy.md) | [简体中文](../zh-CN/privacy.md)

The public distribution contains generic instructions, scripts, and synthetic tests, not anyone's signed-in browser, account settings, articles, or drafts. This Skill does not require users to hand over X passwords, cookies, API tokens, or verification codes. Sign-in and verification happen in their own local EgoLite browser.

## Data created during a run

Plans and verification artifacts may include an entire unpublished article, absolute source paths, account handles, draft URLs/IDs, tables, image addresses, media fingerprints, and screenshots. Cover prompts can also reveal an article's subject. These are private runtime records, not public examples.

By default, keep run directories, cover assets, round scripts, browser snapshots, and logs outside the Vault, Skill installation directory, and any repository intended for publication. Record only the fields required for recovery and verification. Observe network events only to extract save status; do not persist request headers, cookies, tokens, or complete network event streams.

## Sharing and troubleshooting

- Share only source code, generic reference documentation, dependency declarations, and synthetic tests when distributing the Skill.
- Exclude run directories, `output`, article plans, snapshots, screenshots, cover originals and metadata, `.env`, local image configuration, browser data, virtual environments, `__pycache__`, and test caches.
- Reproduce issues with fictional content or a minimal synthetic sample first. When real evidence is necessary, redact accounts, draft IDs, private text, paths, and media addresses; share only the necessary portions.
- `.gitignore` helps prevent accidental additions; it does not remove tracked files or Git history. Inspect the actual files and archive before publishing. Sensitive material previously committed requires separate handling of the history and any exposed credentials.

A local privacy check establishes only that no relevant information was found within the inspected scope. It does not replace the user's decision about their article's audience or permission to use source assets. Saving a draft and publishing it are distinct actions; this Skill stops at the draft.
