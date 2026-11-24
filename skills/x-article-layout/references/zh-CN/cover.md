# 封面发现、生成与上传

[English](../en/cover.md) | [简体中文](cover.md)

封面是文章级图片，与正文图片分开处理。默认保留草稿已有封面，包含用户在 X 手动设置的封面。

## 选择本篇图片

先用 cover-ui.mjs 的 readCover(page) 读取当前草稿。present 只表示页面当前有图，crop_dialog_open 为 true 时可能仍是未保存预览；结合本次记录检查未完成上传，不重新覆盖。

草稿无封面时用 discover_cover.py --help 查参数，执行：

```bash
python -X utf8 /absolute/path/x-article-layout/scripts/discover_cover.py --vault /absolute/path/vault --source /absolute/path/vault/article.md --output /absolute/path/private-runs/cover-discovery.json
```

发现器按明确 frontmatter（cover、cover_image、封面、封面图、封面路径）、明确标注的封面区块、同篇附件目录中明确 cover/封面命名的图片选择。首图、目录图或横版比例本身不能证明它是封面。状态分支：

- found：核对选图依据、文件 SHA 和实际画面后复用。
- missing：根据原文生成；若本次记录已有匹配源/风格的成图，核 SHA 后复用。
- ambiguous：只解决具体候选歧义，不随便选一张。
- invalid_reference：保全原引用，说明失效项；不悄悄忽略显式封面配置。

无需为让发现器找到封面而修改原稿。用户指定独立封面文件时按明确指示处理，并保留来源记录。

## 缺图时生成

先读取用户本次风格要求或其明确指定的风格文件；没有时采用简洁编辑式封面：清楚的主题物、少量短标题、留白和足够对比度。标题、主题与收益来自原文，不添加“保证成功”“永久免费”等未有依据的承诺。不能把目录图换标题就当作封面。

X 默认请求 5:2。选择当前宿主提供且获授权的生成工具，遵循适用的图像规则与本地配置优先级；不假设每个安装者都有某项付费服务。API 密钥只从用户本地配置或安全环境读取，不显示、不写入日志、不放进 Skill。外部生成服务会收到提示词/参考素材，优先仅发送必要的文章主题、摘要与封面文字，不能把无关私稿或凭据作为提示词。

没有可用生成工具时，明确“正文已保存，封面待补”，让用户提供图片或配置工具后继续；不画占位图冒充最终封面，不静默购买额度或切换付费服务。生成失败只报告脱敏错误；替代工具获现有授权时可使用，并如实记录实际生成方式。

实际检查像素比例、中文、信息准确性和缩略图可读性。原图的像素取整误差可在 X 原生 5:2 裁切中调整，文字和主题物留安全边距。文件保存在用户运行资产目录，不默认写回 Vault。

成功成图先记录 generated：源/风格指纹、文件绝对路径、SHA、像素与生成方式。之后记录 uploading、saved_verified。上传失败优先复用同图，避免重复计费；源或风格变化时重新判断旧图是否仍适用。

## 上传同一草稿

1. 核对账号与真实草稿 URL。用 readEditorWithMediaFingerprints 保存当前正文基线，不能用旧原稿覆盖用户在 X 的手改。
2. 用 readCover 再确认没有已保存封面。控件候选是标题之前、composer 外、dialog 外的 input[type="file"][accept="image/jpeg,image/png,image/webp"]。匹配不唯一时先观察，不按全页第一个 input 猜。
3. page.setInputFiles 后通常出现 Edit media 裁切弹窗。背景图片预览不代表保存；读取实际截图检查固定 5:2 框内文字和主题物完整，再点 Apply。
4. 等待页面自己的媒体上传与文章保存完成，重开同一草稿确认封面仍在；检查实际裁切和清晰度。X 可能重编码图片，不能直接要求本地原图字节 SHA 等于压缩图 SHA。
5. 重新读取正文并执行 assertBodyUnchanged(before,after)，核对文字、表格、链接及正文图片身份顺序。发现差异先保全并检查，不能为让校验通过而重写正文。

辅助函数位于 scripts/cover-ui.mjs：readCover(page)、bodyCanonical(state)、assertBodyUnchanged(before,after)。正文快照来自 scripts/ego-import.mjs。封面与正文图片分别计数，Insert → Media 或 appendBlock(image) 不能代替封面上传。始终不点击 Publish。