

from langgraph.graph import START, StateGraph, END
from app.lead_agent.graph.nodes import semantic_parser_node, schema_retriever_node
from app.lead_agent.graph.types import State


def _build_base_graph():
    builder = StateGraph(State)
    builder.add_edge(START, "semantic_parser")
    builder.add_node("semantic_parser", semantic_parser_node)
    builder.add_edge("semantic_parser", "schema_retriever")
    builder.add_node("schema_retriever", schema_retriever_node)
    builder.add_edge("schema_retriever", END)
    return builder


def build_graph():
    builder = _build_base_graph()
    return builder.compile()
