#!/usr/bin/env bash
# 监控 Agentic Loop / Leader 反思相关调试日志。
#
# 日志默认分两路写入 runtime_logs/：
#   - backend.log  后端调用（runtime / planner / routes / storage / workspace …）
#   - model.log    模型调用（llm.request.* / llm.response.*；流式输出在流结束后作为 llm.response 一整块写入）
#
# 用法（项目根目录 govdoc-agent 下）:
#   chmod +x scripts/watch_agentic_loop_logs.sh
#   ./scripts/watch_agentic_loop_logs.sh            # 同时 tail backend 与 model 两个文件
#   ./scripts/watch_agentic_loop_logs.sh backend    # 只看后端
#   ./scripts/watch_agentic_loop_logs.sh model      # 只看模型
#   ./scripts/watch_agentic_loop_logs.sh path/to/xxx.log   # 显式文件
#
# 环境变量 NEW_APP_DEBUG_RUNTIME_LOGS=true（默认）才会出现 [debug:...] 行。

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BACKEND="$ROOT_DIR/runtime_logs/backend.log"
DEFAULT_MODEL="$ROOT_DIR/runtime_logs/model.log"

target="${1:-all}"
case "$target" in
  all)
    files=("$DEFAULT_BACKEND" "$DEFAULT_MODEL")
    ;;
  backend)
    files=("$DEFAULT_BACKEND")
    ;;
  model)
    files=("$DEFAULT_MODEL")
    ;;
  *)
    files=("$target")
    ;;
esac

for f in "${files[@]}"; do
  [[ -f "$f" ]] || { echo "文件不存在: $f"; echo "请先启动服务生成该文件，或传入实际日志文件路径。"; exit 1; }
done

echo "跟踪:"
for f in "${files[@]}"; do echo "  - $f"; done
echo "过滤: 所有 [debug:...] 行"
echo "---"
tail -n 80 -F "${files[@]}" | grep --line-buffered -E '\[debug:|==>'
