"""查重子代理。"""

from __future__ import annotations

from agent.base import Agent
from context.builder import ContextBuilder
from model.client import ModelClient
from workspace.registry import WorkspaceRegistry


class PlagiarismAgent(Agent):
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
            system_prompt="你是查重专家；结合 similarity_check 输出「查重报告.md」。",
            skill_keys=[],
            tool_names=["file_read", "file_write", "similarity_check"],
            use_stream=False,
        )
        self.agent_type = "plagiarism"
        self.agent_id = "plagiarism"
        self.display_name = "查重"
