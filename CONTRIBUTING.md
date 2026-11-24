# Contributing / 贡献说明

## English

Keep the original-note-to-draft workflow intact. Preserve source wording and order, verified draft progress, manual X edits, and the separation between cover and body media. Changes must continue to stop before publishing.

- Explain the concrete trigger, expected behavior and observed behavior in an issue or pull request. Use a minimal synthetic note instead of an unpublished article.
- Keep English and Chinese instructions equivalent when behavior or setup changes.
- Add or update tests for meaningful parser, verification or recovery behavior. Run the commands in [README.md](README.md), including the release checker and packaging tests.
- Do not commit account handles, real draft IDs/URLs, source paths, screenshots, generated covers, browser state, API keys, cookies, run records or local provider configuration. A `.gitignore` does not remove already tracked data.
- Do not request credentials or live account access from contributors. An offline test does not prove that the current X interface works; label browser verification separately.

By submitting a contribution, you agree that your contribution may be distributed under this repository's [MIT license](LICENSE). Do not submit material you are not authorized to share.

## 简体中文

修改应保留“原稿排入草稿”的流程：保持原文与顺序、已验证进度、用户在 X 的手改，以及封面和正文图片的区别。流程继续止于发布之前。

- Issue 或 PR 说明具体触发条件、预期行为和实际行为，用最小合成文章复现，不上传未发布原稿。
- 行为或配置变化时，同步维护等价的中英文说明。
- 为有实际意义的解析、验收或恢复行为增加或更新测试，运行 [README.zh-CN.md](README.zh-CN.md) 中的检查，包括发布检查和打包测试。
- 不提交真实账号、草稿 ID/地址、原稿路径、截图、生成封面、浏览器状态、密钥、Cookie、运行记录或本地服务配置。`.gitignore` 不能移除已跟踪资料。
- 不向贡献者索取凭据或真实账号权限。离线测试不代表 X 当前界面可用，网页验收需单独说明。

提交贡献即表示同意该贡献按本仓库的 [MIT 许可证](LICENSE) 分发。仅提交你有权分享的材料。
