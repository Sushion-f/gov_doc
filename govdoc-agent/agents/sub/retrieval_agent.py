from ..base_agent import BaseAgent
from ..registry import get_agent_spec


class RetrievalAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(get_agent_spec("retrieval"))
