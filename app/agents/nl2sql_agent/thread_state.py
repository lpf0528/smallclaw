from langchain.agents import AgentState
from typing import NotRequired


class ThreadState(AgentState):
    title: NotRequired[str | None]
