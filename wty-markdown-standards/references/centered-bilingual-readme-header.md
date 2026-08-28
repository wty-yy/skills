# Centered Bilingual README Header Template

Use this template for a new public or project-facing bilingual README when the title style is unspecified or the user requests a centered title section.

Keep YAML frontmatter before the header. Replace every `{{PLACEHOLDER}}`. Do not add a second Markdown `#` heading below this block.

## `README.md`

```html
<div align="center">
  <h1>{{PROJECT_TITLE}}</h1>
  <p><strong>{{ENGLISH_REPOSITORY_SUMMARY}}</strong></p>
  <p><strong>🌎 English</strong>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="README.zh-CN.md">🇨🇳 中文</a></p>
</div>
```

## `README.zh-CN.md`

```html
<div align="center">
  <h1>{{PROJECT_TITLE}}</h1>
  <p><strong>{{CHINESE_REPOSITORY_SUMMARY}}</strong></p>
  <p><a href="README.md">🌎 English</a>&nbsp;&nbsp;·&nbsp;&nbsp;<strong>🇨🇳 中文</strong></p>
</div>
```

Use the same project title and equivalent summaries in both files. Keep the current language bold and the alternate language linked.
