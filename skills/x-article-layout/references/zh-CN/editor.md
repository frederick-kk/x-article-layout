# X Articles 编辑器操作与恢复

[English](../en/editor.md) | [简体中文](editor.md)

以下是 helper 所支持的界面结构，属于操作依据，不保证网页永久不变。每次用当前 snapshot 核对控件；不匹配则观察适配，不能在未知位置继续粘贴。

## 准备计划

用 prepare_article.py --help 确认参数，然后生成库外计划：

```bash
python -X utf8 /absolute/path/x-article-layout/scripts/prepare_article.py --vault /absolute/path/vault --source /absolute/path/vault/article.md --output /absolute/path/private-runs/article-plan.json
```

计划包括 Vault 路径、源路径和 SHA、标题、warnings、按原顺序排列的 text/table/image/divider。图片路径只解析 Vault 内文件；同名歧义、无效引用及外部图片应先处理。脚本只读原稿，输出不能放回 Vault。计划含完整未发布内容，不作为公开示例上传。

## 标题与正文

- 入口通常为侧栏 Articles → Drafts；新建后的真实地址为 /compose/articles/edit/文章ID。记录实际 URL，不能从样例构造。
- 标题控件候选为 textarea[name="Article Title"]，正文候选为 [contenteditable="true"][data-testid="composer"]。读取网页实际标题长度限制；不截断原题。
- 正文用 page.keyboard.paste({text,html}) 原生富文本剪贴板。plain_text 包含 URL 和列表标记用于回退，不能直接拿它与 DOM 可见文字比对。helper 使用 HTML 文本检查新增文字，验收器另查链接与结构。
- H2 源标题适配为正文 h1，H3 为 h2，更深标题用独立加粗段落。行内代码等字形可能被 X 改成普通字体，文字、空格、命令必须保留并实际验收，不能把格式相同作为默认结果。
- 操作尾部先真实点击最后一个 data-block，再 ControlOrMeta+End。特殊块必须插在空的 Body 段落；空 LI/引用/标题仍有样式上下文，需用网页键盘/工具栏退回 Body。helper 会检查这一条件。
- 独立 h1/h2 的粘贴可能继承当前段落类型，helper 会通过 Heading/Subheading 工具栏修正。处理已有块时应确认光标实际在目标块，不能只因点过文字就假设选区正确。

不要用 innerHTML、React 内部状态或伪造保存响应代替网页编辑。page.evaluate 在这里用于读取展示状态。

## 原生表格

1. 在正确位置的空正文段落，点 Insert（候选 button[aria-label="Add Media"]）→ Table。
2. 先插入 1×1 占位（候选 button[aria-label="Insert a 1 by 1 table"]）。
3. 点本次新增块的 Edit block，限定 composer 与最新块，不能误改前面的表格。
4. 在弹窗 textarea[name="markdown-input"] 填 plan 中完整 markdown，点 Update。
5. 等待最终行列与所有单元格渲染，核对文字、粗体与链接。占位尺寸不代表最终尺寸；大型表格须检查实际可读性。

不能把 Markdown 管道表直接粘在正文后称表格已导入，也不默认把表格转图片。

## 图片与分隔线

- 正文图片用 Insert → Media，当前 helper 限定网页上传弹窗 [role="dialog"] input[type="file"]，通过 setInputFiles 传实际绝对路径。不要选到文章级封面控件。
- 验证文件 SHA 与准备时一致，等待 Uploading media 状态结束及图片加载。blob 预览先出现不代表上传或草稿保存完成。
- 媒体块张数限制以当次弹窗为准，不把每块限制误认为整篇限制。单图保持原文位置，caption 默认不新增内容。
- 纵向长图可能在编辑器或 Preview 中显示裁切缩略图。检查上、下边缘与点击后的完整图；交付时说明实际显示方式。需要拆图时先按用户要求确定方案，不自行重绘或裁掉截图。
- 分隔线用 Insert → Divider，不能把 Markdown --- 当普通文字贴入。

## Helper 接口

模块在 EgoLite 的 .mjs 轮次中导入。以下代码展示接口，page 来自当前 TaskSpace，所有路径和账号来自本次真实运行记录：

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

这些局部变量由本次轮次脚本明确赋值；不是可直接重放的完整脚本。skillDirectory 是本 Skill 所在目录，不依赖开发者的安装路径。只运行当前完整计划，勿在有手改的草稿上强行复放全量前缀。

planPath、runDir 必须为绝对路径。新计划带 vault_path；旧计划缺此项时须显式提供 target.vaultPath。tempDir 可选，指定时须为 Vault 外绝对路径。输出、运行目录、临时目录不得覆盖源文件或计划；helper 会在页面写入前核验这些边界和依赖。

Python 解释器按 target.pythonExecutable → EgoLite 进程内 X_ARTICLE_PYTHON → 平台默认命令（Windows python，其他 python3）选择。优先传绝对路径，不能指望终端刚设置的环境变量自动传入 EgoLite。缺解释器或依赖时先修环境，不能绕过验收继续导入。

appendAndVerifySaved 会核账号、草稿与源指纹，观察网页操作触发的保存/上传请求，等待上传完成后的草稿保存，再重开并对照源计划前缀。它不会直接调用 X 私有接口。当前保存观察依赖页面请求特征；X 改版导致未观察到时会停止，不能视为保存成功。不要把网络事件、请求头、响应体整批存入日志。

底层 appendBlock 只返回 saved:false 的页面应用回执。上层 helper 通过后才返回 saved:true 与 source_verified:true，ui_checks 仍需界面检查。每次成功回执都持久记录，不能只存在进程变量。

## 保存验收与恢复

等待网页保存后重开同一 URL；composer 先出现时可能还是空占位，须等标题、文字、表格及所有图片 complete 且 naturalWidth>0。每块与计划对照，最终用 verify_snapshot.py --help 查完整验收参数；退出码 0 通过、1 有差异、2 输入错误、3 仍需实际界面检查。

用 readEditorWithMediaFingerprints 读取正文媒体身份，blob URL 跨重开会变；有内容指纹时据此比较，不能直接判定 URL 变化为图片变化。普通 HTTPS 图片仍核对图片位置与实际展示。

每次恢复先读取运行记录和同一草稿，三方比较源版本、最后验收快照与当前网页。源内容变化、账号不符或用户手改都需要重新判断；保全用户文字，不用旧计划覆盖。超时先看已写状态，最多做有证据的有限重试；未知时停在同一草稿说明，不复制草稿或无限重试。