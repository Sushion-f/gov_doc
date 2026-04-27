from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from agents import canonical_agent_name, get_agent_spec, scope_for_agent, title_for_agent
from .schemas import TaskPacket


TASK_STATUS_CREATED = "created"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"
TASK_STATUS_STOPPED = "stopped"

@dataclass
class ExecutionStep:
    index: int
    skill_name: str
    title: str
    objective: str
    scope: str
    depends_on: list[str] = field(default_factory=list)
    subtask_role: str = "skill_worker"


@dataclass
class ExecutionPlan:
    intent: str
    summary: str
    steps: list[ExecutionStep]
    requires_user_input: bool = False
    clarification_question: str | None = None

    @property
    def primary_skill(self) -> str:
        if not self.steps:
            return "general"
        return self.steps[0].skill_name


@dataclass
class RegistryTaskMessage:
    role: str
    content: str
    timestamp: str


@dataclass
class RegistryTask:
    task_id: str
    parent_task_id: str | None
    title: str
    task_packet: TaskPacket
    status: str
    created_at: str
    updated_at: str
    output: str = ""
    team_id: str | None = None
    messages: list[RegistryTaskMessage] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "taskId": self.task_id,
            "parentTaskId": self.parent_task_id,
            "title": self.title,
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "output": self.output,
            "teamId": self.team_id,
            "taskPacket": self.task_packet.model_dump(),
            "messages": [
                {
                    "role": item.role,
                    "content": item.content,
                    "timestamp": item.timestamp,
                }
                for item in self.messages
            ],
        }


class A2ATaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, RegistryTask] = {}

    def register(
        self,
        packet: TaskPacket,
        title: str,
        *,
        parent_task_id: str | None = None,
        team_id: str | None = None,
    ) -> RegistryTask:
        now = datetime.utcnow().isoformat()
        task = RegistryTask(
            task_id=packet.task_id,
            parent_task_id=parent_task_id,
            title=title,
            task_packet=packet,
            status=TASK_STATUS_CREATED,
            created_at=now,
            updated_at=now,
            team_id=team_id,
        )
        self._tasks[packet.task_id] = task
        return task

    def set_status(self, task_id: str, status: str) -> RegistryTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.status = status
        task.updated_at = datetime.utcnow().isoformat()
        return task

    def append_message(self, task_id: str, role: str, content: str) -> RegistryTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.messages.append(
            RegistryTaskMessage(
                role=role,
                content=content,
                timestamp=datetime.utcnow().isoformat(),
            )
        )
        task.updated_at = datetime.utcnow().isoformat()
        return task

    def set_output(self, task_id: str, output: str) -> RegistryTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        task.output = output
        task.updated_at = datetime.utcnow().isoformat()
        return task

    def get_snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return task.snapshot()


a2a_task_registry = A2ATaskRegistry()


def title_for_skill(skill_name: str) -> str:
    return title_for_agent(skill_name)


def build_execution_plan(
    content: str,
    requested_skill: str | None,
    attachments: list[dict[str, Any]] | None = None,
) -> ExecutionPlan:
    attachments = attachments or []
    canonical = canonical_agent_name(requested_skill)
    if canonical:
        spec = get_agent_spec(canonical)
        objective = spec.default_objective
        if attachments:
            objective += " 需要结合用户上传附件。"
        return ExecutionPlan(
            intent="explicit_skill",
            summary=f"用户已直接选择 {spec.title}，由该 sub agent 直接处理当前请求。",
            steps=[
                ExecutionStep(
                    index=1,
                    skill_name=spec.name,
                    title=spec.title,
                    objective=objective,
                    scope=spec.scope,
                    subtask_role=spec.default_subtask_role,
                )
            ],
        )

    spec = get_agent_spec("general")
    objective = spec.default_objective
    if attachments:
        objective += " 需要参考用户上传附件。"
    return ExecutionPlan(
        intent="general_chat",
        summary="planner 不可用时，默认由主 Agent 直接回应用户，并在必要时提示后续可调用的 sub agent。",
        steps=[
            ExecutionStep(
                index=1,
                skill_name=spec.name,
                title=spec.title,
                objective=objective,
                scope=spec.scope,
                subtask_role=spec.default_subtask_role,
            )
        ],
    )


def build_root_task_packet(
    *,
    task_id: str,
    conversation_id: str,
    objective: str,
    requested_model: str | None,
    plan: ExecutionPlan,
    attachments: list[dict[str, Any]],
    runtime_context_summary: str,
    user_memory_refs: list[str],
) -> TaskPacket:
    return TaskPacket(
        task_id=task_id,
        conversation_id=conversation_id,
        parent_task_id=None,
        objective=objective,
        skill_name=plan.primary_skill,
        scope=plan.summary,
        repo="gov-writing-new-system",
        branch_policy="single-request runtime dispatch only",
        acceptance_tests=[
            "每个 sub-agent 必须返回结构化结果",
            "完整保留事件流与历史记录",
            "需要落盘的产物必须进入工作空间",
        ],
        commit_policy="no git commit during runtime execution",
        team_id="leader-agent",
        subtask_role="leader_agent",
        input_payload={
            "content": objective,
            "model": requested_model,
            "runningContextSummary": runtime_context_summary,
            "planIntent": plan.intent,
            "planSteps": [step.skill_name for step in plan.steps],
        },
        attachments=attachments,
        acceptance_criteria=[
            "生成结构化步骤流",
            "保留完整历史并可回放",
            "如有产物则同步到工作空间",
        ],
        reporting_contract="输出 leader plan、subtask 结果、编辑器标注和产物引用",
        escalation_policy="skill 失败时先尝试 fallback；若仍不可执行则返回失败事件或等待用户补充信息",
        user_memory_refs=user_memory_refs,
    )


