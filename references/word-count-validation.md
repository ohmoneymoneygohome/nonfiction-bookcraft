# 长篇书稿字数校验

## 什么时候使用

只要书稿目录为章节、节或其他正文单元设了字数目标，就把目标纳入交付门槛。短文、邮件等没有全书结构的请求不需要建立这套清单。

## 计数口径

使用 `han_char_plus_ascii_word`：

- 每个可见汉字计 1，包括 CJK 统一表意文字及兼容汉字。
- 每个连续 ASCII 英文字母/数字词计 1；内部连字符或撇号连接的英文词仍计 1。例如 `AI`、`2026`、`long-form` 各计 1。
- 标点、空白、Markdown 标记、HTML 标签、URL、代码围栏中的代码不计。
- Markdown 标题的可见文字、列表/表格的可见文字计入。
- 文献、附录或其他非正文文件应在清单中显式排除，不能靠把它们塞入正文增加计数。

用户指定其他口径时，以用户口径为准，并在清单中记录。目标数字必须说明是“最低值”还是一个区间；默认 `min_words` 是硬性最低值，`max_words` 可选。不得自行按宽松百分比把未达目标判成通过。

## 清单格式

在项目根目录创建 `WORD_COUNT_TARGETS.json`：

```json
{
  "count_mode": "han_char_plus_ascii_word",
  "manuscript_dir": "MANUSCRIPT",
  "outline_path": "OUTLINE.md",
  "exclude": ["参考资料.md"],
  "chapters": [
    {"file": "01-introduction.md", "min_words": 5000},
    {"file": "02-method.md", "min_words": 8000, "max_words": 10000}
  ]
}
```

所有正文 Markdown 文件必须且只能出现在 `chapters` 或 `exclude` 中。`outline_path` 启用时，校验器会检查目录中的目标数值与每章 `min_words` 顺序一致；更新目标后必须同步两处。

## 执行与门槛

在项目根目录运行：

```bash
python /path/to/nonfiction-bookcraft/scripts/check_word_counts.py WORD_COUNT_TARGETS.json
```

校验器逐文件报告实际值和门槛。退出码 `0` 表示通过，`1` 表示字数不达标或超出上限，`2` 表示清单、路径、章节覆盖或目录目标有误。只有退出码为 `0` 才能把相应单元标为字数通过。正文被改动、拆分、合并或重排后必须重跑。

子代理、模型自报、编辑器状态栏和 PDF 页数只能用于诊断，不能替代该检查。长篇分工时，主代理负责清单、文件覆盖、最终计数和状态；分代理负责明确指派的章节，不得自行改变目标。
