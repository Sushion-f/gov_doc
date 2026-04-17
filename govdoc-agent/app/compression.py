from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryCompressionBudget:
    max_chars: int = 1200
    max_lines: int = 24
    max_line_chars: int = 160


def collapse_inline_whitespace(line: str) -> str:
    return " ".join(line.split())


def truncate_line(line: str, max_chars: int) -> str:
    if max_chars <= 0 or len(line) <= max_chars:
        return line
    if max_chars == 1:
        return "…"
    return line[: max_chars - 1] + "…"


def dedupe_lines(lines: list[str], budget: SummaryCompressionBudget) -> tuple[list[str], int]:
    seen = set()
    result: list[str] = []
    removed = 0
    for raw in lines:
        normalized = collapse_inline_whitespace(raw)
        if not normalized:
            continue
        normalized = truncate_line(normalized, budget.max_line_chars)
        key = normalized.lower()
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        result.append(normalized)
    return result, removed


def compress_summary_text(summary: str, budget: SummaryCompressionBudget) -> tuple[str, dict]:
    normalized, removed = dedupe_lines(summary.splitlines(), budget)
    if not normalized:
        return "", {
            "original_lines": 0,
            "compressed_lines": 0,
            "removed_duplicate_lines": removed,
            "omitted_lines": 0,
            "truncated": False,
        }

    selected: list[str] = []
    total_chars = 0
    omitted = 0
    for line in normalized:
        line_len = len(line) + (1 if selected else 0)
        if len(selected) >= budget.max_lines or total_chars + line_len > budget.max_chars:
            omitted += 1
            continue
        selected.append(line)
        total_chars += line_len

    if omitted:
        notice = f"- … {omitted} additional line(s) omitted."
        if len(selected) < budget.max_lines and total_chars + len(notice) + 1 <= budget.max_chars:
            selected.append(notice)

    compressed = "\n".join(selected)
    return compressed, {
        "original_lines": len(summary.splitlines()),
        "compressed_lines": len(selected),
        "removed_duplicate_lines": removed,
        "omitted_lines": omitted,
        "truncated": compressed.strip() != summary.strip(),
    }


def build_structured_summary(
    older_messages: list[dict],
    recent_messages: list[dict],
    tool_names: list[str],
    key_files: list[str],
) -> str:
    recent_user_requests = [
        msg["content"].strip().replace("\n", " ")
        for msg in older_messages + recent_messages
        if msg["role"] == "user" and msg["content"].strip()
    ][-3:]

    current_work = recent_messages[-1]["content"].strip().replace("\n", " ") if recent_messages else "继续处理当前会话"
    pending_work = []
    if recent_messages and recent_messages[-1]["role"] == "assistant":
        pending_work.append("等待用户继续追问、确认修改或打开联动文档。")
    else:
        pending_work.append("继续完成当前任务并生成可落盘产物。")

    timeline = []
    for msg in older_messages[-6:] + recent_messages[-4:]:
        prefix = msg["role"]
        content = msg["content"].strip().replace("\n", " ")
        if len(content) > 120:
            content = content[:119] + "…"
        timeline.append(f"  - {prefix}: {content}")

    lines = [
        "Summary:",
        f"- Scope: {len(older_messages)} earlier message(s) compacted.",
        f"- Current work: {current_work or '继续处理当前会话。'}",
        "- Pending work:",
        *[f"  - {item}" for item in pending_work],
        "- Tools mentioned:",
    ]
    if tool_names:
        lines.extend([f"  - {name}" for name in sorted(set(tool_names))])
    else:
        lines.append("  - lead_agent")
    lines.append("- Recent user requests:")
    if recent_user_requests:
        lines.extend([f"  - {item}" for item in recent_user_requests])
    else:
        lines.append("  - 暂无可总结请求。")
    lines.append("- Key files referenced:")
    if key_files:
        lines.extend([f"  - {item}" for item in sorted(set(key_files))])
    else:
        lines.append("  - 暂无")
    lines.append("- Key timeline:")
    lines.extend(timeline or ["  - 暂无"])
    return "\n".join(lines)


# --- Leader / context window guard (Agentic Loop) ---

# 粗略 token 估计：约 4 字符/token（中英混合近似）
CHARS_PER_TOKEN_EST = 4
DEFAULT_MAX_CONTEXT_TOKENS = 32000
DEFAULT_TOOL_RESULT_MAX_CHARS = 4000


