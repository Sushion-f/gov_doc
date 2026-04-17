from __future__ import annotations

from dataclasses import dataclass

from .registry import AgentDefinition, system_prompt_for_agent


@dataclass
class BaseAgent:
    definition: AgentDefinition

    def build_system_prompt(self, context: dict | None = None) -> str:
        prompt = system_prompt_for_agent(self.definition.name)
        context = context or {}
        sections: list[str] = [prompt]
        doc_content = (context.get("doc_content") or "").strip()
        doc_type = (context.get("doc_type") or "").strip()
        user_intent = (context.get("user_intent") or "").strip()
        if doc_content or doc_type or user_intent:
            sections.append("## 当前上下文")
            if user_intent:
                sections.append(f"- 用户意图：{user_intent}")
            if doc_type:
                sections.append(f"- 公文类型：{doc_type}")
            if doc_content:
                sections.append("")
                sections.append("### 当前公文内容")
                sections.append(doc_content)
        return "\n".join(part for part in sections if part).strip()
