import json
import shutil
from pathlib import Path

from .config import settings


def data_root() -> Path:
    root = Path(settings.workspace_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        return root
    except OSError:
        fallback = Path(__file__).resolve().parent.parent / ".runtime-data" / "users"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def user_root(user_id: str) -> Path:
    root = data_root() / user_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_workspace_root(user_id: str) -> Path:
    root = user_root(user_id) / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_memory_root(user_id: str) -> Path:
    root = user_root(user_id) / "memory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def user_template_root(user_id: str) -> Path:
    root = user_root(user_id) / "templates"
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_node_dir(user_id: str, node_id: str) -> Path:
    root = user_workspace_root(user_id) / node_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_workspace_version(
    user_id: str,
    node_id: str,
    version_no: int,
    title: str,
    content_html: str | None,
    content_text: str | None,
    annotations: list[dict] | None = None,
) -> str:
    node_dir = workspace_node_dir(user_id, node_id)
    version_dir = node_dir / f"v{version_no:04d}"
    version_dir.mkdir(parents=True, exist_ok=True)
    (version_dir / "title.txt").write_text(title or "", encoding="utf-8")
    (version_dir / "content.html").write_text(content_html or "<p></p>", encoding="utf-8")
    (version_dir / "content.txt").write_text(content_text or "", encoding="utf-8")
    (version_dir / "annotations.json").write_text(
        json.dumps(annotations or [], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(version_dir.relative_to(user_root(user_id)))


def write_memory_doc(user_id: str, name: str, content: str) -> str:
    root = user_memory_root(user_id)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return str(path.relative_to(user_root(user_id)))
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(user_root(user_id)))


def read_user_doc(user_id: str, relative_path: str | None) -> str:
    if not relative_path:
        return ""
    path = user_root(user_id) / relative_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def clear_user_memory_subdir(user_id: str, relative_dir: str) -> None:
    path = user_memory_root(user_id) / relative_dir
    if path.exists():
        shutil.rmtree(path)


def write_template_file(user_id: str, file_name: str, content: bytes) -> str:
    root = user_template_root(user_id)
    path = root / file_name
    path.write_bytes(content)
    return str(path.relative_to(user_root(user_id)))
