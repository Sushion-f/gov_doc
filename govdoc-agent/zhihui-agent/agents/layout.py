"""排版子代理。"""

from __future__ import annotations

from agent.base import Agent
from context.builder import ContextBuilder
from model.client import ModelClient
from workspace.registry import WorkspaceRegistry


class LayoutAgent(Agent):
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
            system_prompt="你是公文排版专家；可调用 docx_render 生成版式文件（占位实现）。",
            skill_keys=["gov_doc_format"],
            tool_names=["file_read", "file_write", "docx_render"],
            use_stream=False,
        )
        self.agent_type = "layout"
        self.agent_id = "layout"
        self.display_name = "排版"
