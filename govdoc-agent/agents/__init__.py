from .registry import (
    AgentDefinition,
    AgentRegistry,
    canonical_agent_name,
    exposed_agent_descriptors,
    get_agent_spec,
    prompt_key_for_agent,
    scope_for_agent,
    selectable_sub_agents,
    system_prompt_for_agent,
    title_for_agent,
)
from .sub import register_builtin_sub_agents


register_builtin_sub_agents()

__all__ = [
    "AgentDefinition",
    "AgentRegistry",
    "canonical_agent_name",
    "exposed_agent_descriptors",
    "get_agent_spec",
    "prompt_key_for_agent",
    "scope_for_agent",
    "selectable_sub_agents",
    "system_prompt_for_agent",
    "title_for_agent",
]