def estimate_tokens(messages: list[dict]) -> int:
    """粗略估计 messages 的 token 数（用于预检与裁剪触发）。"""
    total_chars = 0
    for msg in messages:
        role = msg.get("role") or ""
        content = msg.get("content")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    total_chars += len(str(part.get("text") or part.get("output_text") or ""))
        tool_calls = msg.get("tool_calls") or []
        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            total_chars += len(str(fn.get("arguments") or "")) + len(str(fn.get("name") or ""))
        if role == "tool":
            total_chars += len(str(msg.get("tool_call_id") or ""))
    return max(1, total_chars // CHARS_PER_TOKEN_EST)


def truncate_tool_results(
    messages: list[dict],
    *,
    max_tool_result_chars: int = DEFAULT_TOOL_RESULT_MAX_CHARS,
) -> list[dict]:
    """对 role=tool 的单条 content 做长度截断，返回新列表。"""
    out: list[dict] = []
    for msg in messages:
        if msg.get("role") != "tool":
            out.append(msg)
            continue
        m = dict(msg)
        content = m.get("content")
        if isinstance(content, str) and len(content) > max_tool_result_chars:
            tail = max_tool_result_chars // 4
            m["content"] = (
                content[: max_tool_result_chars - tail]
                + "\n…[truncated]…\n"
                + content[-tail:]
            )
        out.append(m)
    return out


def prune_oldest_tool_exchange(messages: list[dict], *, keep_last_pairs: int = 6) -> list[dict]:
    """移除最早的多轮 assistant(tool_calls)+tool 对，保留系统与用户首条。"""
    if len(messages) <= 2 or keep_last_pairs <= 0:
        return messages
    head: list[dict] = []
    i = 0
    # 保留 system + 第一条 user
    while i < len(messages) and messages[i].get("role") == "system":
        head.append(messages[i])
        i += 1
    if i < len(messages) and messages[i].get("role") == "user":
        head.append(messages[i])
        i += 1
    rest = messages[i:]
    pairs: list[list[dict]] = []
    j = 0
    while j < len(rest):
        if rest[j].get("role") == "assistant" and rest[j].get("tool_calls"):
            block = [rest[j]]
            j += 1
            while j < len(rest) and rest[j].get("role") == "tool":
                block.append(rest[j])
                j += 1
                if len(block) > 20:
                    break
            pairs.append(block)
        else:
            j += 1
    if len(pairs) <= keep_last_pairs:
        return messages
    kept = pairs[-keep_last_pairs:]
    flat = [item for block in kept for item in block]
    return head + flat


def summarize_memory_for_context(text: str, *, max_chars: int = 2000) -> str:
    """记忆类 markdown 瘦身：首段摘要 + 截断。"""
    raw = (text or "").strip()
    if not raw:
        return ""
    if len(raw) <= max_chars:
        return raw
    first_block = raw.split("\n\n", 1)[0].strip()
    head = first_block[: min(400, len(first_block))]
    remainder_budget = max_chars - len(head) - 40
    if remainder_budget < 200:
        return head + "\n…[memory truncated]…"
    mid = raw[len(first_block) :].strip()
    return head + "\n\n" + mid[:remainder_budget] + "\n…[memory truncated]…"


def apply_leader_context_guard(
    messages: list[dict],
    *,
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
    precheck_ratio: float = 0.85,
    tool_result_max_chars: int = DEFAULT_TOOL_RESULT_MAX_CHARS,
    summary_budget: SummaryCompressionBudget | None = None,
) -> list[dict]:
    """
    四层保护（顺序）：预检 → tool 截断 → 会话式压缩（摘要）→ 裁剪最早 tool 交换。
    """
    budget = summary_budget or SummaryCompressionBudget()
    msgs = truncate_tool_results(list(messages), max_tool_result_chars=tool_result_max_chars)
    est = estimate_tokens(msgs)
    if est > int(max_context_tokens * precheck_ratio):
        compressed: list[dict] = []
        for msg in msgs:
            if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                text, _meta = compress_summary_text(msg["content"], budget)
                compressed.append({**msg, "content": text})
            elif msg.get("role") == "system" and isinstance(msg.get("content"), str):
                text, _meta = compress_summary_text(msg["content"], budget)
                compressed.append({**msg, "content": text})
            else:
                compressed.append(msg)
        msgs = compressed
    est2 = estimate_tokens(msgs)
    if est2 > int(max_context_tokens * precheck_ratio):
        msgs = prune_oldest_tool_exchange(msgs, keep_last_pairs=4)
        msgs = truncate_tool_results(msgs, max_tool_result_chars=tool_result_max_chars)
    return msgs
