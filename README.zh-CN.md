# X文章排版助手

简体中文 · [English](README.md)

将 Obsidian 里已有的 Markdown 文章排进 **X Articles 草稿箱**。保留原文措辞、链接和图片顺序，单独插入原生表格，缺少封面时准备配套图片。流程止于草稿。

## 能做什么

- 引导新用户安装、连接 EgoLite，由本人登录，并核对目标账号和 Articles 权限。
- 只读指定原稿，从所选 Vault 内解析本地图片。
- 用编辑器原生控件粘贴富文本，分别插入表格、正文图片和分隔线。
- 保留 X 已有封面；否则复用明确标注的本地封面，或用可用的生图工具制作与原文相符的 5:2 封面。
- 重新打开同一草稿核对保存结果，从已验证进度续传，保留用户手改。

这是独立项目。分发包不包含 EgoLite、Obsidian、X 或 Python 依赖本身。

## 使用条件

| 组件 | 用途 |
| --- | --- |
| 支持本地 Skills 的 Codex | 执行 Skill 指令和本地辅助脚本 |
| [EgoLite](https://lite.ego.app/)，且 `ego-browser` 命令可用 | 在 TaskSpace 内操作已登录网页 |
| Python 3.10+ 及附带的依赖声明 | 解析 Markdown、发现封面、核对快照 |
| 当前具备 Articles 权限的 X 账号 | 保存文章草稿；以实际页面及 [X 官方说明](https://help.x.com/en/using-x/articles) 核对资格 |
| 已获授权的生图工具（需要补封面时） | 本包不提供服务密钥或额度 |

浏览器轮次运行于 `ego-browser nodejs`。仅执行离线 Node 测试时，才需要另装 Node.js 22；无需第三方 npm 包。

## 安装

1. 下载或复制本仓库。可安装的 Skill 是整个 [`skills/x-article-layout`](skills/x-article-layout/SKILL.zh-CN.md) 文件夹；中文或英文独立安装包中，则是顶层的 `x-article-layout` 文件夹。
2. 将该文件夹复制到 `$CODEX_HOME/skills/`；没有设置 `CODEX_HOME` 时，默认放进 `~/.codex/skills/`。保留 `x-article-layout` 文件夹名，先检查已有安装，不直接覆盖。
3. 在下一轮 Codex 对话中使用。中文、英文独立包的内部 Skill 名称和脚本相同，**选择其中一个安装即可**。仓库版本同时包含中英文指令。

第一次可以这样说：

> 使用 $x-article-layout，先带我配置 EgoLite、登录我的 X 账号并确认 Articles 权限，再把我指定的 Obsidian 文章排进草稿箱。保留原文，不要发布。

具体安装、登录步骤见 [首次使用引导](skills/x-article-layout/references/zh-CN/onboarding.md)。密码、验证码和双重验证由你亲自在浏览器输入，不发送给助手。

安装 Python 依赖前，先让助手检查已有环境。确实缺少时，在 Vault 和本仓库之外的合适环境中，使用该环境的 Python 安装：

```sh
python -m pip install -r skills/x-article-layout/requirements.txt
```

命令从仓库根目录运行。浏览器导入时可通过 `target.pythonExecutable` 传入所选 Python 的绝对路径；若 EgoLite 进程继承了环境变量，也可用 `X_ARTICLE_PYTHON`。

提供文章路径、Vault 根路径和目标 `@账号`。在同篇草稿先导入少量开头，核对保存与重开；首次遇到表格和图片时分别验收后，再继续导入。

## 工作流与限制

[中文 Skill](skills/x-article-layout/SKILL.zh-CN.md) 按需引导至 [编辑器操作](skills/x-article-layout/references/zh-CN/editor.md)、[封面处理](skills/x-article-layout/references/zh-CN/cover.md) 和 [隐私说明](skills/x-article-layout/references/zh-CN/privacy.md)。[English Skill](skills/x-article-layout/SKILL.md) 提供等价英文流程。

标题和富文本按 X 当前编辑器适配；表格使用原生 Table 块单独插入，不把 Markdown 管道文字当成表格。部分样式、代码字体或长图缩略图可能存在差异，助手须检查实际显示并说明适配。外部图片不自动下载。

没有可用生图工具时，明确封面待补，保留已保存草稿，不购买订阅或额度。X 控件或保存行为变化时，先检查再继续写入。始终不点击 **Publish**。

离线脚本已在 Windows、Python 3.10.9 / 3.13.5、Node.js 22.21 下通过 45 项 Python 测试和 17 项 Node 测试。附带的 CI 面向 Windows 与 Ubuntu，托管运行结果见仓库 Actions 页面；真实网页兼容性及新用户账号权限仍需首次试跑。macOS 提供配置引导，本次尚未进行运行验收。

## 隐私与分享

原稿、账号配置、草稿链接、生成封面、截图、浏览器数据、运行记录和本地服务配置均应保存在 **Skill 与仓库之外**。运行记录可能包含完整未发布文章。生成封面时，必要的提示词或参考材料会发送给使用者选择的图像服务。

发布检查和打包白名单可以降低误带资料的风险，不能保证未来任意新增文件都已匿名。排错或提 Issue 时，优先使用合成样本，并移除私人正文、账号、ID、路径、媒体地址和凭据。见 [SECURITY.md](SECURITY.md) 与 [隐私说明](skills/x-article-layout/references/zh-CN/privacy.md)。

## 开发检查

安装 Skill 依赖后，在仓库根目录执行：

```sh
python tools/check_release.py
python -B -m unittest discover -s tools -p "test_*.py"
```

随后进入 `skills/x-article-layout` 执行：

```sh
python -B -X utf8 -m unittest discover -s scripts -p "test_*.py"
node --test scripts/test_cover_ui.mjs scripts/test_import_runtime.mjs
```

如默认的 Windows `python` 或其他系统的 `python3` 指向不同环境，将 `X_ARTICLE_TEST_PYTHON` 设为已安装依赖的同一 Python 可执行文件。测试只用合成输入，不连接 X 或图像服务。

发布包输出到仓库之外的绝对路径：

```sh
python tools/build_release.py --output /absolute/path/to/release-output
```

提交修改前请阅读 [贡献说明](CONTRIBUTING.md)；版本变化见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

采用 [MIT](LICENSE)。第三方浏览器、平台及运行依赖仍适用各自的许可与条款。
