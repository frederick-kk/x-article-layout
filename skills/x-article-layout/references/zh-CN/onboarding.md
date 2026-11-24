# 首次配置与登录

[English](../en/onboarding.md) | [简体中文](onboarding.md)

本引导面向第一次使用的人。环境已经可用时跳过安装。EgoLite 是浏览器，ego-browser 是它提供的本机控制命令；本包不携带浏览器安装程序、登录状态或 X API 凭据。

## 1. 安装与连接 EgoLite

从 [EgoLite 官网](https://lite.ego.app/) 下载适合 Windows 或 macOS 的安装包，用户运行安装程序并完成首次启动引导。是否导入其他浏览器数据由用户选择，不自动导入配置或读取密码。官网当前支持的平台以下载页为准；没有对应构建时说明限制。

完成引导后新开终端，检查命令。Windows PowerShell：

```powershell
Get-Command ego-browser
ego-browser nodejs -e "console.log('ego-browser ready')"
ego-browser skill
```

macOS：

```bash
command -v ego-browser
ego-browser nodejs -e "console.log('ego-browser ready')"
ego-browser skill
```

命令不可用时先确认引导已完成、终端已重新打开；不要清 Cookie 或重置浏览器。旧版提示不认识 skill 时按当前官方安装/升级指引处理；未获现有授权的软件升级先征得用户同意。ego-browser skill 必须读到 [ego-browser:skill] end of guide，截断则保存到库外文件分段读。后续 API、TaskSpace 生命周期、交接方式以该指南为准，不另装 Playwright、启动调试端口或猜测 API。

## 2. 准备 Python

使用本机 Python 3.10 或更新版本，在用户选定的虚拟环境安装本包 requirements.txt。虚拟环境放在 Vault、Skill 目录和公开仓库之外，遵循本机磁盘及缓存规则。安装依赖前先检查现有环境，避免重复安装；用该 Python 的 -m pip 安装，避免装到另一解释器。检查：

```bash
python -c "import markdown_it, bs4, yaml, PIL; print('article helpers ready')"
python -X utf8 /absolute/path/x-article-layout/scripts/prepare_article.py --help
```

示例路径需替换为真实安装路径，Windows 可用 PowerShell 的 & 调用带空格的 Python 路径。浏览器导入时将这一解释器的实际路径传给 target.pythonExecutable；EgoLite 的 Node 进程可能不继承刚在终端设置的环境变量。无第三方 Node 包依赖，浏览器轮次使用 EgoLite 自带 Node 运行时。

## 3. 用户登录自己的 X

按动态指南为本目标选择 TaskSpace，打开 https://x.com/。用户告知已有空间时先核对该空间和页面，不依据截图顺序猜 ID；不要枚举其他浏览器配置。

遇到登录或验证页面，调用 task.handOff() 并停止本轮浏览器操作。请用户在 EgoLite 内亲自登录、切换到目标账号并处理 2FA/验证码，再明确回复“已完成，继续”。不索要密码、验证码、Cookie 或登录令牌，不因为等待了一段时间就自动接管。

用户回复后接管同一空间，按指南采用/恢复标签页。核对个人资料入口显示的 @handle 与用户指定账号一致，显示昵称不足以核对身份。未指定账号而当前账号明确可见时先让用户确认目标，再首次写入；不把任何安装者的账号写成默认值。

## 4. 确认 Articles 并试跑

从侧栏 Articles 进入，必要时检查 https://x.com/compose/articles。核对是 Articles 的 Drafts，而非普通 Post 草稿。X 对 Articles 有账号资格要求，按 [X 官方说明](https://help.x.com/en/using-x/articles) 和当前网页实际权限判断，不硬编码某套餐永久可用。

入口不存在或页面拒绝时，先核对账号与登录状态，向用户说明缺少的能力；不自动订阅、付费或改成普通 Post。通过后先逐块导入本篇开头，验证富文本、保存与重开；首次遇到表格和图片时分别验收后再继续。沿用同篇草稿，无需创建公开测试内容。

## PowerShell 轮次文件

复杂浏览器代码写成 UTF-8 .mjs，放库外本次运行目录。PowerShell 使用单行入口：

```powershell
ego-browser nodejs -e "await import('file:///D:/x-article-runs/round-01.mjs')"
```

路径只是用法示例，应使用本次实际绝对路径和正斜线。中文和多行代码放文件内；不通过 Get-Content 管道传代码。每轮新建完整脚本，只运行本次对话写出的脚本，避免重放上轮写入。每轮 JavaScript 变量不保留，TaskSpace/标签页保留；按最新指南恢复它们。
