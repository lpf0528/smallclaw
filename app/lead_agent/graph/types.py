from langgraph.graph import MessagesState


class State(MessagesState):
    question: str = ""
    semantic: str = ""
