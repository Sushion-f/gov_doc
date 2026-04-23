# GovDoc Agent（智慧公文后端）

本仓库后端已收敛为 **`zhihui-agent/`** 单一子项目，其余旧版 `app/`、`agents/`、`tools/` 等已移除。

## 目录

- `zhihui-agent/src/`：核心库（`model` / `workspace` / `skill` / `tool` / `context` / `orchestrator` / `agent` / `events`）
- `zhihui-agent/agents/`：子代理（检索 / 写作 / 审核 / 排版 / 查重）
- `zhihui-agent/skills/`：`SKILL.md` 技能包
- `zhihui-agent/server/`：FastAPI + WebSocket + 素材与产物 HTTP
- `zhihui-agent/data/workspaces/`：运行时用户工作区根（`{user_id}/...`）

## 环境变量

| 变量 | 说明 |
|------|------|
| `ZHIHUI_LLM_BASE_URL` | OpenAI 兼容网关，如 `https://api.openai.com/v1` |
| `ZHIHUI_LLM_API_KEY` | API Key |
| `ZHIHUI_LLM_MODEL` | 默认模型名 |

## 启动

```bash
cd zhihui-agent
python -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
export ZHIHUI_LLM_BASE_URL=... ZHIHUI_LLM_API_KEY=...
uvicorn server.app:app --host 127.0.0.1 --port 8000
```

- 健康检查：`GET /health`
- WebSocket：`WS /ws/chat`，消息形如 `{"type":"chat","user_message":"...","user_id":"u1","session_id":"s1"}`

## 说明

- **唯一 HTTP 调 LLM** 实现在 `src/model/client.py`（`httpx`，不依赖 `openai` SDK）。
- 子代理可通过 `ToolRegistry.register_agent` 挂到主循环（当前默认 Orchestrator 使用内置 file_* 工具与单次规划）。
