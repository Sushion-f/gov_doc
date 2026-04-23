"""审核子代理。"""

from __future__ import annotations

from agent.base import Agent
from context.builder import ContextBuilder
from model.client import ModelClient
from workspace.registry import WorkspaceRegistry


class ReviewAgent(Agent):
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
            system_prompt="你是公文审核专家；输出「审核报告.md」。",
            skill_keys=["review_criteria", "gov_doc_format"],
            tool_names=["file_read", "file_write"],
            use_stream=False,
        )
        self.agent_type = "review"
        self.agent_id = "review"
        self.display_name = "审核"
