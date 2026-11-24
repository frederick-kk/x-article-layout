# Security and privacy / 安全与隐私

## English

The current `0.1.x` release line is the supported baseline for issue triage. Use the latest available patch in that line when reproducing a problem.

Do not post passwords, cookies, API keys, authentication headers, unpublished notes, unredacted screenshots or browser profiles in public issues or pull requests. Draft IDs, media addresses and local paths may also identify private work.

For a security vulnerability, use GitHub's **Report a vulnerability** option in this repository's Security tab **if the maintainer has enabled private vulnerability reporting**. If it is unavailable, do not publish exploit details or sensitive evidence; open a brief redacted issue requesting a private reporting route. Do not assume a private channel exists.

For ordinary bugs, provide a synthetic note, sanitized error, software versions and steps to reproduce. If a credential was exposed, revoke or rotate it at its issuing service; deleting a file does not revoke a credential or remove existing copies.

Only share the source release archives. Keep local run data outside the repository and recheck the actual archive contents before publishing. Automated checks detect a defined set of patterns; a passing result is not a guarantee that arbitrary text has no personal information.

## 简体中文

当前以 `0.1.x` 发布系列为问题排查的维护基线，复现问题时请使用该系列最新可用修订版。

不要在公开 Issue 或 PR 中发送密码、Cookie、API 密钥、认证请求头、未发布原稿、未脱敏截图或浏览器配置。草稿 ID、媒体地址和本机路径也可能暴露私人工作。

报告安全漏洞时，**仅在维护者已启用私密漏洞报告的情况下**，使用仓库 Security 页的 **Report a vulnerability**。入口不可用时，不公开利用细节或敏感证据；可先发一条简短且已脱敏的 Issue，请求私密报告渠道，不假定该渠道已存在。

普通问题请提供合成文章、脱敏错误、软件版本和复现步骤。凭据一旦暴露，应到签发服务撤销或轮换；删除文件不会撤销凭据，也无法清除已有副本。

分享时仅使用源码发布包。运行资料保存在仓库外，发布前核对实际压缩包内容。自动检查覆盖的是既定模式，通过不代表任意文字都没有个人信息。
