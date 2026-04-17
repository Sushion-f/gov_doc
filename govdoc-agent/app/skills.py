"""Backward-compatible shim for the renamed capability adapter module.

Prefer importing from `app.agent_capability_adapter`.
"""

from .agent_capability_adapter import *  # noqa: F401,F403
