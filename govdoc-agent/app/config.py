import json
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MODEL_JSON_PATH = _ROOT / "config" / "model.json"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        env_path = _ROOT / ".env"
        if env_path.is_file():
            load_dotenv(env_path)
    except ImportError:
        pass


def _load_model_json() -> dict:
    """读取 config/model.json；文件缺失或解析失败时返回空 dict。"""
    if not _MODEL_JSON_PATH.is_file():
        return {}
    try:
        with open(_MODEL_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


_load_dotenv()
_MODEL_CONFIG = _load_model_json()
_MODEL_LLM = _MODEL_CONFIG.get("llm") if isinstance(_MODEL_CONFIG.get("llm"), dict) else {}
_MODEL_CONTEXT = (
    _MODEL_CONFIG.get("context") if isinstance(_MODEL_CONFIG.get("context"), dict) else {}
)


def _llm_str(key: str) -> str:
    """仅从 model.json 的 llm 段读取字符串；缺省或空则返回 \"\"。"""
    raw = _MODEL_LLM.get(key)
    if raw is None:
        return ""
    return str(raw).strip()


def _llm_float(key: str, if_missing: float) -> float:
    """仅从 model.json 读取；键不存在或空串时使用 if_missing（仅作类型占位，不作为业务默认）。"""
    raw = _MODEL_LLM.get(key)
    if raw is None:
        return if_missing
    if isinstance(raw, str) and raw.strip() == "":
        return if_missing
    return float(raw)


def _llm_int(key: str, if_missing: int) -> int:
    raw = _MODEL_LLM.get(key)
    if raw is None:
        return if_missing
    if isinstance(raw, str) and raw.strip() == "":
        return if_missing
    return int(raw)


def _llm_bool(key: str, if_missing: bool) -> bool:
    raw = _MODEL_LLM.get(key)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return if_missing
    if isinstance(raw, str) and raw.strip() == "":
        return if_missing
    return str(raw).lower() == "true"


def _context_float(key: str, if_missing: float) -> float:
    raw = _MODEL_CONTEXT.get(key)
    if raw is None:
        return if_missing
    if isinstance(raw, str) and raw.strip() == "":
        return if_missing
    return float(raw)


def _context_int(key: str, if_missing: int) -> int:
    raw = _MODEL_CONTEXT.get(key)
    if raw is None:
        return if_missing
    if isinstance(raw, str) and raw.strip() == "":
        return if_missing
    return int(raw)


def _parse_available_models() -> list[dict[str, str]]:
    """解析 llm.available_models：每项含 id（网关 model 名）与 label（展示名）。"""
    raw = _MODEL_LLM.get("available_models")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        mid = str(item.get("id") or item.get("modelName") or "").strip()
        if not mid:
            continue
        label = str(item.get("label") or item.get("modelDisplayName") or mid).strip()
        out.append({"id": mid, "label": label})
    return out


class Settings:
    app_name = "govdoc-agent"
    database_url = os.getenv("NEW_APP_DATABASE_URL", "sqlite:///./govdoc_agent.db")
    legacy_auth_base_url = os.getenv("LEGACY_AUTH_BASE_URL", "").rstrip("/")
    legacy_service_base_url = os.getenv("LEGACY_SERVICE_BASE_URL", "").rstrip("/")
    legacy_system_url = os.getenv("LEGACY_SYSTEM_URL", "/areport")
    enable_dev_auth_mock = os.getenv("ENABLE_DEV_AUTH_MOCK", "true").lower() == "true"

    # 以下 LLM 相关项**仅**来自 config/model.json 的 llm 段，不使用环境变量与代码中的供应商默认 URL/model
    llm_base_url = _llm_str("base_url").rstrip("/")
    # 若填写完整 POST 地址，则优先使用（避免 base_url 路径与网关不一致导致 404）
    llm_chat_completions_url = _llm_str("chat_completions_url").strip()
    llm_api_key = _llm_str("api_key")
    llm_default_model = _llm_str("default_model")
    llm_timeout_seconds = _llm_float("timeout_seconds", 90.0)
    enable_model_planner = _llm_bool("enable_planner", True)
    planner_model = _llm_str("planner_model")
    planner_temperature = _llm_float("planner_temperature", 0.1)
    planner_max_steps = _llm_int("planner_max_steps", 5)
    llm_available_models = _parse_available_models()

    debug_runtime_logs = os.getenv("NEW_APP_DEBUG_RUNTIME_LOGS", "true").lower() == "true"
    debug_log_max_chars = int(os.getenv("NEW_APP_DEBUG_LOG_MAX_CHARS", "40000"))
    debug_log_max_string_chars = int(
        os.getenv("NEW_APP_DEBUG_LOG_MAX_STRING_CHARS", "12000")
    )
    # 分路日志：后端调用、模型调用各写独立文件；空字符串表示落在默认 runtime_logs/ 下。
    backend_log_path = os.getenv(
        "NEW_APP_BACKEND_LOG_PATH",
        str(_ROOT / "runtime_logs" / "backend.log"),
    )
    model_log_path = os.getenv(
        "NEW_APP_MODEL_LOG_PATH",
        str(_ROOT / "runtime_logs" / "model.log"),
    )
    # 单个日志文件上限（字节），超过后滚动到 .1/.2/... 保留历史。
    log_file_max_bytes = int(os.getenv("NEW_APP_LOG_FILE_MAX_BYTES", str(20 * 1024 * 1024)))
    log_file_backup_count = int(os.getenv("NEW_APP_LOG_FILE_BACKUP_COUNT", "5"))
    # 是否同时把 log_stage 的内容回显到 stdout（便于 uvicorn 聚合日志查看）；默认关闭以免和文件重复。
    log_stage_echo_stdout = os.getenv("NEW_APP_LOG_STAGE_ECHO_STDOUT", "false").lower() == "true"
    # debug 日志样式：summary=汇总输入/汇总输出的人类可读块（默认）；json=整条缩进 JSON（旧版，便于深度排错）
    _debug_log_style = os.getenv("NEW_APP_DEBUG_LOG_STYLE", "summary").strip().lower()
    debug_log_style = _debug_log_style if _debug_log_style in ("summary", "json") else "summary"
    workspace_root = os.getenv("NEW_APP_WORKSPACE_ROOT", "/data/new-app/users")
    context_window_tokens = int(
        os.getenv(
            "NEW_APP_CONTEXT_WINDOW_TOKENS",
            str(_context_int("window_tokens", 128000)),
        )
    )
    context_compact_trigger_ratio = float(
        os.getenv(
            "NEW_APP_CONTEXT_COMPACT_TRIGGER_RATIO",
            str(_context_float("compact_trigger_ratio", 0.75)),
        )
    )
    context_compact_target_ratio = float(
        os.getenv(
            "NEW_APP_CONTEXT_COMPACT_TARGET_RATIO",
            str(_context_float("compact_target_ratio", 0.40)),
        )
    )
    compaction_preserve_recent_messages = int(
        os.getenv(
            "NEW_APP_COMPACTION_PRESERVE_RECENT_MESSAGES",
            str(_context_int("keep_recent_messages", 6)),
        )
    )
    compaction_max_chars = int(
        os.getenv(
            "NEW_APP_COMPACTION_MAX_CHARS",
            str(int(context_window_tokens * context_compact_trigger_ratio * 4)),
        )
    )
    compaction_summary_max_chars = int(
        os.getenv(
            "NEW_APP_COMPACTION_SUMMARY_MAX_CHARS",
            str(_context_int("summary_max_chars", 4000)),
        )
    )
    compaction_summary_max_lines = int(
        os.getenv("NEW_APP_COMPACTION_SUMMARY_MAX_LINES", "24")
    )
    compaction_summary_max_line_chars = int(
        os.getenv("NEW_APP_COMPACTION_SUMMARY_MAX_LINE_CHARS", "160")
    )
    planner_max_tool_rounds = int(
        os.getenv("NEW_APP_PLANNER_MAX_TOOL_ROUNDS", "6")
    )
    subagent_max_depth = int(
        os.getenv("NEW_APP_SUBAGENT_MAX_DEPTH", "3")
    )
    subagent_max_output_retries = int(
        os.getenv("NEW_APP_SUBAGENT_MAX_OUTPUT_RETRIES", "1")
    )
    cors_origins = [
        item.strip()
        for item in os.getenv(
            "NEW_APP_CORS_ORIGINS",
            "http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000",
        ).split(",")
        if item.strip()
    ]


settings = Settings()
