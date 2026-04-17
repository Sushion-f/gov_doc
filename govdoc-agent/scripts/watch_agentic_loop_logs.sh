#!/usr/bin/env bash
# 监控 Agentic Loop / Leader 反思相关调试日志（依赖 log_stage 输出到同一日志流）。
#
# 用法（项目根目录 govdoc-agent 下）:
#   chmod +x scripts/watch_agentic_loop_logs.sh
#   ./scripts/watch_agentic_loop_logs.sh
#
# 若主进程把 stdout 重定向到 runtime_logs/govdoc_agent.log，则:
#   ./scripts/watch_agentic_loop_logs.sh runtime_logs/govdoc_agent.log
#
# 环境变量 NEW_APP_DEBUG_RUNTIME_LOGS=true（默认）才会出现 [debug:leader.reflect] 等行。

set -euo pipefail
LOG="${1:-runtime_logs/govdoc_agent.log}"

if [[ ! -f "$LOG" ]]; then
  echo "文件不存在: $LOG"
  echo "请先启动服务并将日志重定向到该路径，或传入实际日志文件路径。"
  exit 1
fi

echo "跟踪: $LOG"
echo "过滤: 所有 [debug:...] 行（含 leader.reflect / planner / runtime / skill）"
echo "---"
tail -n 80 -f "$LOG" | grep --line-buffered -E '\[debug:'
