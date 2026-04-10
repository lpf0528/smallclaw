from langchain_core.tools import tool
from typing import Annotated, Any, Literal
from app.agents.tools.simple_tools import direct_response_tool, ask_clarification_tool


@tool("recommended_related_test_questions")
def recommended_related_test_questions_tool(
    related_test_questions: Annotated[str, "The recommended test questions."],
):
    """Generate recommended related test questions."""
    return


@tool("generate_quiz")
def generate_quiz_tool():
    """Generate a quiz."""
    return