def build_subtask_packet(
    *,
    task_id: str,
    parent_task_id: str,
    conversation_id: str,
    step: ExecutionStep,
    requested_model: str | None,
    step_input: str,
    attachments: list[dict[str, Any]],
    runtime_context_summary: str,
    user_memory_refs: list[str],
    handoff_trace: list[dict[str, Any]],
) -> TaskPacket:
    team_id = "leader-agent-direct" if step.subtask_role == "main_agent" else f"sub-agent-{step.skill_name}"
    return TaskPacket(
        task_id=task_id,
        conversation_id=conversation_id,
        parent_task_id=parent_task_id,
        objective=step.objective,
        skill_name=step.skill_name,
        scope=step.scope,
        repo="gov-writing-new-system",
        branch_policy="subtask local execution only",
        acceptance_tests=[
            f"{step.title} 输出必须可被 leader 汇总",
            "结果要包含 normalized_result / render_blocks / artifact_refs / annotations",
        ],
        commit_policy="persist into conversation database and workspace only",
        team_id=team_id,
        subtask_role=step.subtask_role,
        input_payload={
            "content": step_input,
            "model": requested_model,
            "runningContextSummary": runtime_context_summary,
            "handoffTrace": handoff_trace,
            "dependsOn": step.depends_on,
        },
        attachments=attachments,
        acceptance_criteria=[
            f"完成 {step.title} 子任务",
            "向 leader 返回结构化结果",
        ],
        reporting_contract="返回结构化 result 供 leader merge",
        escalation_policy="旧系统 skill 不可用时允许模型 fallback；仍失败则返回 failed",
        user_memory_refs=user_memory_refs,
    )


def build_handoff_content(
    previous_input: str,
    step_skill: str,
    normalized_result: dict[str, Any],
) -> str:
    """将上一步骤的结果拼接到 previous_input，形成下一步骤的 task_prompt。

    对 retrieval：
    - 若 LLM 兜底输出了整段摘要（summary_text），优先整段下传，而不是仅按 bullet 截断，
      避免写作步骤拿到的只是去除结构的片段。
    - 若 legacy 返回结构化 items，则取 top-N 的 title/summary 列点。
    """
    step_skill = canonical_agent_name(step_skill) or step_skill
    clarification = (normalized_result.get("user_clarification") or "").strip()
    question = (normalized_result.get("question") or "").strip()
    if step_skill == "retrieval":
        if clarification:
            return (
                previous_input.strip()
                + "\n\n用户补充信息：\n"
                + clarification
                + (f"\n补充针对问题：{question}" if question else "")
            )
        summary_text = (normalized_result.get("summary_text") or "").strip()
        if summary_text:
            truncated = summary_text if len(summary_text) <= 4000 else summary_text[:4000] + "…"
            return (
                previous_input.strip()
                + "\n\n【前序 retrieval 步骤提供的整段背景资料（请直接作为写作依据，不要再额外检索）】\n"
                + truncated
            )
        items = normalized_result.get("items") or []
        bullets: list[str] = []
        for item in items[:8]:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or item.get("name") or "资料").strip()
            summary = (item.get("summary") or item.get("content") or "").strip()
            if summary:
                bullets.append(f"- {title}: {summary}")
            else:
                bullets.append(f"- {title}")
        if bullets:
            return (
                previous_input.strip()
                + "\n\n【前序 retrieval 步骤提供的参考资料要点】\n"
                + "\n".join(bullets)
                + "\n\n请基于以上要点完成下一步，不要再额外检索外部资料。"
            )
        return previous_input
    if step_skill == "writing":
        if clarification:
            return (
                previous_input.strip()
                + "\n\n用户补充写作要求：\n"
                + clarification
                + (f"\n补充针对问题：{question}" if question else "")
            )
        return normalized_result.get("document") or previous_input
    if clarification:
        return (
            previous_input.strip()
            + "\n\n用户补充信息：\n"
            + clarification
            + (f"\n补充针对问题：{question}" if question else "")
        )
    return previous_input


def format_dispatch_tool_result_json(
    *,
    step: ExecutionStep,
    subtask_id: str,
    normalized_result: dict[str, Any],
    source_state: str | None,
    error_detail: str | None,
    retryable: bool,
) -> str:
    """供 Leader 闭环追加的 OpenAI tool 消息正文（结构化 JSON 字符串）。"""
    payload = {
        "type": "dispatch_sub_agent_result",
        "taskId": subtask_id,
        "skillName": step.skill_name,
        "stepTitle": step.title,
        "stepIndex": step.index,
        "normalizedResult": normalized_result,
        "sourceState": source_state,
        "errorDetail": error_detail,
        "retryable": retryable,
    }
    return json.dumps(payload, ensure_ascii=False)


def build_synthetic_dispatch_tool_calls(
    steps: list[ExecutionStep],
    *,
    task_prompts: list[str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """为已执行步骤构造 assistant.tool_calls 与对应的 tool_call_id 列表。"""
    tool_calls: list[dict[str, Any]] = []
    ids: list[str] = []
    for step, prompt in zip(steps, task_prompts):
        call_id = f"call_step_{step.index:02d}_{step.skill_name}"
        ids.append(call_id)
        arguments = {
            "agent_name": step.skill_name,
            "task_prompt": prompt,
            "context": {},
            "run_in_background": False,
        }
        tool_calls.append(
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": "dispatch_sub_agent",
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        )
    return tool_calls, ids
