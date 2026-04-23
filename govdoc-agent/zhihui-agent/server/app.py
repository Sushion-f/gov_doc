"""FastAPI：挂载路由与 WebSocket。"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
for p in (_SRC, _ROOT):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from server.routes.artifacts import create_artifacts_router
    from server.routes.assets import create_assets_router
    from server.routes.chat import create_chat_router
    from zhihui_agent import create_zhihui_agent

    data_root = _ROOT / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    def _factory():
        return create_zhihui_agent({"root": _ROOT, "data_root": data_root, "skills_dir": _ROOT / "skills"})

    app.state.agent_factory = _factory
    app.include_router(create_artifacts_router(data_root))
    app.include_router(create_assets_router(data_root))
    app.include_router(create_chat_router(lambda: app.state.agent_factory()))
    yield


app = FastAPI(title="Zhihui Agent", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "zhihui-agent"}
