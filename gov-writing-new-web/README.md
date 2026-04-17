# gov-writing-new-web

Vue 3 + Vite 前端（GovDoc AgentLoop 对话与工作区）。

## 本地开发

```bash
npm install
npm run dev
```

默认通过 `VITE_API_BASE_URL`（未设置时为 `http://127.0.0.1:8000`）请求后端。HTTP 封装见 `src/api.js`，业务状态与接口调用见 `src/store.js`。

## 接口文档（与后端联调）

与本仓库同级的 **`docs/`** 目录（路径示例：`../docs/`）中与后端共用：

- **`前端-HTTP接口文档.md`** — 全部 API 路径、请求体、SSE 事件字段、鉴权方式  
- **`README.md`** — 文档索引  

后端服务见同级目录 **`govdoc-agent`**。
