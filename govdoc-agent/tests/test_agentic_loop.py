"""
Agentic Loop 相关单元测试（压缩、依赖分层、无网络）。

运行（在 govdoc-agent 目录下）:
  PYTHONPATH=. python3 -m unittest tests.test_agentic_loop -v

与端到端日志联调时，另开终端监控（见 scripts/watch_agentic_loop_logs.sh）。
"""

from __future__ import annotations

import unittest

from app.a2a_runtime import ExecutionStep
from app.compression import (
    apply_leader_context_guard,
    estimate_tokens,
    summarize_memory_for_context,
    truncate_tool_results,
)
from app.runtime import _execution_step_waves, _expand_effective_goal, _normalize_artifact_contract
from agents.main_agent import MainAgent


class TestCompressionHelpers(unittest.TestCase):
    def test_estimate_tokens_min_one(self) -> None:
        self.assertGreaterEqual(estimate_tokens([{"role": "user", "content": "hi"}]), 1)

    def test_summarize_memory_truncates_long_text(self) -> None:
        long_text = "段落一\n\n" + ("x" * 5000)
        out = summarize_memory_for_context(long_text, max_chars=200)
        self.assertLessEqual(len(out), 400)
        self.assertIn("truncated", out)

    def test_truncate_tool_results_long_content(self) -> None:
        long_json = '{"k": "' + ("v" * 6000) + '"}'
        msgs = [{"role": "tool", "tool_call_id": "c1", "content": long_json}]
        out = truncate_tool_results(msgs, max_tool_result_chars=4000)
        self.assertLessEqual(len(out[0]["content"]), 4500)
        self.assertIn("truncated", out[0]["content"])

    def test_apply_leader_context_guard_returns_list(self) -> None:
        base = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "你好"},
        ]
        guarded = apply_leader_context_guard(base, max_context_tokens=100_000)
        self.assertIsInstance(guarded, list)
        self.assertGreaterEqual(len(guarded), 2)


class TestExecutionStepWaves(unittest.TestCase):
    def test_empty_steps_empty_waves(self) -> None:
        self.assertEqual(_execution_step_waves([]), [])

    def test_chain_dependency_three_waves(self) -> None:
        s1 = ExecutionStep(
            index=1,
            skill_name="retrieval",
            title="检索",
            objective="o1",
            scope="s",
            depends_on=[],
        )
        sid1 = "step_01_retrieval"
        s2 = ExecutionStep(
            index=2,
            skill_name="writing",
            title="写作",
            objective="o2",
            scope="s",
            depends_on=[sid1],
        )
        sid2 = "step_02_writing"
        s3 = ExecutionStep(
            index=3,
            skill_name="review",
            title="审核",
            objective="o3",
            scope="s",
            depends_on=[sid2],
        )
        waves = _execution_step_waves([s1, s2, s3])
        self.assertEqual(len(waves), 3)
        self.assertEqual([w[0].skill_name for w in waves], ["retrieval", "writing", "review"])

    def test_parallel_same_wave_when_no_dep(self) -> None:
        a = ExecutionStep(1, "retrieval", "r1", "o", "s", depends_on=[])
        b = ExecutionStep(2, "retrieval", "r2", "o", "s", depends_on=[])
        waves = _execution_step_waves([a, b])
        self.assertEqual(len(waves), 1)
        self.assertEqual(len(waves[0]), 2)


class TestRuntimeContracts(unittest.TestCase):
    def test_expand_effective_goal_for_regenerate(self) -> None:
        goal, mode = _expand_effective_goal(
            "重新生成",
            {
                "intentType": "regenerate",
                "rewriteMode": "regenerate",
                "baseUserGoal": "起草一份国庆放假通知",
                "latestAssistantSummary": "已生成一版国庆放假通知草稿。",
                "latestArtifactRefs": [{"title": "公文写作结果.docx", "workspaceNodeId": "node_1"}],
            },
        )
        self.assertEqual(mode, "regenerate")
        self.assertIn("原始用户目标：起草一份国庆放假通知", goal)
        self.assertIn("最近一次结果摘要", goal)
        self.assertIn("公文写作结果.docx", goal)

    def test_normalize_artifact_contract_uses_camel_case(self) -> None:
        payload = _normalize_artifact_contract(
            {
                "artifact_type": "document",
                "content_html": "<p>正文</p>",
                "source_skill": "writing",
                "source_state": "model_success",
            }
        )
        self.assertEqual(payload["artifactType"], "document")
        self.assertEqual(payload["contentHtml"], "<p>正文</p>")
        self.assertEqual(payload["sourceSkill"], "writing")
        self.assertEqual(payload["sourceState"], "model_success")


class TestMainAgentHeuristics(unittest.TestCase):
    def test_simple_writing_shortcut_when_no_retrieval_needed(self) -> None:
        agent = MainAgent()
        self.assertTrue(
            agent._should_shortcut_simple_writing(
                "起草一份通知，不需要检索，直接生成国庆放假通知",
                None,
                [],
            )
        )

    def test_no_shortcut_for_empty_message(self) -> None:
        agent = MainAgent()
        self.assertFalse(agent._should_shortcut_simple_writing("", None, []))


if __name__ == "__main__":
    unittest.main()
