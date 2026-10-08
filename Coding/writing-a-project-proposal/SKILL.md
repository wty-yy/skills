---
name: writing-a-project-proposal
description: Write, rewrite, condense, or format Chinese project proposal materials for NSFC, NDRC, government science projects, midterm reports, technical reports, and proposal-style documents. Use this skill when the user asks to convert one text or DOCX into another template style, draft research content, summarize key technical problems, align wording with a proposal format, maintain similar length and grammar, or output only the final Chinese result.
---

# Writing A Project Proposal

## 使用范围

用于中文项目申报、科技计划、发改委项目、自然科学基金、技术报告、中期报告等材料写作。常见任务包括：

- 将文本1改写为文本2的格式，保持字数基本一致、语法结构一致
- 将一个 `.docx` 材料改为另一个 `.docx` 模板格式
- 围绕给定内容生成研究内容、关键技术问题、测试支撑作用、项目目标等申报书段落
- 仿照样例精简、凝练、扩写已有内容
- 输出最终转换结果，并在用户要求时补充需要人工进一步修改的地方

除非用户明确要求英文，输出只使用中文。

## 工作流程

1. 识别用户任务类型，是格式仿写、模板转换、研究内容生成，还是关键技术问题凝练。
2. 读取用户提供的正文、样例、模板或本地文件。若涉及 `.docx`，优先提取正文与结构，再进行内容改写。
3. 保持目标样例的语法结构、段落数量、标题层级、句式密度和术语风格。
4. 按用户给定的字数、段落数、符号限制、主语限制和禁用词要求写作。
5. 若用户要求“只需输出最后转化得到的结果”，不要解释过程，不要添加多余说明。
6. 若用户要求“最后告诉我可能需要我进一步修改的地方”，先输出最终正文，再用简短小节列出需要人工核查的点。

## 写作原则

- 风格保持严谨、科学、学术化，适配国家自然科学基金、国家发改委项目、科技项目申报书等语境。
- 优先使用用户原文中的核心术语，同一概念保持同一表述。
- 避免自造词汇，避免宣传式、口号式、泛泛而谈的表达。
- 不随意改变用户指定的固定术语。例如用户要求“可信推理”的表述不要改变时，全篇统一使用“可信推理”。
- 避免出现用户禁用的表述。例如用户要求不要出现“可解释推理”，则完全规避。
- 用户限定标点时，严格使用允许的符号。
- 用户要求避免显式分点时，不使用“第一、第二、第三、首先、然后、最后”等显性序列词。
- 用户要求主语统一时，保持主语一致，同时通过省略主语、调整句式减少重复。
- 用户要求字数基本一致时，以原文或目标样例为长度基准，允许小幅浮动，但不大幅扩写或压缩。

## 常用模式

具体 prompt 模式、约束模板和写作范式见 `references/prompt-patterns.md`。当用户提出格式转换、DOCX模板转换、研究内容生成、关键技术问题凝练等任务时，先读取该参考文件。

## 输出要求

- 默认只输出用户要求的最终中文文本。
- 如用户要求落盘，遵循项目或 `AGENTS.md` 中的输出路径规则。
- 如用户要求给出修改建议，建议应简短、具体，聚焦数据、指标、项目名称、技术边界、模板字段等需要人工确认的内容。
- 不输出英文标题，不解释 skill 的使用过程，除非用户明确要求。
