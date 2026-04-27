# GovDoc Agent

Independent Python backend for the GovDoc agent runtime.   

## 协作文档（与前端联调）

与本仓库同级的 **`docs/`**（路径示例：`../docs/`）提供：

- **`前端-HTTP接口文档.md`** — 前端：全部 HTTP/SSE 路径、请求体、鉴权与调用顺序  
- **`后端-服务说明与联调指南.md`** — 后端：启动、配置、运行链路、联调清单  

索引：**`../docs/README.md`**

## Run

```bash
cd govdoc-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## One-click Start / Stop

```bash
cd govdoc-agent
chmod +x manage_govdoc_agent.sh
./manage_govdoc_agent.sh start
./manage_govdoc_agent.sh dev
./manage_govdoc_agent.sh status
./manage_govdoc_agent.sh logs
./manage_govdoc_agent.sh stop
```

You can override env vars inline when needed:

```bash
ENABLE_DEV_AUTH_MOCK=false ./manage_govdoc_agent.sh restart
```

LLM 网关地址、API Key、默认模型、超时、Planner、可选模型列表等 **全部只从** [`config/model.json`](config/model.json) 的 `llm` 段读取，**不再**使用 `OPENAI_*` / `NEW_APP_LLM_*` 环境变量或代码里的供应商默认 URL。修改后需重启后端。

默认健康检查接口为 `GET /api/agentloop/health`。

Detailed runtime logs are enabled by default and will print to both the terminal and `runtime_logs/govdoc_agent.log`.

If you want to watch the full request/context/model trace directly in your terminal, use foreground mode:

```bash
./manage_govdoc_agent.sh dev
```

```bash
NEW_APP_DEBUG_RUNTIME_LOGS=true ./manage_govdoc_agent.sh restart
NEW_APP_DEBUG_LOG_MAX_CHARS=80000 ./manage_govdoc_agent.sh restart
```

## 模型配置（单一文件）

启动时顺序为：**加载项目根目录 `.env`（非 LLM 项）** → **读取 `config/model.json` 中的 `llm` 段** → 组装 `Settings` 中的 LLM 相关字段。**LLM 仅认 `model.json`**，勿再通过环境变量覆盖。

- 配置文件路径：[`config/model.json`](config/model.json)（含 `base_url`、`api_key`、`default_model`、`available_models` 等）
- 敏感信息可写在 `model.json` 本地副本中，**勿将含 Key 的文件提交到仓库**（用 `.gitignore` 或私有部署配置）。
- **火山方舟 OpenAI 兼容**：常见为 `base_url` = `https://ark.cn-beijing.volces.com/api/v3` 或 **`.../api/coding/v3`**（与账号/产品线有关）。若请求 `.../chat/completions` **404**，可切换上述路径，或设置 **`chat_completions_url`** 为控制台文档给出的完整 POST 地址。
- **`default_model` / `available_models[].id`**：方舟侧通常填控制台 **推理接入点 ID**（形如 `ep-xxxx`），填展示名可能导致 4xx。

## Key env vars

- `NEW_APP_DATABASE_URL`: SQLAlchemy database URL. Defaults to `sqlite:///./govdoc_agent.db`.
- `LEGACY_AUTH_BASE_URL`: Old Java service base URL, for example `http://127.0.0.1:8080/areport`.
- `LEGACY_SYSTEM_URL`: Old system page URL used by the frontend switch button.
- `ENABLE_DEV_AUTH_MOCK`: Defaults to `true`. Returns a mock logged-in user when legacy auth is unavailable.
- `NEW_APP_DEBUG_RUNTIME_LOGS`: Defaults to `true`. Prints detailed request, context, skill, LLM, and response traces.
- `NEW_APP_DEBUG_LOG_MAX_CHARS`: Max chars per debug log block. Defaults to `40000`.
- `NEW_APP_DEBUG_LOG_MAX_STRING_CHARS`: Max chars per string field before clipping. Defaults to `12000`.
