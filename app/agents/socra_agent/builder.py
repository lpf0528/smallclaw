
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph, END
from app.agents.socra_agent.nodes import coordinator_node
from app.agents.socra_agent.types import State


def _build_base_graph():
    builder = StateGraph(State)
    builder.add_edge(START, "coordinator")
    builder.add_node("coordinator", coordinator_node)
    builder.add_edge("coordinator", END)
    return builder


def build_graph_with_memory():

    memory = MemorySaver()

    # build state graph
    builder = _build_base_graph()
    return builder.compile(checkpointer=memory)


def build_graph():
    builder = _build_base_graph()
    return builder.compile()


graph = build_graph()
