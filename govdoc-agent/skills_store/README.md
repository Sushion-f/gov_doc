# skills_store

把 sub-agent 的系统提示词以 Markdown 配方文件的形式托管在这个目录下，
后端启动时会自动加载并覆盖 `prompts/sub/<name>.md` 的内置 prompt。

## 目录结构

```
skills_store/
  <name>/
    SKILL.md
```

其中 `<name>` 只允许 `A-Za-z0-9_-`，必须匹配 `agents/sub/` 中的 skill 名
（`retrieval` / `writing` / `dedup` / `layout` / `review` / `general`），
或未来通过代码注册的新 sub-agent。

## SKILL.md 格式

支持 YAML frontmatter + Markdown 正文。YAML 段只需简单 `key: value`，
若 value 以 `[` 或 `{` 起始会按 JSON 解析。

```markdown
---
name: retrieval
display: 检索专家 Claw
description: 在上传的工作区文件中检索资料并提炼要点
tools: [workspace.ls, workspace.cat, memory.read]
temperature: 0.3
output_schema: {"type": "object", "required": ["citations", "outline"]}
---

## 角色

你是一名资料检索专家……

## 返回格式

必须是严格 JSON，包含 `citations[]`、`outline[]`。
```

## 上传/覆盖/删除

前端或运维可直接调用以下 REST 接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET`    | `/api/agentloop/skills/custom` | 列出当前所有覆盖 |
| `GET`    | `/api/agentloop/skills/custom/{name}` | 读取原文 |
| `POST`   | `/api/agentloop/skills/custom` | multipart(file=SKILL.md) 或 form(name+markdown) |
| `DELETE` | `/api/agentloop/skills/custom/{name}` | 删除覆盖，回落到内置 prompt |

覆盖文件的 `mtime` 变化会触发下次请求时的热重载，无需重启。
