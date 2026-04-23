"""检索子代理。"""

from __future__ import annotations

from agent.base import Agent
from context.builder import ContextBuilder
from model.client import ModelClient
from workspace.registry import WorkspaceRegistry


class RetrievalAgent(Agent):
    def __init__(
        self,
        model: ModelClient,
        workspaces: WorkspaceRegistry,
        context_builder: ContextBuilder,
    ) -> None:
        super().__init__(
            model=model,
            workspaces=workspaces,
            context_builder=context_builder,
            system_prompt="你是素材检索专家，负责从政策与资料角度提炼要点；输出应写入「检索结果.md」。",
            skill_keys=["gov_doc_format"],
            tool_names=["file_read", "memory_update"],
            use_stream=False,
        )
        self.agent_type = "retrieval"
        self.agent_id = "retrieval"
        self.display_name = "检索"
