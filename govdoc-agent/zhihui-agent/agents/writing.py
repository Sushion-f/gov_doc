"""写作子代理（流式 + 分段写入由工具层 EventBus 支持）。"""

from __future__ import annotations

from agent.base import Agent
from context.builder import ContextBuilder
from model.client import ModelClient
from workspace.registry import WorkspaceRegistry


class WritingAgent(Agent):
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
            system_prompt="你是公文撰写专家；可分段产出正文，配合 file_append / file_write 写入工作区。",
            skill_keys=["gov_doc_format", "writing_style_formal"],
            tool_names=["file_read", "file_append", "file_write"],
            use_stream=True,
        )
        self.agent_type = "writing"
        self.agent_id = "writing"
        self.display_name = "写作"
